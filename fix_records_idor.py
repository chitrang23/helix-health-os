import os

records_code = '''from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from routes.auth import users_db

router = APIRouter(tags=["Records"])

def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.split("Bearer ")[1]
    
    for email, user in users_db.items():
        if user.get("token") == token:
            return user["user_id"]
            
    raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/records/{patient_id}/history")
@router.get("/v1/records/{patient_id}/history")
async def get_patient_history(
    patient_id: int, 
    current_user_id: int = Depends(get_current_user_id)
):
    if current_user_id != patient_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access other patient records")
        
    return {
        "patient_id": patient_id,
        "history": [
            {"date": "2026-01-15", "type": "Blood Test", "status": "Completed"}
        ]
    }
'''

with open(os.path.join("routes", "records.py"), "w", encoding="utf-8") as f:
    f.write(records_code)

print("✅ Updated routes/records.py with IDOR authorization checks.")
