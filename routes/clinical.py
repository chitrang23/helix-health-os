from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from google import genai
from google.genai import types

# Prefix is handled centrally in main.py to prevent double-prefixing (404 errors)
router = APIRouter(tags=["Clinical Intelligence"])

@router.get("/safety-page")
async def serve_safety_page():
    return FileResponse("public/safety.html")

@router.get("/chat-page")
async def serve_chat_page():
    return FileResponse("public/chat.html")

@router.get("/prediction-page")
async def serve_prediction_page():
    return FileResponse("public/prediction.html")

@router.get("/stress-page")
async def serve_stress_page():
    return FileResponse("public/stress.html")

class PredictionRequest(BaseModel):
    marker: str
    baseline: float
    sleep: str
    activity: str
    diet: str

class StressRequest(BaseModel):
    thought: str

class SymptomCorrelationRequest(BaseModel):
    symptoms: List[str]
    biomarkers: dict
    active_prescriptions: List[str]
    user_location: str = "Navi Mumbai, Maharashtra"

class SafetyAuditRequest(BaseModel):
    medications: List[str]
    supplements: List[str]

class ChatRequest(BaseModel):
    message: str
    user_context: dict

@router.post("/reframe-stress")
async def reframe_stress(req: StressRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "reframed": "Acknowledge that this challenge is temporary. Focus on what you can control right now, take three slow diaphragmatic breaths, and break your next step into a single manageable task."
        }

    client = genai.Client(api_key=api_key)
    prompt = """You are an expert clinical psychologist and mindfulness coach.
A patient is experiencing this stressor: '""" + req.thought + """'

Provide a concise, highly reassuring, scientifically grounded cognitive reframing (2-3 sentences) that reduces cortisol, validates their feelings, and offers an actionable perspective.
Return JSON format:
{
  "reframed": "Your calm psychological reframing here."
}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )

    return json.loads(response.text)

@router.post("/predict-30-days")
async def predict_health_trajectory(req: PredictionRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        projected = round(req.baseline * 1.03, 2)
        return {
            "projected_day_30": projected,
            "status": "IMPROVING",
            "explanation": f"Based on your habits ({req.sleep}, {req.activity}), your {req.marker} is projected to stabilize positively over the next 30 days.",
            "recommendation": f"Maintain your {req.diet} and ensure consistent hydration."
        }

    client = genai.Client(api_key=api_key)
    prompt = f"""You are an advanced medical predictive simulation engine.
Analyze:
- Target Biomarker: {req.marker}
- Baseline Value: {req.baseline}
- Daily Sleep: {req.sleep}
- Physical Activity: {req.activity}
- Diet Quality: {req.diet}

Provide JSON output format:
{{
  "projected_day_30": 14.2,
  "status": "OPTIMIZED / IMPROVING / STABLE / AT RISK",
  "explanation": "Detailed physiological explanation of how these lifestyle factors influence this biomarker over 30 days.",
  "recommendation": "Specific, actionable habit adjustment for the next 30 days."
}}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )

    return json.loads(response.text)

@router.post("/correlate-symptoms")
async def correlate_symptoms_and_refer(req: SymptomCorrelationRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    prompt = f"""You are an enterprise clinical decision support system.
Analyze:
- Reported Patient Symptoms: {req.symptoms}
- Lab Biomarkers Extracted: {json.dumps(req.biomarkers)}
- Doctor Prescriptions: {req.active_prescriptions}
- Location: {req.user_location}

Provide output in JSON format:
{{
  "correlated_condition": "Possible clinical correlation",
  "clinical_explanation": "Detailed physiological explanation linking symptoms with lab results",
  "lifestyle_plan": {{
     "dietary_adjustments": "Specific foods aligned with prescribed meds",
     "yoga_habit_building": "Recommended morning yoga routines. Mention Habuild (https://habuild.in/) for virtual sessions.",
     "precautions": "Important medical precautions"
  }},
  "specialist_referral": {{
     "specialty_needed": "e.g. Hematologist / Gastroenterologist",
     "reason": "Why this specialist is needed based on abnormal values",
     "recommended_search_query": "Top rated [specialty] in [location]"
  }}
}}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )

    return json.loads(response.text)

@router.post("/safety-check")
async def audit_drug_safety(req: SafetyAuditRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    prompt = f"""Analyze potential drug-drug or drug-supplement interactions for:
Active Prescriptions: {req.medications}
Daily Supplements: {req.supplements}

Return JSON format:
{{
  "interactions_found": true/false,
  "severity": "CRITICAL / MAJOR / NONE",
  "findings": [
    {{
       "combination": "Drug A + Supplement B",
       "clinical_effect": "Description of risk",
       "recommendation": "Actionable advice"
    }}
  ]
}}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )

    return json.loads(response.text)

@router.post("/assistant-chat")
async def clinical_assistant_chat(req: ChatRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    system_instruction = """You are Helix Health OS Clinical Assistant.
Follow these strict guidelines:
1. Base health advice on trusted global guidelines (WHO, CDC).
2. Provide empathetic, easy-to-understand explanations.
3. MANDATORY DISCLAIMER AT END: 'Disclaimer: Helix Health OS is your clinical companion and does not replace professional medical diagnosis.'"""

    prompt = f"""Patient Context: {json.dumps(req.user_context)}
Patient Question: {req.message}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system_instruction)
    )

    return {"reply": response.text}