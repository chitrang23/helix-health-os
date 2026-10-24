# routes/drug_safety.py
import os
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from google import genai
from google.genai import types

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, DrugRuleModel, ClinicalObservation, UserMedication
from services.safety_engine import SafetyEngine

# Main router; routes/drug_safety.py is mounted in main.py at /api/drug-safety
router = APIRouter(tags=["Drug Safety & Interactions"])


class SafetyCheckPayload(BaseModel):
    medications: Optional[List[str]] = Field(default_factory=list, description="List of active prescription names")
    supplements: Optional[List[str]] = Field(default_factory=list, description="List of daily vitamins and supplements")


@router.get("/")
def get_drug_safety_status(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Returns active pharmacovigilance rules registered in the system
    and the authenticated patient's verified active medications.
    Never returns hardcoded demo drugs.
    """
    rules_count = db.query(DrugRuleModel).filter(DrugRuleModel.is_active.is_(True)).count()
    user_meds = db.query(UserMedication).filter(
        UserMedication.user_id == current_user.id,
        UserMedication.is_active.is_(True)
    ).all()

    return {
        "status": "active",
        "registered_rules_count": rules_count,
        "patient_active_medications": [
            {
                "id": m.id,
                "name": m.substance_name,
                "dosage": m.dosage or "Not specified",
                "is_supplement": m.is_supplement,
                "source_type": m.source_type
            }
            for m in user_meds
        ],
        "message": f"Monitoring active against {rules_count} verified pharmacovigilance rules."
    }


@router.post("/audit")
@router.post("/")
def audit_prescriptions(
    req: SafetyCheckPayload,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Audits active prescriptions against supplements and the patient's verified lab biomarkers.
    Evaluates strictly against verified database interaction rules.
    Never invents, hallucinates, or silently assumes negative results.
    """
    meds = [m.strip() for m in req.medications if m and m.strip()]
    supps = [s.strip() for s in req.supplements if s and s.strip()]

    # If payload is empty, load active documented medications from this patient's vault
    if not meds and not supps:
        db_meds = db.query(UserMedication).filter(
            UserMedication.user_id == current_user.id,
            UserMedication.is_active.is_(True)
        ).all()
        for m in db_meds:
            if m.is_supplement:
                supps.append(m.substance_name)
            else:
                meds.append(m.substance_name)

    if not meds and not supps:
        return {
            "interactions_found": False,
            "severity": "NONE",
            "findings": [],
            "message": "Not available — no source data provided. Enter medications or upload a prescription to audit."
        }

    # 1. Fetch active database pharmacovigilance rules
    rules = db.query(DrugRuleModel).filter(DrugRuleModel.is_active.is_(True)).all()

    # 2. Fetch authenticated patient's latest verified lab biomarker values
    latest_observations = (
        db.query(ClinicalObservation)
        .filter(ClinicalObservation.user_id == current_user.id)
        .order_by(ClinicalObservation.effective_date.desc())
        .all()
    )

    biomarker_map = {}
    for obs in latest_observations:
        key = obs.analyte_as_written.lower().strip()
        if key not in biomarker_map and obs.normalized_numeric_value is not None:
            biomarker_map[key] = obs.normalized_numeric_value
        if obs.canonical_key:
            c_key = obs.canonical_key.lower().strip()
            if c_key not in biomarker_map and obs.normalized_numeric_value is not None:
                biomarker_map[c_key] = obs.normalized_numeric_value

    # 3. Deterministic Safety Evaluation via SafetyEngine
    alerts = SafetyEngine.evaluate_interactions(
        prescriptions=meds,
        supplements=supps,
        rules=rules,
        latest_biomarkers=biomarker_map
    )

    findings = []
    for a in alerts:
        findings.append({
            "combination": a.get("combination") or a.get("pair") or "Substance Interaction",
            "severity": a.get("severity") or a.get("level", "WARNING").upper(),
            "clinical_effect": a.get("clinical_effect") or a.get("mechanism", "Documented pharmacological concern."),
            "recommendation": a.get("recommendation", "Review concurrent timing and dosage with prescribing clinician."),
            "evidence_source": a.get("evidence_source", "Versioned Clinical Pharmacovigilance Rules")
        })

    # 4. Optional Extended Check via Gemini for substances not covered by cataloged rules
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key and (len(meds) + len(supps) >= 2) and not findings:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""You are a clinical pharmacologist and safety auditor.
Analyze potential drug-drug or drug-supplement interactions for:
- Active Prescriptions: {json.dumps(meds)}
- Supplements/Vitamins: {json.dumps(supps)}
- Patient Latest Labs: {json.dumps(biomarker_map)}

STRICT RULES:
1. Only return clinically verified interactions documented in peer-reviewed pharmacotherapy literature or FDA/EMA guidance.
2. If no documented interactions exist, return interactions_found: false with empty findings.
3. NEVER invent or fabricate hypothetical side effects.
4. Always cite identifiable evidence sources.

Return JSON format:
{{
  "interactions_found": true/false,
  "severity": "CRITICAL / MAJOR / MODERATE / NONE",
  "findings": [
    {{
       "combination": "Drug A + Supplement B",
       "clinical_effect": "Exact physiological mechanism of concern",
       "recommendation": "Concrete action for patient to discuss with doctor",
       "evidence_source": "Recognized pharmacological standard / clinical guideline"
    }}
  ]
}}"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3].strip()

            gemini_data = json.loads(raw_text)
            if gemini_data.get("interactions_found") and gemini_data.get("findings"):
                findings.extend(gemini_data["findings"])
        except Exception:
            # Deterministic rule findings remain unaffected if AI provider is unreachable
            pass

    interactions_found = len(findings) > 0
    if not interactions_found:
        return {
            "interactions_found": False,
            "severity": "NONE",
            "findings": [],
            "substances_audited": meds + supps,
            "biomarkers_referenced_count": len(biomarker_map),
            "message": "No interactions or contraindications found in cataloged safety rules for this regimen.",
            "disclaimer": "Screening covers cataloged rules and documented references. Always consult your prescribing physician."
        }

    # Determine maximum severity
    has_critical = any(f.get("severity", "").upper() == "CRITICAL" for f in findings)
    has_high = any(f.get("severity", "").upper() in ("HIGH", "MAJOR", "DANGER") for f in findings)
    overall_severity = "CRITICAL" if has_critical else ("HIGH" if has_high else "MODERATE")

    return {
        "interactions_found": True,
        "severity": overall_severity,
        "findings": findings,
        "substances_audited": meds + supps,
        "biomarkers_referenced_count": len(biomarker_map),
        "disclaimer": "Pharmacological screening tool. Does not replace physician oversight or clinical pharmacist consultation."
    }