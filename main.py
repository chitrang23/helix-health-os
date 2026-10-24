import glob
import os
import time
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import (
    verify_password,
    create_access_token,
    get_current_authenticated_user
)
from models.orm import User
from services.observability import MetricsCollector

# Import all modular routers from routes/
from routes import (
    auth, 
    chat, 
    clinical, 
    dashboard_page, 
    drug_safety, 
    export, 
    ocr, 
    pathology, 
    records, 
    soap, 
    stress, 
    trajectory, 
    translator, 
    twin
)

try:
    from routes import metrics
    has_metrics_route = True
except ImportError:
    has_metrics_route = False

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Source-grounded healthcare intelligence platform with zero hardcoded medical values.",
    version="1.0.0"
)

# 1. Strict Credentials-Safe CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# 2. Telemetry and Security Headers Middleware
@app.middleware("http")
async def security_and_observability_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    MetricsCollector.record_request(response.status_code, duration)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# 3. Startup Tasks: Clean Temporary Processing Buffers
@app.on_event("startup")
def startup_tasks():
    for temp_file in glob.glob("temp_page_*.png"):
        try:
            os.remove(temp_file)
        except Exception:
            pass
    os.makedirs("temp_uploads", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)

# 4. Mount Static Frontend Files
app.mount("/public", StaticFiles(directory="public"), name="public")
app.mount("/static", StaticFiles(directory="public"), name="static")

# 5. Register All Modular Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI Assistant Chat"])
app.include_router(clinical.router, prefix="/api/clinical", tags=["Clinical Analysis"])
app.include_router(dashboard_page.router, prefix="", tags=["Frontend Pages"])
app.include_router(drug_safety.router, prefix="/api/drug-safety", tags=["Drug Safety & Interactions"])
app.include_router(export.router, prefix="/api/export", tags=["FHIR & Data Export"])
app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR Medical Document Processing"])
app.include_router(pathology.router, prefix="/api/pathology", tags=["Pathology Reports"])
app.include_router(records.router, prefix="/api/records", tags=["Medical Records Vault"])
app.include_router(soap.router, prefix="/api/soap", tags=["SOAP Note Generation"])
app.include_router(stress.router, prefix="/api/stress", tags=["Stress & Mental Health Tracking"])
app.include_router(trajectory.router, prefix="/api/trajectory", tags=["Health Trajectory Analysis"])
app.include_router(translator.router, prefix="/api/translator", tags=["Global Medical Translator"])
app.include_router(twin.router, prefix="/api/twin", tags=["Metabolic Twin Simulation"])

if has_metrics_route:
    app.include_router(metrics.router, prefix="/api/metrics", tags=["Health Metrics"])


# 6. Database-Grounded Root Auth Endpoints (Prevents 404s when frontend posts to /token or /login directly)
class RootLoginPayload(BaseModel):
    email: EmailStr
    password: str

@app.post("/token", tags=["Authentication Alias"])
async def root_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Standard OAuth2 password token endpoint.
    Authenticates strictly against database records (checks email or username).
    """
    identifier = form_data.username.strip().lower()
    user = db.query(User).filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }
    }

@app.post("/login", tags=["Authentication Alias"])
async def root_login(
    payload: RootLoginPayload,
    db: Session = Depends(get_db)
):
    """
    JSON login endpoint for web frontend compatibility.
    """
    clean_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }
    }


# 7. Safe Non-Fabricating Translation Proxy
@app.post("/api/translate/object", tags=["Translation Proxy"])
async def translate_object_proxy(data: dict):
    return {"translated_data": data}

# 8. Secure Telemetry
@app.get("/api/system/metrics", tags=["Observability"])
def get_system_metrics(
    current_user: User = Depends(get_current_authenticated_user)
):
    """Returns real-time request telemetry and operational status for authenticated users."""
    return MetricsCollector.get_summary()

@app.get("/", tags=["Root"])
def read_root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "documentation": "/docs",
        "frontend_entry": "/public/index.html"
    }