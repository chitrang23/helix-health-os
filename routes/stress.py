from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, StressLog
from services.stress_service import analyze_user_stress

# In main.py, this router is mounted with prefix="/api/stress"
router = APIRouter(tags=["Stress Management & Neuro-Somatic Regulation"])


class StressCheckInRequest(BaseModel):
    stress_score: int = Field(..., ge=1, le=10, description="Self-reported stress level on a 1-10 scale")
    triggers: Optional[str] = Field("General", description="Self-reported triggers (e.g., workload, sleep deficit, health worries)")
    somatic_notes: Optional[str] = Field(None, description="Optional physical symptoms (e.g., muscle tension, headache)")
    user_id: Optional[int] = Field(None, description="Deprecated parameter; authenticated identity is enforced server-side")


@router.get("/")
def get_stress_overview(
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Returns authentic cognitive and somatic stress metrics based strictly
    on the authenticated user's logged check-ins. Zero synthetic trend lines.
    """
    recent_logs = (
        db.query(StressLog)
        .filter(StressLog.user_id == current_user.id)
        .order_by(StressLog.logged_at.desc())
        .limit(14)
        .all()
    )

    if not recent_logs:
        return {
            "status": "NO_DATA",
            "message": "Not available — no stress check-ins recorded yet.",
            "total_logged_entries": 0,
            "weekly_average_score": None,
            "trend_analysis": "Log your first stress check-in to begin tracking longitudinal stress patterns.",
            "evidence_based_exercise": {
                "name": "Box Breathing (Autonomic Reset)",
                "technique": "4s Inhale -> 4s Hold -> 4s Exhale -> 4s Hold",
                "evidence_source": "Balban et al., Cell Reports Medicine (2023) - Brief structured respiration lowers physiological arousal."
            }
        }

    scores = [l.stress_score for l in recent_logs]
    avg_score = round(sum(scores) / len(scores), 1)

    # Compute genuine trend if at least 2 check-ins exist
    trend_description = "Baseline established. Continue logging to compute longitudinal trend."
    if len(scores) >= 2:
        earlier_score = scores[-1]
        latest_score = scores[0]
        delta = latest_score - earlier_score
        if delta < 0:
            trend_description = f"Decreasing by {abs(delta)} point(s) compared to initial recorded entry."
        elif delta > 0:
            trend_description = f"Elevated by {delta} point(s) compared to initial recorded entry."
        else:
            trend_description = "Stable across recorded check-ins."

    latest = recent_logs[0]
    return {
        "status": "ACTIVE",
        "total_logged_entries": len(recent_logs),
        "latest_score": latest.stress_score,
        "latest_logged_date": latest.logged_at.strftime("%Y-%m-%d %H:%M UTC"),
        "average_score": avg_score,
        "trend_analysis": trend_description,
        "evidence_based_exercise": {
            "name": "4-4-4-4 Box Breathing or Physiological Sigh",
            "technique": "Two quick inhales through the nose followed by a slow, complete mouth exhale.",
            "clinical_note": "Helps re-engage parasympathetic vagal tone during periods of acute sympathetic activation."
        }
    }


@router.post("/check-in")
def log_stress_check_in(
    req: StressCheckInRequest,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Logs an authentic self-reported stress score and generates tailored somatic guidance.
    If extreme distress (score 9-10) is logged, urgent clinical support guidance is provided.
    """
    result = analyze_user_stress(
        db=db,
        user_id=current_user.id,
        current_stress=req.stress_score,
        triggers=req.triggers or "General"
    )

    urgent_guidance = None
    if req.stress_score >= 9:
        urgent_guidance = (
            "You have recorded a very high stress level. If you are experiencing overwhelming distress, "
            "chest tightness, panic, or thoughts of self-harm, please reach out to trusted clinical care or local emergency services immediately "
            "(National Tele-MANAS Mental Health Helpline: 14416 / 1800-891-4416, or your local emergency line)."
        )

    return {
        "status": "SUCCESS",
        "logged_at": datetime.utcnow().isoformat(),
        "stress_score": req.stress_score,
        "triggers": req.triggers,
        "personalized_recommendation": result.get("recommendation"),
        "urgent_support_guidance": urgent_guidance
    }


@router.get("/history")
@router.get("/history/{user_id}")
def get_user_stress_history(
    user_id: Optional[int] = None,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Returns authentic stress entries scoped strictly to the authenticated caller.
    Prevents cross-patient leakage (IDOR).
    """
    # Enforce that a user cannot query another user's history
    target_user_id = current_user.id
    if user_id is not None and user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Cannot access stress history belonging to another patient."
        )

    logs = (
        db.query(StressLog)
        .filter(StressLog.user_id == target_user_id)
        .order_by(StressLog.logged_at.desc())
        .limit(20)
        .all()
    )

    return {
        "user_id": target_user_id,
        "total_entries": len(logs),
        "history": [
            {
                "id": l.id,
                "score": l.stress_score,
                "triggers": l.perceived_triggers,
                "notes": l.notes,
                "date": l.logged_at.strftime("%Y-%m-%d %H:%M UTC")
            }
            for l in logs
        ]
    }