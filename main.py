from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone
import logging

from routes import auth, records, clinical

app = FastAPI(
    title="Helix Health OS",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="public"), name="static")

# Mount All Routers
app.include_router(auth.router)
app.include_router(records.router)
app.include_router(clinical.router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled Error on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An internal health OS processing error occurred.",
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

# Page Routes
@app.get("/")
async def serve_login():
    return FileResponse("public/index.html")

@app.get("/register")
async def serve_register():
    return FileResponse("public/register.html")

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse("public/dashboard.html")
