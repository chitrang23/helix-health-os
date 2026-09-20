from fastapi import APIRouter

router = APIRouter(tags=["Export"])

@router.get("/export/health")
async def export_health():
    return {"status": "export active"}
