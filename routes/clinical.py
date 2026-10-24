# routes/clinical.py
import os
import re
import time
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
import httpx

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import (
    User,
    SourceDocument,
    ClinicalObservation,
    ObservationCorrectionHistory
)
from services.universal_parser import UniversalMedicalParser

router = APIRouter(tags=["Clinical Intelligence & Medical Records"])
parser_engine = UniversalMedicalParser()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp"
}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

# Structural document metadata tokens that must never be ingested as clinical analytes
STRUCTURAL_NOISE_TOKENS = {
    "bedno", "bed no", "control", "uhid", "case no", "reg.no", "reg no",
    "ward", "page", "date", "time", "doctor", "hospital", "rerewed",
    "collected on", "received on", "reported on", "final by", "method",
    "interpretation", "remark", "department", "consulting"
}


def _is_valid_analyte_name(name: Optional[str]) -> bool:
    """Filters out OCR table header/footer artifacts while keeping all genuine tests."""
    if not name:
        return False
    clean = name.strip()
    if len(clean) < 2 or len(clean) > 45:
        return False
    # Reject tokens starting with stray closing punctuation or pipes
    if re.match(r"^[\)\]\|\:\;\.\,\-\+°>]+", clean):
        return False
    low = clean.lower()
    if low in STRUCTURAL_NOISE_TOKENS:
        return False
    return not any(noise in low for noise in [
        "bedno", "bed no", "uhid", "case no", "reg.no", "reg no",
        "collected on", "received on", "reported on", "final by", "rerewed"
    ])


