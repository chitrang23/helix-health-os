from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Digital Twin"])

class TwinSimulationInput(BaseModel):
    horizon_days: int
    daily_steps: int
    carb_reduction_pct: float
    weekly_cardio_mins: int

@router.post("/twin/{user_id}/simulate")
@router.post("/v1/twin/{user_id}/simulate")
async def simulate_twin(user_id: int, data: TwinSimulationInput, authorization: Optional[str] = Header(None)):
    baseline_glucose = 115.0
    reduction = (data.carb_reduction_pct / 100.0) * 10.0 + (data.daily_steps / 10000.0) * 5.0
    projected_final = max(80.0, baseline_glucose - reduction)
    
    return {
        "status": "success",
        "user_id": user_id,
        "horizon_days": data.horizon_days,
        "projections": {
            "fasting_glucose": {
                "baseline": baseline_glucose,
                "projected_final": projected_final,
                "unit": "mg/dL"
            },
            "hba1c": {
                "baseline": 5.8,
                "projected_final": 5.4,
                "unit": "%"
            }
        }
    }
