from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, ClinicalObservation, SourceDocument

# Do NOT specify prefix="/api/metrics" here because main.py already supplies it
router = APIRouter(tags=["Longitudinal Health Metrics"])


@router.get("/available-analytes")
def get_user_analytes(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Dynamic Test Discovery:
    Discovers all distinct test names/analytes extracted from this specific patient's documents.
    Does not assume hemoglobin, glucose, or any predefined biomarker panel exists.
    """
    records = (
        db.query(
            ClinicalObservation.analyte_as_written,
            ClinicalObservation.original_unit,
            func.count(ClinicalObservation.id).label("observation_count")
        )
        .filter(ClinicalObservation.user_id == current_user.id)
        .group_by(ClinicalObservation.analyte_as_written, ClinicalObservation.original_unit)
        .order_by(ClinicalObservation.analyte_as_written.asc())
        .all()
    )

    if not records:
        return {
            "status": "success",
            "message": "Not available — no source data provided. Upload a report to discover available biomarkers.",
            "analytes": []
        }

    return {
        "status": "success",
        "total_available": len(records),
        "analytes": [
            {
                "test_name": r[0],
                "unit": r[1] or "No unit specified",
                "count": r[2]
            }
            for r in records
        ]
    }


@router.get("/history")
def get_biomarker_history(
    test_name: str = Query(..., description="Exact or partial analyte name as extracted from actual reports"),
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Builds a unified, owner-specific health timeline for a given analyte.
    Guarantees zero fake data and traceable provenance.
    """
    clean_test_name = test_name.strip()
    if not clean_test_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analyte query parameter 'test_name' cannot be empty."
        )

    query_results = (
        db.query(ClinicalObservation, SourceDocument)
        .outerjoin(SourceDocument, ClinicalObservation.document_id == SourceDocument.id)
        .filter(
            ClinicalObservation.user_id == current_user.id,
            ClinicalObservation.analyte_as_written.ilike(f"%{clean_test_name}%")
        )
        .order_by(ClinicalObservation.effective_date.asc())
        .all()
    )

    if not query_results:
        return {
            "test_name": clean_test_name,
            "status": "success",
            "provenance": "Not available — no source data provided in your uploaded documents or manual inputs.",
            "data_points": [],
            "history": [],
            "total_observations": 0
        }

    data_points = []
    legacy_history = []
    units_observed = set()

    for obs, doc in query_results:
        unit_str = obs.original_unit or ""
        units_observed.add(unit_str)

        if obs.effective_date:
            date_display = obs.effective_date.strftime("%Y-%m-%d")
            date_verified = True
        elif doc and (doc.observation_date or doc.collection_date or doc.issue_date):
            dt = doc.observation_date or doc.collection_date or doc.issue_date
            date_display = dt.strftime("%Y-%m-%d")
            date_verified = doc.is_date_confirmed
        else:
            date_display = "Date unverified — confirmation required"
            date_verified = False

        numeric_val = obs.normalized_numeric_value
        if numeric_val is None:
            try:
                numeric_val = float(str(obs.original_value).replace(",", "").replace("<", "").replace(">", "").strip())
            except (ValueError, TypeError):
                numeric_val = None

        point_provenance = {
            "observation_id": obs.id,
            "document_id": doc.id if doc else None,
            "source_document": doc.filename if doc else "User direct entry",
            "facility_name": (doc.facility_name if doc and doc.facility_name else "Not stated on report"),
            "test_name": obs.analyte_as_written,
            "date": date_display,
            "is_date_verified": date_verified,
            "numeric_value": numeric_val,
            "raw_value": obs.original_value,
            "unit": unit_str or "Not stated",
            "printed_reference_range": obs.printed_reference_range or "Not available — no printed range on source document",
            "laboratory_flag": obs.laboratory_flag,
            "confidence_score": obs.confidence_score,
            "verification_status": obs.verification_status,
            "data_source_type": obs.data_source_type,
            "extraction_method": obs.extraction_method
        }
        data_points.append(point_provenance)

        if numeric_val is not None:
            legacy_history.append({
                "date": date_display,
                "value": numeric_val,
                "numeric_val": numeric_val,
                "unit": unit_str,
                "source": doc.filename if doc else "User entry"
            })

    unit_warning = None
    if len(units_observed) > 1:
        clean_units = [u if u else "blank" for u in units_observed]
        unit_warning = (
            f"Caution: Multiple units detected across records ({', '.join(clean_units)}). "
            "Values measured in different units cannot be safely compared directly on the same scale."
        )

    return {
        "test_name": clean_test_name,
        "status": "success",
        "total_observations": len(data_points),
        "is_unit_consistent": len(units_observed) <= 1,
        "units_detected": list(units_observed),
        "unit_warning": unit_warning,
        "data_points": data_points,
        "history": legacy_history
    }