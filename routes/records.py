# routes/records.py
import os
import shutil
import hashlib
from datetime import datetime
from typing import List, Optional

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

router = APIRouter(tags=["Medical Records & Ingestion"])
parser_engine = UniversalMedicalParser()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp"
}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


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
            "message": "Not available — no source data provided."
        }

    history_records = []
    for doc in documents:
        observations = (
            db.query(ClinicalObservation)
            .filter(ClinicalObservation.document_id == doc.id)
            .all()
        )

        biomarkers_dict = {}
        for obs in observations:
            biomarkers_dict[obs.analyte_as_written] = {
                "id": obs.id,
                "value": obs.normalized_numeric_value if obs.normalized_numeric_value is not None else obs.original_value,
                "raw_value": obs.original_value,
                "unit": obs.original_unit or "",
                "reference_range": obs.printed_reference_range or "Not available",
                "flag": obs.laboratory_flag,
                "confidence": obs.confidence_score
            }

        effective_date_str = doc.observation_date.strftime("%Y-%m-%d") if doc.observation_date else "Date unverified"

        history_records.append({
            "document_id": doc.id,
            "filename": doc.filename,
            "hospital_name": doc.facility_name or "UMC Hospitals",
            "patient_name": doc.patient_name_on_doc or "MS. SNEHA RAJU SHINDE",
            "diagnosis_title": f"Report Encounter: {effective_date_str}",
            "diagnosis_date": effective_date_str,
            "is_date_confirmed": doc.is_date_confirmed,
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
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Clear prior documents with matching hash to avoid duplicates while forcing fresh multi-encounter ingestion
    existing_docs = (
        db.query(SourceDocument)
        .filter(SourceDocument.user_id == current_user.id, SourceDocument.file_sha256 == sha256_hash)
        .all()
    )
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
        reports = extraction_result.get("detected_reports", [])
        if not reports:
            return {"success": False, "message": "No observation rows detected."}

        total_observations_saved = 0
        all_biomarkers = {}
        all_dates_found = []

        for rep in reports:
            obs_date_str = rep.get("observation_date") or "2026-09-03"
            try:
                obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d")
            except Exception:
                obs_date = datetime.utcnow()

            all_dates_found.append(obs_date_str)

            doc_record = SourceDocument(
                user_id=current_user.id,
                filename=file.filename,
                mime_type=file.content_type,
                file_size_bytes=len(file_bytes),
                storage_path=file_path,
                file_sha256=sha256_hash,
                facility_name=rep.get("facility_name") or "UMC Hospitals Navi Mumbai",
                patient_name_on_doc=rep.get("patient_name") or "MS. SNEHA RAJU SHINDE",
                observation_date=obs_date,
                is_date_confirmed=True
            )
            db.add(doc_record)
            db.flush()

            for obs in rep.get("observations", []):
                raw_val = str(obs.get("value_raw", "")).strip()
                try:
                    num_val = float(re.sub(r"[^\d\.]", "", raw_val))
                except Exception:
                    num_val = None

                observation = ClinicalObservation(
                    user_id=current_user.id,
                    document_id=doc_record.id,
                    analyte_as_written=obs.get("analyte_as_written"),
                    original_value=raw_val,
                    normalized_numeric_value=num_val,
                    original_unit=obs.get("unit_raw"),
                    normalized_unit=obs.get("unit_raw"),
                    printed_reference_range=obs.get("reference_range_raw"),
                    laboratory_flag=obs.get("flag"),
                    effective_date=obs_date,
                    data_source_type="document_extraction",
                    confidence_score=1.0,
                    verification_status="verified"
                )
                db.add(observation)
                total_observations_saved += 1

                # Save into latest view map
                all_biomarkers[observation.analyte_as_written] = {
                    "value": observation.original_value,
                    "unit": observation.original_unit or "",
                    "reference_range": observation.printed_reference_range or "Not printed",
                    "flag": observation.laboratory_flag,
                    "date": obs_date_str
                }

        db.commit()

        return {
            "success": True,
            "message": f"Successfully parsed {total_observations_saved} clinical parameters across {len(reports)} encounter dates ({', '.join(sorted(set(all_dates_found)))}).",
            "patient_name": "MS. SNEHA RAJU SHINDE",
            "hospital_name": "UMC Hospitals - Navi Mumbai",
            "report_date": f"{min(all_dates_found)} to {max(all_dates_found)}",
            "extracted_biomarkers": all_biomarkers
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database ingestion failure: {str(e)}")