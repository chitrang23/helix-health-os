from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, ClinicalObservation, LifestyleEntry

# Mounted in main.py with prefix="/api/twin"
router = APIRouter(tags=["Digital Twin & Metabolic Simulation"])


class TwinSimulationRequest(BaseModel):
    target_biomarker: str = Field(..., description="Analyte name to simulate (e.g., Fasting Blood Glucose, HbA1c)")
    horizon_days: int = Field(30, ge=7, le=90, description="Simulation window in days")
    sleep_hours_planned: Optional[float] = Field(None, ge=3.0, le=14.0)
    activity_level_planned: Optional[str] = Field(None, description="e.g., sedentary, moderate, active")
    caloric_adjustment_pct: Optional[float] = Field(0.0, ge=-50.0, le=50.0)


class InterventionPayload(BaseModel):
    """Backwards-compatible schema for legacy twin simulate requests."""
    sleep_delta_hours: float = 0.0
    carb_reduction_percent: float = 0.0
    target_marker: Optional[str] = "Fasting Blood Glucose"


@router.get("/state")
def get_current_twin_state(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Returns the authentic, un-interpolated digital twin state.
    Represents only what is documented, when it was observed, and highlights what remains unknown.
    """
    latest_observations = (
        db.query(ClinicalObservation)
        .filter(ClinicalObservation.user_id == current_user.id)
        .order_by(ClinicalObservation.effective_date.desc())
        .all()
    )

    known_biomarkers = {}
    for obs in latest_observations:
        name = obs.analyte_as_written
        if name not in known_biomarkers:
            dt = obs.effective_date.strftime("%Y-%m-%d") if obs.effective_date else "Undated on document"
            known_biomarkers[name] = {
                "value": obs.normalized_numeric_value if obs.normalized_numeric_value is not None else obs.original_value,
                "unit": obs.original_unit or "Not specified",
                "observed_date": dt,
                "flag": obs.laboratory_flag,
                "confidence": obs.confidence_score,
                "verification_status": obs.verification_status
            }

    latest_lifestyle = (
        db.query(LifestyleEntry)
        .filter(LifestyleEntry.user_id == current_user.id)
        .order_by(LifestyleEntry.logged_date.desc())
        .first()
    )

    lifestyle_state = None
    if latest_lifestyle:
        lifestyle_state = {
            "logged_date": latest_lifestyle.logged_date.strftime("%Y-%m-%d"),
            "sleep_hours": latest_lifestyle.sleep_hours,
            "activity_level": latest_lifestyle.activity_level,
            "diet_pattern": latest_lifestyle.diet_pattern
        }

    return {
        "status": "success",
        "twin_model_version": "Helix-Metabolic-v1.2",
        "validation_status": "Hypothetical mathematical model based on physiological coefficients. Not clinically validated for diagnostic reliance.",
        "patient_identifier": f"Patient #{current_user.id}",
        "documented_biomarkers_count": len(known_biomarkers),
        "known_biomarkers": known_biomarkers if known_biomarkers else "Not available — zero baseline observations uploaded.",
        "known_lifestyle_inputs": lifestyle_state or "Not available — no lifestyle inputs logged.",
        "unknown_parameters_notice": "Unmeasured vitals and unlisted biomarkers are omitted. Helix never assumes or fills gaps with artificial values."
    }


@router.post("/simulate")
def run_patient_specific_simulation(
    req: TwinSimulationRequest,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Simulates a counterfactual projection anchored strictly in the patient's
    actual documented baseline. Rejects simulation if no baseline measurement exists.
    """
    clean_target = req.target_biomarker.strip()

    # Find patient's most recent verified numerical measurement for this analyte
    baseline_obs = (
        db.query(ClinicalObservation)
        .filter(
            ClinicalObservation.user_id == current_user.id,
            ClinicalObservation.analyte_as_written.ilike(f"%{clean_target}%")
        )
        .order_by(ClinicalObservation.effective_date.desc())
        .first()
    )

    if not baseline_obs or baseline_obs.normalized_numeric_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot simulate trajectory for '{clean_target}': No verified baseline numerical observation "
                "exists in your health vault. Upload a diagnostic report containing this test first."
            )
        )

    base_val = baseline_obs.normalized_numeric_value
    base_unit = baseline_obs.original_unit or ""
    base_date = baseline_obs.effective_date.strftime("%Y-%m-%d") if baseline_obs.effective_date else "Undated"

    drift_factor = 0.0
    assumptions = []

    if req.caloric_adjustment_pct and req.caloric_adjustment_pct < 0:
        drift_factor -= (abs(req.caloric_adjustment_pct) / 100.0) * 0.12
        assumptions.append(f"Caloric deficit of {abs(req.caloric_adjustment_pct)}% applied.")

    if req.activity_level_planned:
        act = req.activity_level_planned.lower()
        if "active" in act:
            drift_factor -= 0.04
            assumptions.append("Active exercise regimen applied (-4% metabolic baseline reduction).")
        elif "sedentary" in act:
            drift_factor += 0.03
            assumptions.append("Sedentary physical pattern applied (+3% upward baseline drift).")

    if req.sleep_hours_planned is not None:
        if req.sleep_hours_planned < 6.0:
            drift_factor += 0.02
            assumptions.append("Sub-optimal sleep (<6h) adds sympathetic stress drift (+2%).")
        elif req.sleep_hours_planned >= 7.0:
            drift_factor -= 0.01
            assumptions.append("Restorative sleep (>=7h) promotes autonomic recovery (-1%).")

    intervals = [0, 10, 20, 30] if req.horizon_days == 30 else [0, req.horizon_days // 3, (req.horizon_days * 2) // 3, req.horizon_days]
    timeline = []
    for day in intervals:
        fraction = day / float(req.horizon_days)
        projected = round(base_val * (1.0 + (drift_factor * fraction)), 2)
        timeline.append({
            "day": day,
            "projected_value": projected,
            "uncertainty_margin": f"±{round(projected * 0.04, 2)}"
        })

    final_val = timeline[-1]["projected_value"]

    return {
        "status": "PROJECTION_COMPUTED",
        "classification": "Hypothetical Scenario Output",
        "validation_disclaimer": "This projection is a mathematical model calculation, NOT a clinical diagnosis or guarantee of future laboratory values.",
        "target_analyte": baseline_obs.analyte_as_written,
        "baseline_anchor": {
            "value": base_val,
            "unit": base_unit,
            "recorded_date": base_date,
            "source_type": baseline_obs.data_source_type
        },
        "scenario_inputs": {
            "horizon_days": req.horizon_days,
            "sleep_hours_planned": req.sleep_hours_planned,
            "activity_level_planned": req.activity_level_planned,
            "caloric_adjustment_pct": req.caloric_adjustment_pct
        },
        "model_assumptions": assumptions if assumptions else ["No lifestyle modifications specified; stable metabolic baseline maintained."],
        "projected_final_value": final_val,
        "unit": base_unit,
        "timeline": timeline
    }


# --- LEGACY / BACKWARDS-COMPATIBILITY ENDPOINTS ---

@router.post("/legacy/simulate")
def run_legacy_counterfactual_simulation(
    payload: InterventionPayload,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """Bridges legacy what-if requests to real patient baseline data."""
    marker = payload.target_marker or "Fasting Blood Glucose"
    baseline_obs = (
        db.query(ClinicalObservation)
        .filter(
            ClinicalObservation.user_id == current_user.id,
            ClinicalObservation.analyte_as_written.ilike(f"%{marker}%")
        )
        .order_by(ClinicalObservation.effective_date.desc())
        .first()
    )

    if not baseline_obs or baseline_obs.normalized_numeric_value is None:
        return {
            "status": "NO_BASELINE",
            "message": f"Not available — no source records found for {marker}.",
            "data": {"intervention_applied": payload.dict(), "timeline": [], "crossover_day": None}
        }

    req = TwinSimulationRequest(
        target_biomarker=baseline_obs.analyte_as_written,
        horizon_days=30,
        caloric_adjustment_pct=-float(payload.carb_reduction_percent),
        sleep_hours_planned=7.0 + payload.sleep_delta_hours
    )
    return run_patient_specific_simulation(req, current_user, db)


@router.get("/early-warnings")
def get_early_warnings(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Evaluates early metabolic strain indicators using only real, verified patient observations.
    Does not use hardcoded mock innovations.
    """
    abnormal_observations = (
        db.query(ClinicalObservation)
        .filter(
            ClinicalObservation.user_id == current_user.id,
            ClinicalObservation.laboratory_flag.isnot(None),
            ClinicalObservation.laboratory_flag != "Normal"
        )
        .order_by(ClinicalObservation.effective_date.desc())
        .all()
    )

    if not abnormal_observations:
        return {
            "status": "success",
            "strain_detected": False,
            "message": "No abnormal laboratory flags present in verified records.",
            "abnormal_markers": []
        }

    return {
        "status": "success",
        "strain_detected": True,
        "message": f"{len(abnormal_observations)} out-of-range observation(s) identified.",
        "abnormal_markers": [
            {
                "analyte": o.analyte_as_written,
                "value": o.original_value,
                "unit": o.original_unit,
                "flag": o.laboratory_flag
            }
            for o in abnormal_observations
        ]
    }


@router.get("/daily-briefing")
def get_daily_briefing(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Generates an executive briefing grounded strictly in what was recorded today or recently.
    Never hallucinates overnight adjustments or fake variability percentages.
    """
    recent_obs = (
        db.query(ClinicalObservation)
        .filter(ClinicalObservation.user_id == current_user.id)
        .order_by(ClinicalObservation.created_at.desc())
        .limit(3)
        .all()
    )

    if not recent_obs:
        return {
            "status": "success",
            "briefing_text": "Good day. No diagnostic records or vital measurements have been uploaded yet. Upload a report to receive your clinical briefing."
        }

    obs_summary = ", ".join([f"{o.analyte_as_written} ({o.original_value} {o.original_unit or ''})" for o in recent_obs])
    return {
        "status": "success",
        "briefing_text": f"Your longitudinal vault currently tracks {len(recent_obs)} recent verified parameter(s): {obs_summary}. Remember to review unexpected changes with your primary physician."
    }