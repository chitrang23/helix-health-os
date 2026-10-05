import os

print("Starting Helix Health OS Production Upgrade...")

config_path = "core/config.py"
if os.path.exists(config_path):
    with open(config_path, "r") as f:
        content = f.read()
    if "MAX_UPLOAD_SIZE" not in content:
        content += "\nMAX_UPLOAD_SIZE_MB = 100\n"
    with open(config_path, "w") as f:
        f.write(content)
    print(f"Updated {config_path}")

ocr_pipeline_path = "services/ocr_pipeline.py"
if os.path.exists(ocr_pipeline_path):
    with open(ocr_pipeline_path, "r") as f:
        ocr_code = f.read()
    dynamic_parser_patch = '''
import re
from datetime import datetime

def extract_report_metadata(text: str):
    hospital_name = "Associated Medical Center"
    hospital_match = re.search(r"(?:Hospital|Clinic|Medical Center|Lab|Diagnostics)[:\\\\s]+([A-Za-z\\\\s]+)", text, re.IGNORECASE)
    if hospital_match:
        hospital_name = hospital_match.group(1).strip()
        
    report_date = datetime.utcnow().date().isoformat()
    date_match = re.search(r"(\\\\d{2}[-/]\\\\d{2}[-/]\\\\d{4}|\\\\d{4}[-/]\\\\d{2}[-/]\\\\d{2})", text)
    if date_match:
        try:
            raw_date = date_match.group(1)
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    report_date = datetime.strptime(raw_date, fmt).date().isoformat()
                    break
                except ValueError:
                    continue
        except Exception:
            pass
            
    return {"hospital_name": hospital_name, "report_date": report_date}
'''
    if "extract_report_metadata" not in ocr_code:
        ocr_code += "\n" + dynamic_parser_patch
        with open(ocr_pipeline_path, "w") as f:
            f.write(ocr_code)
        print("Patched OCR Pipeline for dynamic hospital and date extraction.")

lifestyle_path = "services/lifestyle_engine.py"
lifestyle_content = '''# Habuild & Clinical Lifestyle Engine inspired by Habuild (https://habuild.in/)
class LifestyleEngine:
    @staticmethod
    def get_recommendations(condition: str, user_profile: dict):
        base_plan = {
            "diet": "Balanced whole-food diet rich in fiber, low glycemic index, adequate hydration.",
            "exercise": "Moderate aerobic activity (30 mins/day) combined with breathwork.",
            "habuild_yoga_integration": {
                "program_name": "Habuild Live & Virtual Yoga Sessions",
                "reference_url": "https://habuild.in/",
                "recommended_sessions": ["Surya Namaskar (gentle flow)", "Pranayama & Breath Regulation", "Joint Mobility Routines"],
                "frequency": "Daily 6:30 AM or Live Evening Sessions"
            }
        }
        if "diabetes" in condition.lower() or "sugar" in condition.lower():
            base_plan["diet"] = "Low carbohydrate, high protein, diabetic-friendly fiber rich meals."
            base_plan["habuild_yoga_integration"]["recommended_sessions"].append("Mandukasana & Pranayama for Glycemic Control")
        elif "hypertension" in condition.lower() or "cardio" in condition.lower():
            base_plan["diet"] = "DASH diet, low sodium, potassium-rich foods."
            base_plan["habuild_yoga_integration"]["recommended_sessions"].append("Shavasana & Meditation for Blood Pressure Management")
        return base_plan
'''
with open(lifestyle_path, "w") as f:
    f.write(lifestyle_content)
print(f"Created/Updated {lifestyle_path}")

doctor_matcher_path = "services/doctor_matcher.py"
doctor_matcher_content = '''# Regional Disease-Specific Doctor Recommendation Engine
class DoctorMatcher:
    REGIONAL_SPECIALISTS = {
        "mumbai": {
            "cardiology": [{"name": "Dr. Ajit Menon", "hospital": "Lilavati Hospital, Bandra", "contact": "+91-22-26751000"}, {"name": "Dr. P. Rafiyath", "hospital": "Asian Heart Institute, BKC", "contact": "+91-22-66986666"}],
            "diabetology": [{"name": "Dr. Shashank Joshi", "hospital": "Lilavati & Joshi Clinic, Khar", "contact": "+91-22-26469999"}],
            "neurology": [{"name": "Dr. Uday Andar", "hospital": "Breach Candy Hospital", "contact": "+91-22-23672889"}],
            "general": [{"name": "Dr. Rahul Khurana", "hospital": "Global Hospitals, Parel", "contact": "+91-22-67670101"}]
        },
        "default": {
            "cardiology": [{"name": "Senior Consultant Cardiologist", "hospital": "Apex Metro Heart Institute", "contact": "1800-HEART-CLINIC"}],
            "diabetology": [{"name": "Endocrinology & Metabolic Specialist", "hospital": "Metabolic Care Center", "contact": "1800-SUGAR-CARE"}],
            "general": [{"name": "Internal Medicine Lead", "hospital": "City General Hospital", "contact": "1800-GENERAL"}]
        }
    }

    @classmethod
    def recommend_doctor(cls, specialty: str, region: str = "mumbai"):
        reg = region.lower() if region.lower() in cls.REGIONAL_SPECIALISTS else "default"
        spec = specialty.lower()
        specialist_pool = cls.REGIONAL_SPECIALISTS[reg]
        for key in specialist_pool:
            if key in spec:
                return specialist_pool[key]
        return specialist_pool.get("general", [{"name": "Dr. General Practitioner", "hospital": "Primary Health Clinic"}])
'''
with open(doctor_matcher_path, "w") as f:
    f.write(doctor_matcher_content)
print(f"Created {doctor_matcher_path}")

print("Helix Health OS Production upgrade successfully applied!")
