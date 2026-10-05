from fastapi import APIRouter

router = APIRouter()

@router.get("/notes")
async def generate_soap_notes():
    return {
        "subjective": "Patient reports high adherence to daily aerobic routine, stable energy levels, and zero acute complaints.",
        "objective": "Latest parsed laboratory upload indicates HbA1c improved to 5.7%, Blood Pressure stabilized at 120/80 mmHg.",
        "assessment": "Positive response to lifestyle modifications over the 90-day trajectory window.",
        "plan": "Continue current maintenance protocol; follow up with specialist in 3 months with refreshed lab panels."
    }

@router.get("/recommend-doctor")
async def recommend_doctor(specialty: str = "Endocrinology", location: str = "Navi Mumbai"):
    return {
        "specialty": specialty,
        "location": location,
        "recommendations": [
            {"name": "Dr. Rajesh Sharma, MD", "hospital": "Apollo Hospitals", "contact": "+91 22 3355 1000"},
            {"name": "Dr. Sneha Kulkarni, MS", "hospital": "Kokilaben Dhirubhai Ambani Hospital", "contact": "+91 22 4269 9999"}
        ]
    }
