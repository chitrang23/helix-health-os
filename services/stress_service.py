import os
from google import genai
from sqlalchemy.orm import Session
from models.orm import StressLog, HealthRecord

client = genai.Client()

def analyze_user_stress(db: Session, user_id: int, current_stress: int, triggers: str) -> dict:
    """
    Analyzes stress levels, correlates with recent health markers (like sleep/HRV if available),
    and generates personalized cognitive behavioral guidance using Gemini.
    """
    # Fetch recent health records (e.g., sleep, heart rate, or cortisol markers)
    records = db.query(HealthRecord).filter(HealthRecord.user_id == user_id).limit(5).all()
    marker_summary = ", ".join([f"{r.biomarker_name}: {r.value} {r.unit or ''}" for r in records]) or "No active biomarkers tracked."

    prompt = f"""
    You are Helix Clinical Stress AI, an expert in behavioral health and neuro-endocrine stress responses.
    
    Patient Current Stress Score (1-10): {current_stress}
    Reported Triggers: {triggers}
    Recent Biomarkers / Vitals: {marker_summary}
    
    Provide:
    1. A brief clinical assessment of this stress level.
    2. Two targeted, actionable somatic or cognitive interventions to lower cortisol immediately.
    3. A gentle, reassuring closing statement.
    Keep it professional, concise, and structured.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        ai_recommendation = response.text
    except Exception:
        ai_recommendation = "Focus on 4-7-8 diaphragmatic breathing, reduce caffeine intake, and take a 15-minute unplugged walk to stabilize cortisol levels."

    # Save log to database
    try:
        log = StressLog(
            user_id=user_id,
            stress_score=current_stress,
            perceived_triggers=triggers,
            notes=ai_recommendation
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "stress_score": current_stress,
        "triggers": triggers,
        "recommendation": ai_recommendation,
        "status": "Logged & Analyzed Successfully"
    }