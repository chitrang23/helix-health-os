import os

routes_clinical_path = "routes/clinical.py"
if os.path.exists(routes_clinical_path):
    with open(routes_clinical_path, "r") as f:
        content = f.read()
    
    # Inject lifestyle and doctor recommendation endpoints if not present
    new_endpoints = '''
from services.lifestyle_engine import LifestyleEngine
from services.doctor_matcher import DoctorMatcher

@router.get("/api/lifestyle/recommendations")
async def get_lifestyle_recommendations(condition: str = "general", user_id: int = 1):
    return LifestyleEngine.get_recommendations(condition, {"user_id": user_id})

@router.get("/api/doctors/recommend")
async def recommend_doctors(specialty: str = "general", region: str = "mumbai"):
    return DoctorMatcher.recommend_doctor(specialty, region)
'''
    if "api/lifestyle/recommendations" not in content:
        content += "\n" + new_endpoints
        with open(routes_clinical_path, "w") as f:
            f.write(content)
        print("Successfully wired Lifestyle and Doctor Matching endpoints into routes/clinical.py")
