from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter(prefix="", tags=["Frontend"])

@router.get("/dashboard.html")
async def serve_dashboard():
    return FileResponse("public/dashboard.html")

@router.get("/")
async def serve_index():
    return FileResponse("public/index.html")