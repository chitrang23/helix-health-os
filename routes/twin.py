from fastapi import APIRouter
from pydantic import BaseModel
from services.metabolic_twin import simulate_counterfactual
from services.metabolic_twin.kalman_engine import detect_early_strain

router = APIRouter()

class InterventionPayload(BaseModel):
    sleep_delta_hours: float = 0.0
    carb_reduction_percent: float = 0.0

@router.post("/api/twin/simulate")
def run_counterfactual_simulation(payload: InterventionPayload):
    """Feature 1: What-If Counterfactual Time-Travel Simulator"""
    base_state = {"latest_marker": 95.5}
    result = simulate_counterfactual(base_state, payload.dict())
    return {"status": "success", "data": result}

@router.get("/api/twin/early-warnings")
def get_early_warnings():
    """Feature 2: Predictive Pre-Symptom Early Warning Alarms"""
    mock_innovations = [0.1, 0.4, 2.8]
    warning = detect_early_strain(mock_innovations)
    return {"status": "success", "warning": warning}

@router.get("/api/assistant/daily-briefing")
def get_daily_briefing():
    """Feature 3: Voice-Activated / Text Bio-Contextual Executive Briefing"""
    return {
        "status": "success",
        "briefing_text": "Good morning. Your metabolic twin adjusted overnight - your glucose variability improved by 4% following yesterday's adjustment, but your recovery score dipped slightly. Focus on low-strain activities today."
    }