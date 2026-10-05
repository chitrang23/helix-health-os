import os

print("Upgrading Helix backend to 100% dynamic AI-powered modules...")

# 1. Update OCR & Document Intelligence Pipeline to use real Gemini Vision/Text
ocr_pipeline_path = "services/ocr_pipeline.py"
ocr_code = '''import os
import google.generativeai as genai
from core.config import GEMINI_API_KEY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class DynamicOCREngine:
    @staticmethod
    def extract_medical_report(file_bytes: bytes, mime_type: str = "application/pdf") -> dict:
        if not GEMINI_API_KEY:
            return {"error": "Gemini API key not configured.", "fallback": True}
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = \"\"\"
            You are an elite clinical data extraction system. Analyze this medical report/lab document.
            Extract and return ONLY a valid JSON structure with the following keys:
            - patient_name: string or null
            - age: integer or null
            - gender: string or null
            - report_date: string (YYYY-MM-DD) or null
            - hospital_or_lab: string or null
            - lab_results: dictionary of test names mapped to numeric values (e.g., {"glucose": 140, "creatinine": 1.1})
            - medications: list of strings found
            - summary: brief clinical overview
            \"\"\"
            response = model.generate_content([
                prompt,
                {"mime_type": mime_type, "data": file_bytes}
            ])
            import json
            text = response.text.strip()
            if text.startswith("`json"):
                text = text[7:-3].strip()
            return json.loads(text)
        except Exception as e:
            return {"error": str(e), "raw_text": getattr(response, 'text', '') if 'response' in locals() else ""}
'''
with open(ocr_pipeline_path, "w", encoding="utf-8") as f:
    f.write(ocr_code)
print("Updated services/ocr_pipeline.py with dynamic Gemini OCR extraction")

# 2. Update Lifestyle & Stress Management Engine to use Gemini AI dynamically
lifestyle_path = "services/lifestyle_engine.py"
lifestyle_code = '''import os
import google.generativeai as genai
from core.config import GEMINI_API_KEY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class DynamicLifestyleEngine:
    @staticmethod
    def generate_recommendations(health_profile: dict) -> dict:
        if not GEMINI_API_KEY:
            return {
                "habuild_yoga_integration": {"program_name": "Habuild Core Yoga", "frequency": "Daily 30 mins", "recommended_sessions": ["Surya Namaskar", "Pranayama"]},
                "diet": "Balanced Mediterranean diet",
                "stress_management": "Mindfulness & 4-7-8 breathing technique"
            }
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f\"\"\"
            As an expert clinical lifestyle and yoga physician (partnered with Habuild), generate personalized lifestyle recommendations based on this patient profile: {health_profile}.
            Return ONLY a valid JSON with keys:
            - habuild_yoga_integration: {{ "program_name": string, "frequency": string, "recommended_sessions": [list of specific yoga postures/sessions] }}
            - diet: string description
            - stress_management: string decoupled stress relief protocol
            \"\"\"
            response = model.generate_content(prompt)
            import json
            text = response.text.strip()
            if text.startswith("`json"):
                text = text[7:-3].strip()
            return json.loads(text)
        except Exception as e:
            return {"error": str(e), "habuild_yoga_integration": {"program_name": "Habuild Baseline", "frequency": "Daily", "recommended_sessions": ["Deep Breathing"]}}
'''
with open(lifestyle_path, "w", encoding="utf-8") as f:
    f.write(lifestyle_code)
print("Updated services/lifestyle_engine.py with dynamic Gemini lifestyle & yoga generation")

print("All engines successfully upgraded to dynamic Gemini-powered execution!")
