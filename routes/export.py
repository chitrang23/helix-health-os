# routes/export.py
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, ClinicalObservation, SourceDocument, UserMedication
from services.fhir_exporter import FHIRExporter
from services.handoff_engine import HandoffEngine

# main.py includes this router with prefix="/api/export"
router = APIRouter(tags=["FHIR & Data Export"])


@router.get("/health")
async def export_health():
    return {"status": "export active"}


@router.get("/fhir")
def export_fhir_bundle(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Exports the authenticated patient's clinical health records as an HL7 FHIR R4
    Transaction Bundle. Grounded strictly in database observations.
    Never fabricates patient observations or defaults.
    """
    try:
        observations = (
            db.query(ClinicalObservation)
            .filter(ClinicalObservation.user_id == current_user.id)
            .all()
        )

        user_data = {
            "id": f"Patient-{current_user.id}",
            "gender": current_user.gender or "unknown",
            "birth_date": current_user.dob or "Not documented"
        }

        # Convert actual stored observations into the payload expected by FHIRExporter
        biomarkers_payload = {}
        for obs in observations:
            val = obs.normalized_numeric_value if obs.normalized_numeric_value is not None else obs.original_value
            try:
                biomarkers_payload[obs.analyte_as_written] = float(val)
            except (ValueError, TypeError):
                continue

        lab_records = [{"biomarkers": biomarkers_payload}] if biomarkers_payload else []
        bundle = FHIRExporter.generate_patient_bundle(user_data, lab_records)
        return bundle
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"FHIR bundle export failed: {str(e)}"
        )


@router.get("/handoff-summary")
def export_handoff_summary(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Generates a 1-page clinical handoff summary grounded strictly in the
    authenticated patient's verified observations, active medications, and records.
    Never assumes medications, allergies, or baseline biomarkers.
    """
    observations = (
        db.query(ClinicalObservation, SourceDocument)
        .outerjoin(SourceDocument, ClinicalObservation.document_id == SourceDocument.id)
        .filter(ClinicalObservation.user_id == current_user.id)
        .order_by(ClinicalObservation.effective_date.asc())
        .all()
    )

    if not observations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available — no source records or uploaded reports found to generate handoff summary."
        )

    # Fetch verified patient medications & supplements from database
    meds = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == current_user.id, UserMedication.is_active.is_(True))
        .all()
    )

    prescriptions = [m.substance_name for m in meds if not m.is_supplement]
    supplements = [m.substance_name for m in meds if m.is_supplement]

    patient_data = {
        "id": current_user.id,
        "name": current_user.full_name or current_user.email.split("@")[0].title(),
        "email": current_user.email,
        "gender": current_user.gender,
        "dob": current_user.dob,
        "active_prescriptions": prescriptions,
        "active_supplements": supplements
    }

    obs_list = [obs for obs, _ in observations]
    handoff = HandoffEngine.build_doctor_briefing(patient_data, obs_list)
    return handoff