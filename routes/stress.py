from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_stress_metrics():
    return {
        "cognitive_load": "Optimal",
        "focus_intervals_today": 6,
        "recommended_break_in_minutes": 25,
        "stress_trend": "Decreasing by 12% week-over-week based on activity pacing."
    }