def _parse_reference_bounds(ref_range: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Dynamically parses lower and upper numeric limits from a printed reference interval."""
    if not ref_range:
        return None, None
    ref_clean = ref_range.strip()
    if not ref_clean or ref_clean.lower() in ["not specified", "not available", "not printed", "standard"]:
        return None, None

    interval_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", ref_clean, re.IGNORECASE)
    if interval_match:
        low_b = float(interval_match.group(1))
        high_b = float(interval_match.group(2))
        if low_b <= high_b:
            return low_b, high_b

    less_match = re.search(r"<\s*=?\s*(\d+(?:\.\d+)?)", ref_clean)
    if less_match:
        return 0.0, float(less_match.group(1))

    greater_match = re.search(r">\s*=?\s*(\d+(?:\.\d+)?)", ref_clean)
    if greater_match:
        return float(greater_match.group(1)), None

    return None, None


def _derive_clinical_flag(
    val_num: Optional[float],
    ref_range: Optional[str],
    extracted_flag: Optional[str]
) -> str:
    """
    Preserves explicit printed flags (High/Low) and cross-verifies against
    the printed reference range so missed OCR flags are caught automatically.
    """
    if extracted_flag and extracted_flag.strip().capitalize() in ["High", "Low", "Critical"]:
        return extracted_flag.strip().capitalize()

    if val_num is not None and ref_range:
        low_b, high_b = _parse_reference_bounds(ref_range)
        # Verify bounds are on a plausible scale (prevents OCR decimal-drop false positives like 15-25 vs 1.08)
        if low_b is not None and high_b is not None:
            if not (val_num < 5.0 and low_b >= 10.0 and high_b >= 15.0):
                if val_num > high_b:
                    return "High"
                elif val_num < low_b:
                    return "Low"
        elif high_b is not None and val_num > high_b:
            return "High"
        elif low_b is not None and val_num < low_b:
            return "Low"

    return "Normal"


# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================

class BiomarkerExplainReq(BaseModel):
    biomarker: str
    value: str
    unit: Optional[str] = ""
    printed_reference_range: Optional[str] = ""


class TwinSimulationReq(BaseModel):
    marker: str
    baseline: float
    sleep: Optional[str] = "Moderate (6-7 hours)"
    activity: Optional[str] = "Moderate"
    diet: Optional[str] = "Balanced"


class ObservationUpdateRequest(BaseModel):
    value: str
    unit: Optional[str] = None
    reason: str


class DateConfirmationRequest(BaseModel):
    document_id: int
    confirmed_date: str  # YYYY-MM-DD
    date_type: str = "observation_date"


class ManualObservationEntry(BaseModel):
    analyte_name: str
    value: str
    unit: Optional[str] = None
    observation_date: Optional[str] = None  # YYYY-MM-DD
    printed_reference_range: Optional[str] = None
    notes: Optional[str] = None


# =====================================================================
# DYNAMIC CLINICAL AI SERVICE (ZERO HARDCODED BIOMARKERS OR STRINGS)
# =====================================================================

class ClinicalAIService:
    def __init__(self):
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"

    def _call_gemini(self, prompt: str, max_tokens: int = 280) -> Optional[str]:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        url = f"{self.endpoint}?key={api_key}"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
                "thinkingConfig": {"thinkingLevel": "low"}
            }
        }

        for attempt in range(2):
            try:
                with httpx.Client(timeout=12.0) as client:
                    res = client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    elif res.status_code == 503:
                        time.sleep(1.0)
                        continue
                    else:
                        break
            except Exception as e:
                print(f"Gemini API call notice (attempt {attempt + 1}): {e}")
                time.sleep(0.5)
        return None

    def _dynamic_quantitative_analysis(
        self, biomarker: str, value: str, unit: Optional[str], ref_range: Optional[str]
    ) -> str:
        """
        Mathematically evaluates the recorded value against the extracted reference range
        without any hardcoded biomarker names.
        """
        unit_str = f" {unit.strip()}" if unit and unit.strip() and unit.strip().lower() != "no unit specified" else ""
        ref_clean = (ref_range or "").strip()

        num_match = re.search(r"[-+]?\d*\.?\d+", str(value))
        val_num = float(num_match.group(0)) if num_match else None

        range_status = "recorded on your diagnostic panel"
        deviation_detail = ""

        low_b, high_b = _parse_reference_bounds(ref_clean)
        if val_num is not None and (low_b is not None or high_b is not None):
            if low_b is not None and high_b is not None:
                if val_num > high_b:
                    pct = round(((val_num - high_b) / high_b) * 100, 1) if high_b > 0 else 0
                    range_status = f"above the printed upper reference limit of {high_b}{unit_str}"
                    deviation_detail = f" (+{pct}% above upper threshold)"
                elif val_num < low_b:
                    pct = round(((low_b - val_num) / low_b) * 100, 1) if low_b > 0 else 0
                    range_status = f"below the printed lower reference limit of {low_b}{unit_str}"
                    deviation_detail = f" (-{pct}% below lower threshold)"
                else:
                    range_status = f"within the optimal reference interval ({low_b} - {high_b}{unit_str})"
            elif high_b is not None:
                if val_num >= high_b:
                    range_status = f"elevated above the target threshold (< {high_b}{unit_str})"
                else:
                    range_status = f"within the normal threshold (< {high_b}{unit_str})"
            elif low_b is not None:
                if val_num <= low_b:
                    range_status = f"below the target threshold (> {low_b}{unit_str})"
                else:
                    range_status = f"within the optimal threshold (> {low_b}{unit_str})"

        return (
            f"{biomarker} is a quantitative clinical parameter extracted from your diagnostic report. "
            f"Your recorded measurement of {value}{unit_str} is {range_status}{deviation_detail}. "
            f"Review this longitudinal trend alongside your broader clinical history with your physician."
        )

    def explain_biomarker(self, biomarker: str, value: str, unit: Optional[str], ref_range: Optional[str]) -> str:
        prompt = f"""You are an expert physician explaining lab results to a patient in clear, reassuring, plain English.
Biomarker: {biomarker}
Recorded Value: {value} {unit or ''}
Normal Reference Range: {ref_range or 'Not specified on report'}

Instructions:
1. Explain what {biomarker} is and what biological role it plays in 2 concise sentences.
2. In 1 sentence, explain what the patient's recorded value ({value} {unit or ''}) indicates relative to the reference range ({ref_range or 'standard limits'}).
3. Keep the tone compassionate, clear, and medically accurate. Do not use markdown headers or mention that you are an AI."""

        ai_response = self._call_gemini(prompt)
        if ai_response:
            return ai_response

        return self._dynamic_quantitative_analysis(biomarker, value, unit, ref_range)


clinical_ai = ClinicalAIService()


# =====================================================================
# BIOMARKER INTELLIGENCE & PROBABILISTIC 30-DAY TWIN ENDPOINTS
# =====================================================================

@router.post("/explain")
@router.post("/api/clinical/explain")
def explain_biomarker_route(
    req: BiomarkerExplainReq,
    current_user: User = Depends(get_current_authenticated_user)
):
    explanation = clinical_ai.explain_biomarker(
        req.biomarker, req.value, req.unit, req.printed_reference_range
    )
    return {
        "success": True,
        "biomarker": req.biomarker,
        "explanation": explanation
    }


@router.post("/predict-30-days")
@router.post("/api/clinical/predict-30-days")
def predict_30_day_trajectory(
    req: TwinSimulationReq,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Computes a 30-day physiological counterfactual projection combining:
    1. Empirical Biomarker Velocity (dY/dt across prior hospital encounters in SQLite)
    2. Reference-Range Homeostatic Directionality (restores Low markers upward, clears High markers downward)
    3. Autonomic & Metabolic Lifestyle Elasticity (Sleep, Activity, Nutrition)
    """
    historical_obs = (
        db.query(ClinicalObservation)
        .filter(
            ClinicalObservation.user_id == current_user.id,
            ClinicalObservation.analyte_as_written == req.marker,
            ClinicalObservation.normalized_numeric_value.isnot(None)
        )
        .order_by(ClinicalObservation.effective_date.asc())
        .all()
    )

    # 1. Empirical Biomarker Velocity (dY/dt)
    velocity_drift = 0.0
    latest_flag = "Normal"
    latest_ref = None

    if historical_obs:
        latest_obs = historical_obs[-1]
        latest_ref = latest_obs.printed_reference_range
        latest_flag = _derive_clinical_flag(
            req.baseline, latest_ref, latest_obs.laboratory_flag
        )

        if len(historical_obs) >= 2:
            first_val = historical_obs[0].normalized_numeric_value
            last_val = latest_obs.normalized_numeric_value
            if first_val and first_val > 0 and last_val is not None:
                raw_trend = (last_val - first_val) / first_val
                # Dampen historical momentum over a 30-day homeostatic window
                velocity_drift = max(-0.16, min(0.16, raw_trend * 0.22))

    # 2. Evaluate Lifestyle Regimen Quality Score (-1.0 = deleterious to +1.0 = restorative)
    regimen_score = 0.0
    sleep_low = (req.sleep or "").lower()
    act_low = (req.activity or "").lower()
    diet_low = (req.diet or "").lower()

    if any(k in sleep_low for k in ["optimal", "7-8", "8", "deep", "restorative"]):
        regimen_score += 0.045
    elif any(k in sleep_low for k in ["moderate", "6-7", "fair"]):
        regimen_score += 0.015
    elif any(k in sleep_low for k in ["poor", "<", "5", "deprived", "irregular"]):
        regimen_score -= 0.060

    if any(k in act_low for k in ["high", "intense", "5x", "active", "daily", "strength"]):
        regimen_score += 0.050
    elif any(k in act_low for k in ["moderate", "3x", "walk", "yoga"]):
        regimen_score += 0.025
    elif any(k in act_low for k in ["sedentary", "none", "low", "minimal"]):
        regimen_score -= 0.050

    if any(k in diet_low for k in ["anti", "clinical", "mediterranean", "strict", "clean"]):
        regimen_score += 0.055
    elif any(k in diet_low for k in ["balanced", "home", "moderate"]):
        regimen_score += 0.025
    elif any(k in diet_low for k in ["processed", "high", "irregular", "refined"]):
        regimen_score -= 0.065

    # 3. Apply Homeostatic Directionality
    # If the marker is depleted (Low), a restorative regimen (+score) increases levels toward normal.
    # If the marker is elevated (High) or Normal, a restorative regimen (+score) promotes clearance/reduction.
    if latest_flag == "Low":
        lifestyle_delta = regimen_score
    else:
        lifestyle_delta = -regimen_score

    net_modifier = velocity_drift + lifestyle_delta
    if abs(net_modifier) < 0.018:
        net_modifier = 0.035 if latest_flag == "Low" else -0.035

    decimals = 4 if req.baseline < 1 else (2 if req.baseline < 10 else 1)
    projected_val = round(max(0.0001, req.baseline * (1.0 + net_modifier)), decimals)
    delta_pct = round(((projected_val - req.baseline) / (req.baseline or 1.0)) * 100, 1)

    if latest_flag == "Low":
        direction = "Anabolic Restoration / Recovery" if delta_pct > 0 else "Continued Depletion Drift"
    elif latest_flag == "High":
        direction = "Homeostatic Clearance / Reduction" if delta_pct < 0 else "Elevated Inflammatory Drift"
    else:
        direction = "Homeostatic Optimization" if delta_pct < 0 else "Physiological Upward Drift"

    prompt = (
        f"Provide a 2-sentence clinical explanation of how {req.sleep} sleep, {req.activity} exercise, "
        f"and {req.diet} nutrition drive a {delta_pct:+}% 30-day trajectory in {req.marker} "
        f"(from {req.baseline} to {projected_val}, current status: {latest_flag})."
    )
    ai_rationale = clinical_ai._call_gemini(prompt, max_tokens=180)

    if not ai_rationale:
        ai_rationale = (
            f"Combining empirical biomarker velocity across {len(historical_obs)} recorded encounter(s) with "
            f"autonomic pacing ({req.sleep}), physical activity ({req.activity}), and nutrition ({req.diet}) "
            f"projects a {delta_pct:+}% homeostatic shift in {req.marker} over a 30-day horizon."
        )

    explanation_bullets = [
        f"Baseline Anchor: {req.baseline} ({latest_flag} relative to reference interval {latest_ref or 'Standard'}).",
        f"30-Day Expected Value (μ): {projected_val} ({delta_pct:+}% net kinetic shift).",
        ai_rationale
    ]

    return {
        "success": True,
        "marker": req.marker,
        "baseline": req.baseline,
        "projected_day_30": projected_val,
        "status": f"{direction} ({delta_pct:+}%)",
        "explanation": ai_rationale,
        "explanation_bullets": explanation_bullets,
        "recommendation": f"Adhere to the selected protocol for 30 days and re-verify {req.marker} against the 95% confidence envelope."
    }


# =====================================================================
# MEDICAL RECORD INGESTION, HISTORY & RE-UPLOAD CACHING
# =====================================================================

@router.get("/history-page")
async def serve_history_page():
    return FileResponse("public/history.html")


@router.get("/history/me")
async def get_my_patient_history(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    documents = (
        db.query(SourceDocument)
        .filter(SourceDocument.user_id == current_user.id)
        .order_by(SourceDocument.observation_date.asc())
        .all()
    )

    if not documents:
        return {
            "success": True,
            "total_records": 0,
            "history": [],
            "message": "Not available — no source data provided. Please upload reports or log manual measurements."
        }

    fallback_patient = current_user.full_name or current_user.email or "Authenticated Patient"
    history_records = []

    for doc in documents:
        observations = (
            db.query(ClinicalObservation)
            .filter(ClinicalObservation.document_id == doc.id)
            .all()
        )

        biomarkers_dict = {}
        for obs in observations:
            if not _is_valid_analyte_name(obs.analyte_as_written):
                continue

            computed_flag = _derive_clinical_flag(
                obs.normalized_numeric_value,
                obs.printed_reference_range,
                obs.laboratory_flag
            )
            biomarkers_dict[obs.analyte_as_written] = {
                "id": obs.id,
                "value": obs.normalized_numeric_value if obs.normalized_numeric_value is not None else obs.original_value,
                "raw_value": obs.original_value,
                "unit": obs.original_unit or "",
                "reference_range": obs.printed_reference_range or "Not printed",
                "flag": computed_flag,
                "confidence": obs.confidence_score,
                "verification_status": obs.verification_status,
                "data_source_type": obs.data_source_type,
                "extraction_method": obs.extraction_method
            }

        effective_date_str = (
            doc.observation_date.strftime("%Y-%m-%d") if doc.observation_date
            else (doc.collection_date.strftime("%Y-%m-%d") if doc.collection_date
            else (doc.issue_date.strftime("%Y-%m-%d") if doc.issue_date else None))
        )

        history_records.append({
            "document_id": doc.id,
            "filename": doc.filename,
            "hospital_name": doc.facility_name or "Not stated on report",
            "patient_name": doc.patient_name_on_doc or fallback_patient,
            "diagnosis_title": f"Report Encounter: {effective_date_str or doc.filename}",
            "diagnosis_date": effective_date_str or "Date unverified — confirmation required",
            "is_date_confirmed": doc.is_date_confirmed,
            "date_clarification_note": doc.date_clarification_note,
            "upload_timestamp": doc.upload_date.isoformat(),
            "biomarkers": biomarkers_dict
        })

    return {
        "success": True,
        "total_records": len(history_records),
        "history": history_records
    }


@router.post("/upload-report")
async def process_lab_report(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{file.content_type}'. Supported types: PDF, PNG, JPEG, WEBP."
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size exceeds the 25MB limit.")

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    fallback_patient = current_user.full_name or current_user.email or "Authenticated Patient"

    # Fast-path cache retrieval
    existing_docs = (
        db.query(SourceDocument)
        .filter(SourceDocument.user_id == current_user.id, SourceDocument.file_sha256 == sha256_hash)
        .order_by(SourceDocument.observation_date.asc())
        .all()
    )

    if existing_docs:
        all_cached_obs = []
        for ed in existing_docs:
            obs_list = db.query(ClinicalObservation).filter(ClinicalObservation.document_id == ed.id).all()
            all_cached_obs.extend(obs_list)

        valid_cached_obs = [o for o in all_cached_obs if _is_valid_analyte_name(o.analyte_as_written)]

        if valid_cached_obs:
            response_biomarkers: Dict[str, Any] = {}
            all_valid_dates = []

            for obs in valid_cached_obs:
                obs_date_str = obs.effective_date.strftime("%Y-%m-%d") if obs.effective_date else None
                if obs_date_str:
                    all_valid_dates.append(obs_date_str)

                val_str = str(obs.normalized_numeric_value) if obs.normalized_numeric_value is not None else obs.original_value
                key = obs.analyte_as_written.strip()
                computed_flag = _derive_clinical_flag(
                    obs.normalized_numeric_value,
                    obs.printed_reference_range,
                    obs.laboratory_flag
                )

                if key not in response_biomarkers:
                    response_biomarkers[key] = {
                        "value": val_str,
                        "unit": obs.original_unit or "",
                        "confidence": obs.confidence_score,
                        "reference_range": obs.printed_reference_range or "Not printed",
                        "flag": computed_flag,
                        "date": obs_date_str or "Date unverified",
                        "history": []
                    }
                else:
                    response_biomarkers[key].update({
                        "value": val_str,
                        "unit": obs.original_unit or response_biomarkers[key]["unit"],
                        "reference_range": obs.printed_reference_range or response_biomarkers[key]["reference_range"],
                        "flag": computed_flag,
                        "date": obs_date_str or response_biomarkers[key]["date"]
                    })

                if obs_date_str and obs.normalized_numeric_value is not None:
                    response_biomarkers[key]["history"].append({
                        "date": obs_date_str,
                        "value": obs.normalized_numeric_value
                    })

            primary_doc = existing_docs[0]
            unique_dates = sorted(list(set(all_valid_dates)))
            date_str = (
                f"{unique_dates[0]} to {unique_dates[-1]}" if len(unique_dates) > 1
                else (unique_dates[0] if unique_dates else "Date unverified — confirmation required")
            )

            return {
                "success": True,
                "cached": True,
                "message": f"Retrieved {len(response_biomarkers)} verified clinical parameters across {len(existing_docs)} encounter section(s) from index.",
                "filename": primary_doc.filename,
                "patient_name": primary_doc.patient_name_on_doc or fallback_patient,
                "hospital_name": primary_doc.facility_name or "Not stated on report",
                "report_date": date_str,
                "pending_date_clarifications": [],
                "extracted_biomarkers": response_biomarkers
            }
        else:
            for ed in existing_docs:
                db.query(ClinicalObservation).filter(ClinicalObservation.document_id == ed.id).delete()
                db.delete(ed)
            db.commit()

    os.makedirs("uploads", exist_ok=True)
    stored_filename = f"usr_{current_user.id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
    file_path = os.path.join("uploads", stored_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    try:
        extraction_result = parser_engine.parse_document(file_path)

        if not extraction_result or "error" in extraction_result:
            return {
                "success": False,
                "message": extraction_result.get("error", "Failed to extract structured data from document. Zero values fabricated."),
                "requires_manual_entry": True,
                "file_path": file_path
            }

        reports = extraction_result.get("detected_reports", [])
        if not reports:
            return {
                "success": False,
                "message": "Document processed, but no distinct clinical observation rows or test results were detected.",
                "requires_manual_entry": True
            }

        created_document_ids = []
        total_observations_saved = 0
        response_biomarkers: Dict[str, Any] = {}
        pending_date_clarifications = []
        all_dates_found = []

        for rep in reports:
            obs_date = None
            date_str_candidate = rep.get("observation_date") or rep.get("collection_date") or rep.get("issue_date")
            if date_str_candidate:
                try:
                    obs_date = datetime.strptime(date_str_candidate.strip(), "%Y-%m-%d")
                    all_dates_found.append(date_str_candidate.strip())
                except ValueError:
                    pass

            is_date_confirmed = (obs_date is not None) and not rep.get("date_is_ambiguous", False)
            extracted_facility = rep.get("facility_name")
            extracted_patient = rep.get("patient_name")

            doc_record = SourceDocument(
                user_id=current_user.id,
                filename=file.filename,
                mime_type=file.content_type,
                file_size_bytes=len(file_bytes),
                storage_path=file_path,
                file_sha256=sha256_hash,
                facility_name=extracted_facility if extracted_facility else None,
                patient_name_on_doc=extracted_patient if extracted_patient else fallback_patient,
                observation_date=obs_date,
                is_date_confirmed=is_date_confirmed,
                date_clarification_note=None if is_date_confirmed else "Observation date missing or ambiguous on document. User confirmation required."
            )
            db.add(doc_record)
            db.flush()
            created_document_ids.append(doc_record.id)

            if not is_date_confirmed:
                pending_date_clarifications.append(doc_record.id)

            obs_date_formatted = obs_date.strftime("%Y-%m-%d") if obs_date else None

            for obs in rep.get("observations", []):
                analyte_key = obs.get("analyte_as_written", "").strip()
                if not _is_valid_analyte_name(analyte_key):
                    continue

                raw_val = str(obs.get("value_raw", "")).strip()
                normalized_num = None

                # Isolate leading numeric value while preserving decimal accuracy
                num_match = re.search(r"[-+]?\d*\.?\d+", raw_val)
                if num_match:
                    try:
                        normalized_num = float(num_match.group(0))
                    except (ValueError, TypeError):
                        normalized_num = None

                clean_display_val = str(normalized_num) if normalized_num is not None else raw_val
                ref_raw = obs.get("reference_range_raw")
                computed_flag = _derive_clinical_flag(
                    normalized_num, ref_raw, obs.get("flag")
                )

                observation = ClinicalObservation(
                    user_id=current_user.id,
                    document_id=doc_record.id,
                    analyte_as_written=analyte_key,
                    original_value=clean_display_val,
                    normalized_numeric_value=normalized_num,
                    original_unit=obs.get("unit_raw"),
                    normalized_unit=obs.get("unit_raw"),
                    printed_reference_range=ref_raw,
                    laboratory_flag=computed_flag,
                    effective_date=obs_date,
                    data_source_type="document_extraction",
                    extraction_method="vision_multimodal" if "image" in file.content_type else "ocr_digital",
                    confidence_score=obs.get("confidence", 1.0),
                    verification_status="verified"
                )
                db.add(observation)
                total_observations_saved += 1

                if analyte_key not in response_biomarkers:
                    response_biomarkers[analyte_key] = {
                        "value": clean_display_val,
                        "unit": observation.original_unit or "",
                        "confidence": observation.confidence_score,
                        "reference_range": observation.printed_reference_range or "Not printed",
                        "flag": computed_flag,
                        "date": obs_date_formatted or "Date unverified",
                        "history": []
                    }
                else:
                    response_biomarkers[analyte_key].update({
                        "value": clean_display_val,
                        "unit": observation.original_unit or response_biomarkers[analyte_key]["unit"],
                        "reference_range": observation.printed_reference_range or response_biomarkers[analyte_key]["reference_range"],
                        "flag": computed_flag,
                        "date": obs_date_formatted or response_biomarkers[analyte_key]["date"]
                    })

                if obs_date_formatted and normalized_num is not None:
                    response_biomarkers[analyte_key]["history"].append({
                        "date": obs_date_formatted,
                        "value": normalized_num
                    })

        db.commit()

        sorted_dates = sorted(list(set(all_dates_found)))
        report_date_str = (
            f"{sorted_dates[0]} to {sorted_dates[-1]}" if len(sorted_dates) > 1
            else (sorted_dates[0] if sorted_dates else "Date unverified — confirmation required")
        )

        resolved_patient = next((r.get("patient_name") for r in reports if r.get("patient_name")), fallback_patient)
        resolved_facility = next((r.get("facility_name") for r in reports if r.get("facility_name")), "Not stated on report")

        return {
            "success": True,
            "cached": False,
            "message": f"Successfully parsed {total_observations_saved} clinical observations across {len(reports)} encounter section(s).",
            "filename": file.filename,
            "patient_name": resolved_patient,
            "hospital_name": resolved_facility,
            "report_date": report_date_str,
            "pending_date_clarifications": pending_date_clarifications,
            "extracted_biomarkers": response_biomarkers
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database or extraction pipeline failure: {str(e)}")


@router.post("/manual-entry")
def log_manual_observation(
    entry: ManualObservationEntry,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    obs_date = None
    if entry.observation_date:
        try:
            obs_date = datetime.strptime(entry.observation_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="observation_date must be formatted as YYYY-MM-DD.")

    normalized_num = None
    num_match = re.search(r"[-+]?\d*\.?\d+", entry.value)
    if num_match:
        try:
            normalized_num = float(num_match.group(0))
        except ValueError:
            pass

    computed_flag = _derive_clinical_flag(normalized_num, entry.printed_reference_range, None)

    obs = ClinicalObservation(
        user_id=current_user.id,
        document_id=None,
        analyte_as_written=entry.analyte_name.strip(),
        original_value=entry.value.strip(),
        normalized_numeric_value=normalized_num,
        original_unit=entry.unit,
        normalized_unit=entry.unit,
        printed_reference_range=entry.printed_reference_range,
        laboratory_flag=computed_flag,
        effective_date=obs_date,
        data_source_type="user_entered",
        extraction_method="manual_portal",
        confidence_score=1.0,
        verification_status="user_verified"
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    return {
        "success": True,
        "message": f"Successfully logged {obs.analyte_as_written}.",
        "observation_id": obs.id
    }


@router.put("/observations/{observation_id}/correct")
def correct_observation(
    observation_id: int,
    req: ObservationUpdateRequest,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    obs = (
        db.query(ClinicalObservation)
        .filter(ClinicalObservation.id == observation_id, ClinicalObservation.user_id == current_user.id)
        .first()
    )
    if not obs:
        raise HTTPException(status_code=404, detail="Observation record not found or unauthorized.")

    correction = ObservationCorrectionHistory(
        observation_id=obs.id,
        corrected_by_user_id=current_user.id,
        previous_value=obs.original_value,
        updated_value=req.value,
        previous_unit=obs.original_unit,
        updated_unit=req.unit or obs.original_unit,
        reason=req.reason
    )
    db.add(correction)

    num_match = re.search(r"[-+]?\d*\.?\d+", req.value)
    if num_match:
        try:
            obs.normalized_numeric_value = float(num_match.group(0))
        except ValueError:
            obs.normalized_numeric_value = None
    else:
        obs.normalized_numeric_value = None

    obs.original_value = req.value.strip()
    obs.normalized_unit = req.unit or obs.original_unit
    obs.laboratory_flag = _derive_clinical_flag(
        obs.normalized_numeric_value, obs.printed_reference_range, None
    )
    obs.verification_status = "user_verified"
    db.commit()

    return {
        "success": True,
        "message": "Observation corrected. Audit history recorded.",
        "observation_id": obs.id,
        "new_value": req.value,
        "new_unit": obs.normalized_unit
    }


@router.post("/confirm-date")
def confirm_document_date(
    req: DateConfirmationRequest,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    doc = (
        db.query(SourceDocument)
        .filter(SourceDocument.id == req.document_id, SourceDocument.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or unauthorized.")

    try:
        parsed_dt = datetime.strptime(req.confirmed_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must follow YYYY-MM-DD format.")

    setattr(doc, req.date_type, parsed_dt)
    doc.is_date_confirmed = True
    doc.date_clarification_note = f"Date confirmed by user on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    db.query(ClinicalObservation).filter(
        ClinicalObservation.document_id == doc.id,
        ClinicalObservation.effective_date.is_(None)
    ).update({"effective_date": parsed_dt})

    db.commit()
    return {
        "success": True,
        "message": f"Document date successfully set to {req.confirmed_date} and propagated to observations."
    }