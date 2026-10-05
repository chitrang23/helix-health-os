from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_trajectory():
    return {
        "status": "active",
        "prediction_window": "90 Days",
        "metabolic_twin_simulation": {
            "current_hba1c": 5.7,
            "projected_hba1c_90_days": 5.4,
            "velocity": "-0.03 per month",
            "confidence_score": 94.2,
            "recommendations": [
                "Maintain current aerobic routine (45 mins/day)",
                "Keep fasting glucose tracking active"
            ]
        }
    }
