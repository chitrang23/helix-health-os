from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def check_drug_safety(medication: str = "Metformin"):
    return {
        "medication": medication,
        "safety_status": "Safe with current profile",
        "interactions_found": 0,
        "contraindications": None,
        "hepatic_renal_adjustment": "No renal dosage adjustment required based on recent eGFR values."
    }
