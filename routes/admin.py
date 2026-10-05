from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_admin_status():
    return {"status": "active", "module": "admin"}