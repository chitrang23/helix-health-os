from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from routes import ocr, clinical, twin, records, admin, auth

app = FastAPI(title="Helix Health OS")

if os.path.exists("public"):
    app.mount("/static", StaticFiles(directory="public"), name="public")

app.include_router(ocr.router, prefix="/api/ocr")
app.include_router(clinical.router, prefix="/api/clinical")
app.include_router(twin.router, prefix="/api/twin")
app.include_router(records.router, prefix="/api/records")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(auth.router, prefix="/api/auth")

@app.get("/")
async def serve_index():
    return FileResponse("public/dashboard.html")

@app.get("/{filename}")
async def serve_page(filename: str):
    clean_name = filename.split("?")[0].lower()
    if not clean_name.endswith(".html"):
        clean_name += ".html"
    file_path = os.path.join("public", clean_name)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return FileResponse("public/dashboard.html")
