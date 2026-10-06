from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from services.stress_service import analyze_user_stress
from models.orm import StressLog

router = APIRouter()

class StressCheckInRequest(BaseModel):
    user_id: int = 1
    stress_score: int  # 1 to 10
    triggers: str = "General"

@router.get("/")
async def get_stress_metrics():
    """Returns general cognitive load and stress management metrics."""
    return {
        "cognitive_load": "Optimal",
        "focus_intervals_today": 6,
        "recommended_break_in_minutes": 25,
        "stress_trend": "Decreasing by 12% week-over-week based on activity pacing."
    }

@router.post("/check-in")
async def stress_check_in(req: StressCheckInRequest, db: Session = Depends(get_db)):
    """Logs stress metrics, runs AI behavioral analysis via Gemini, and saves to database."""
    if not (1 <= req.stress_score <= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Stress score must be between 1 and 10."
        )
    
    result = analyze_user_stress(db, req.user_id, req.stress_score, req.triggers)
    return result

@router.get("/history/{user_id}")
async def get_stress_history(user_id: int, db: Session = Depends(get_db)):
    """Retrieves longitudinal stress tracking records for a specific user."""
    logs = db.query(StressLog).filter(StressLog.user_id == user_id).order_by(StressLog.logged_at.desc()).limit(10).all()
    return {"user_id": user_id, "history": logs}