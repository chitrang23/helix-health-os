import os
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from routes import ocr, chat, dashboard_page, drug_safety, clinical, trajectory, twin, soap, stress, export

app = FastAPI(title="Helix Health OS", version="2.0.0")

# Mount your public static files folder
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/")
@app.get("/dashboard.html")
async def serve_dashboard():
    # Points directly to your original public/dashboard.html file
    file_path = os.path.join(os.path.dirname(__file__), "public", "dashboard.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("<h1>dashboard.html not found in public/ directory.</h1>", status_code=404)

# Register modular backend routers
app.include_router(ocr.router)
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
# Register modular backend routers
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR"])
app.include_router(dashboard_page.router)
app.include_router(drug_safety.router)
app.include_router(clinical.router)
app.include_router(trajectory.router)
app.include_router(twin.router)
app.include_router(soap.router)
app.include_router(stress.router)
app.include_router(export.router)