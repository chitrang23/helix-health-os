import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

# Mounted in main.py with prefix=""
router = APIRouter(tags=["Frontend Pages"])


@router.get("/")
@router.get("/index.html")
async def serve_index():
    return FileResponse("public/index.html")


@router.get("/login")
@router.get("/login.html")
async def serve_login():
    return FileResponse("public/index.html")


@router.get("/register")
@router.get("/register.html")
async def serve_register():
    return FileResponse("public/register.html")


@router.get("/dashboard")
@router.get("/dashboard.html")
async def serve_dashboard():
    return FileResponse("public/dashboard.html")


@router.get("/history")
@router.get("/history.html")
@router.get("/medical-history")
@router.get("/medical-history.html")
async def serve_history():
    if os.path.exists("public/history.html"):
        return FileResponse("public/history.html")
    elif os.path.exists("public/medical-history.html"):
        return FileResponse("public/medical-history.html")
    return FileResponse("public/dashboard.html")