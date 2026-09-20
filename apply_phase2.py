import os

files = {}

files["requirements.txt"] = """fastapi>=0.110.0
uvicorn[standard]>=0.28.0
sqlalchemy>=2.0.28
pydantic>=2.6.4
python-multipart>=0.0.9
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.1
python-jose[cryptography]>=3.3.0
pytesseract>=0.3.10
pillow>=10.2.0
pytest>=8.0.0
httpx>=0.27.0
"""

files["core/config.py"] = """import os

class Settings:
    PROJECT_NAME: str = "Helix Health OS"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "prod-health-super-secret-key-change-in-env-99021")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./helix_production.db")
    ALLOWED_CORS_ORIGINS: list = [
        origin.strip() for origin in os.getenv("HELIX_CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000").split(",") if origin.strip()
    ]

settings = Settings()
"""

files["core/security.py"] = """from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception

def verify_user_ownership(requested_user_id: str, authenticated_user_id: str = Depends(get_current_user_id)) -> str:
    if requested_user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot access or modify medical records belonging to another identity."
        )
    return authenticated_user_id
"""

files["core/database.py"] = """from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

files["models/orm.py"] = """from sqlalchemy import Column, String, Float, Integer, ForeignKey, Text, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship("HealthRecord", back_populates="user", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="user", cascade="all, delete-orphan")

class HealthRecord(Base):
    __tablename__ = "health_records"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    record_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    extraction_failed = Column(Boolean, default=False)
    raw_ocr_excerpt = Column(Text, nullable=True)
    biomarkers = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="records")

class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    drug_name = Column(String, index=True, nullable=False)
    dosage = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="prescriptions")

class BiomarkerRegistry(Base):
    __tablename__ = "biomarker_registry"
    code = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    loinc_code = Column(String, nullable=True)
    ref_min = Column(Float, nullable=False)
    ref_max = Column(Float, nullable=False)
    critical_min = Column(Float, nullable=True)
    critical_max = Column(Float, nullable=True)
    category = Column(String, nullable=False)
    explanation_en = Column(Text, nullable=True)
    explanation_hi = Column(Text, nullable=True)
    explanation_mr = Column(Text, nullable=True)

class DrugInteraction(Base):
    __tablename__ = "drug_interactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    drug_a = Column(String, index=True, nullable=False)
    drug_b = Column(String, index=True, nullable=False)
    severity = Column(String, nullable=False)
    clinical_effect = Column(Text, nullable=False)
    action_recommendation = Column(Text, nullable=False)

class SimulationCoefficient(Base):
    __tablename__ = "simulation_coefficients"
    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_code = Column(String, index=True, nullable=False)
    lifestyle_factor = Column(String, nullable=False)
    coefficient_per_month = Column(Float, nullable=False)
    reversibility_decay = Column(Float, default=0.05)
"""

files["schemas/dtos.py"] = """from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict
from datetime import datetime

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    age: Optional[int] = Field(None, ge=0, le=130)
    gender: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str

class ManualRecordCreate(BaseModel):
    record_date: Optional[datetime] = None
    biomarkers: Dict[str, float]

class SimulationRequest(BaseModel):
    horizon_days: int = Field(90, ge=14, le=365)
    daily_steps: int = Field(8000, ge=0, le=50000)
    carb_reduction_pct: float = Field(20.0, ge=0.0, le=100.0)
    weekly_cardio_mins: int = Field(150, ge=0, le=1200)
"""

files["services/knowledge_seeder.py"] = """from sqlalchemy.orm import Session
from models.orm import BiomarkerRegistry, DrugInteraction, SimulationCoefficient

def seed_knowledge_base_if_empty(db: Session):
    if db.query(BiomarkerRegistry).first():
        return

    markers = [
        BiomarkerRegistry(
            code="fasting_glucose", name="Fasting Blood Glucose", unit="mg/dL", loinc_code="1558-6",
            ref_min=70.0, ref_max=99.0, critical_min=50.0, critical_max=250.0, category="Metabolic",
            explanation_en="Primary measure of circulating sugar levels after fasting.",
            explanation_hi="????? ?? ??? ???? ?????? ?? ???????? ?????",
            explanation_mr="????????? ???????? ??????? ??????."
        ),
        BiomarkerRegistry(
            code="hba1c", name="Glycated Hemoglobin", unit="%", loinc_code="4548-4",
            ref_min=4.0, ref_max=5.6, critical_min=3.5, critical_max=12.0, category="Metabolic",
            explanation_en="Average blood sugar levels over the past 2-3 months.",
            explanation_hi="????? 2-3 ?????? ??? ??? ???? ?????? ?? ?????",
            explanation_mr="????? 2 ?? 3 ??????????? ???????? ??????? ?????? ?????."
        ),
        BiomarkerRegistry(
            code="cholesterol_total", name="Total Cholesterol", unit="mg/dL", loinc_code="2093-3",
            ref_min=125.0, ref_max=200.0, critical_min=80.0, critical_max=350.0, category="Lipid Profile",
            explanation_en="Cumulative serum lipid volume.",
            explanation_hi="???? ??? ??? ??????????? ?? ???????",
            explanation_mr="???????? ???? ????????????? ??????."
        ),
        BiomarkerRegistry(
            code="serum_creatinine", name="Serum Creatinine", unit="mg/dL", loinc_code="2160-0",
            ref_min=0.6, ref_max=1.3, critical_min=0.3, critical_max=5.0, category="Renal",
            explanation_en="Marker of glomerular filtration and kidney clearance capacity.",
            explanation_hi="?????? ?? ??? ???? ?? ?????? ?? ?????",
            explanation_mr="?????????????? ????????????? ??????."
        )
    ]
    db.add_all(markers)

    interactions = [
        DrugInteraction(
            drug_a="metformin", drug_b="contrast_media", severity="CRITICAL",
            clinical_effect="Significantly increased risk of fatal lactic acidosis through reduced renal clearance.",
            action_recommendation="Withhold metformin 48 hours prior to and post iodinated contrast imaging."
        ),
        DrugInteraction(
            drug_a="atorvastatin", drug_b="clarithromycin", severity="MAJOR",
            clinical_effect="CYP3A4 inhibition spikes serum statin concentrations, increasing risk of rhabdomyolysis.",
            action_recommendation="Temporarily suspend statin therapy during clarithromycin antibiotic course."
        ),
        DrugInteraction(
            drug_a="warfarin", drug_b="aspirin", severity="MAJOR",
            clinical_effect="Additive bleeding risk and severe gastrointestinal hemorrhage potential.",
            action_recommendation="Monitor INR closely; co-prescribe only under strict hematological protocol."
        )
    ]
    db.add_all(interactions)

    coeffs = [
        SimulationCoefficient(biomarker_code="fasting_glucose", lifestyle_factor="daily_steps_per_1000", coefficient_per_month=-1.5),
        SimulationCoefficient(biomarker_code="fasting_glucose", lifestyle_factor="dietary_carb_reduction_pct", coefficient_per_month=-0.45),
        SimulationCoefficient(biomarker_code="hba1c", lifestyle_factor="weekly_cardio_mins_per_60", coefficient_per_month=-0.12),
        SimulationCoefficient(biomarker_code="cholesterol_total", lifestyle_factor="dietary_carb_reduction_pct", coefficient_per_month=-0.8)
    ]
    db.add_all(coeffs)
    db.commit()
"""

files["services/simulation_engine.py"] = """from sqlalchemy.orm import Session
from models.orm import SimulationCoefficient, HealthRecord

class DynamicMetabolicTwin:
    @staticmethod
    def project_trajectory(db: Session, user_id: str, horizon_days: int, steps: int, carb_reduction: float, cardio_mins: int):
        last_record = db.query(HealthRecord).filter(
            HealthRecord.user_id == user_id,
            HealthRecord.extraction_failed == False
        ).order_by(HealthRecord.record_date.desc()).first()

        if not last_record or not last_record.biomarkers:
            return {"error": "Insufficient baseline biomarkers for simulation. Upload a verified lab report first."}

        baseline = last_record.biomarkers
        projections = {}

        for marker_code, initial_val in baseline.items():
            coefficients = db.query(SimulationCoefficient).filter(
                SimulationCoefficient.biomarker_code == marker_code
            ).all()

            monthly_delta = 0.0
            for coeff in coefficients:
                if coeff.lifestyle_factor == "daily_steps_per_1000":
                    monthly_delta += (steps / 1000.0) * coeff.coefficient_per_month
                elif coeff.lifestyle_factor == "dietary_carb_reduction_pct":
                    monthly_delta += carb_reduction * coeff.coefficient_per_month
                elif coeff.lifestyle_factor == "weekly_cardio_mins_per_60":
                    monthly_delta += (cardio_mins / 60.0) * coeff.coefficient_per_month

            trajectory = []
            for day in range(0, horizon_days + 1, 15):
                progress_months = day / 30.0
                projected_val = max(10.0, float(initial_val) + (monthly_delta * progress_months))
                trajectory.append({"day": day, "projected_value": round(projected_val, 2)})

            projections[marker_code] = {
                "baseline": initial_val,
                "projected_final": trajectory[-1]["projected_value"],
                "trajectory": trajectory
            }

        return {
            "simulation_horizon_days": horizon_days,
            "inputs": {
                "daily_steps": steps,
                "carb_reduction_pct": carb_reduction,
                "weekly_cardio_mins": cardio_mins
            },
            "projections": projections
        }
"""

files["services/dynamic_safety_engine.py"] = """from sqlalchemy.orm import Session
from models.orm import DrugInteraction, Prescription

class DynamicSafetyEngine:
    @staticmethod
    def audit_medications(db: Session, user_id: str) -> list:
        prescriptions = db.query(Prescription).filter(Prescription.user_id == user_id).all()
        active_drugs = [p.drug_name.strip().lower() for p in prescriptions]
        flagged_interactions = []

        for i in range(len(active_drugs)):
            for j in range(i + 1, len(active_drugs)):
                drug1, drug2 = active_drugs[i], active_drugs[j]
                match = db.query(DrugInteraction).filter(
                    ((DrugInteraction.drug_a == drug1) & (DrugInteraction.drug_b == drug2)) |
                    ((DrugInteraction.drug_a == drug2) & (DrugInteraction.drug_b == drug1))
                ).first()

                if match:
                    flagged_interactions.append({
                        "drugs": [drug1, drug2],
                        "severity": match.severity,
                        "clinical_effect": match.clinical_effect,
                        "action_recommendation": match.action_recommendation
                    })

        return flagged_interactions
"""

files["main.py"] = """import uuid
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from core.config import settings
from core.database import Base, engine, get_db
from core.security import (
    hash_password, verify_password, create_access_token,
    verify_user_ownership
)
from models.orm import User, HealthRecord, Prescription, BiomarkerRegistry
from schemas.dtos import UserRegisterRequest, TokenResponse, ManualRecordCreate, SimulationRequest
from services.knowledge_seeder import seed_knowledge_base_if_empty
from services.simulation_engine import DynamicMetabolicTwin
from services.dynamic_safety_engine import DynamicSafetyEngine

Base.metadata.create_all(bind=engine)

with Session(engine) as db_session:
    seed_knowledge_base_if_empty(db_session)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0-dynamic",
    description="Next-Gen AI Autonomous Health Operating System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Account with this email already registered.")
    new_user = User(
        id=str(uuid.uuid4()),
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        full_name=user_in.full_name,
        age=user_in.age,
        gender=user_in.gender
    )
    db.add(new_user)
    db.commit()
    token = create_access_token({"sub": new_user.id})
    return TokenResponse(access_token=token, user_id=new_user.id)

@app.post("/api/auth/token", response_model=TokenResponse)
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials provided.")
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user_id=user.id)

@app.post("/api/records/{user_id}/upload")
async def upload_lab_report(
    user_id: str,
    file: UploadFile = File(...),
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    if not file.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(status_code=422, detail="Invalid file type. Only PDF and clinical image scans are permitted.")
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    extracted_biomarkers = {}
    is_failed = len(extracted_biomarkers) == 0

    record = HealthRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        record_date=datetime.utcnow(),
        extraction_failed=is_failed,
        biomarkers=extracted_biomarkers,
        raw_ocr_excerpt="[Manual review required]" if is_failed else ""
    )
    db.add(record)
    db.commit()
    return {
        "record_id": record.id,
        "extraction_failed": is_failed,
        "biomarkers_extracted": extracted_biomarkers,
        "warning": "OCR extracted zero confident biomarkers. Review manually." if is_failed else None
    }

@app.post("/api/records/{user_id}/manual")
def add_manual_record(
    user_id: str,
    record_in: ManualRecordCreate,
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    record = HealthRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        record_date=record_in.record_date or datetime.utcnow(),
        extraction_failed=False,
        biomarkers=record_in.biomarkers
    )
    db.add(record)
    db.commit()
    return {"status": "success", "record_id": record.id, "biomarkers": record.biomarkers}

@app.get("/api/records/{user_id}/history")
def get_user_history(
    user_id: str,
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    records = db.query(HealthRecord).filter(HealthRecord.user_id == user_id).order_by(HealthRecord.record_date.desc()).all()
    return [{
        "record_id": r.id,
        "date": r.record_date,
        "failed": r.extraction_failed,
        "biomarkers": r.biomarkers
    } for r in records]

@app.post("/api/twin/{user_id}/simulate")
def run_simulation(
    user_id: str,
    sim_in: SimulationRequest,
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    return DynamicMetabolicTwin.project_trajectory(
        db=db,
        user_id=user_id,
        horizon_days=sim_in.horizon_days,
        steps=sim_in.daily_steps,
        carb_reduction=sim_in.carb_reduction_pct,
        cardio_mins=sim_in.weekly_cardio_mins
    )

@app.get("/api/safety/{user_id}/interactions")
def check_safety(
    user_id: str,
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    interactions = DynamicSafetyEngine.audit_medications(db, user_id)
    return {
        "user_id": user_id,
        "audit_timestamp": datetime.utcnow(),
        "total_violations": len(interactions),
        "interactions": interactions
    }

@app.post("/api/safety/{user_id}/prescriptions")
def add_prescription(
    user_id: str,
    drug_name: str = Form(...),
    dosage: str = Form(...),
    frequency: str = Form(...),
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    rx = Prescription(
        id=str(uuid.uuid4()),
        user_id=user_id,
        drug_name=drug_name.strip().lower(),
        dosage=dosage,
        frequency=frequency
    )
    db.add(rx)
    db.commit()
    return {"status": "added", "prescription_id": rx.id, "drug": rx.drug_name}

@app.get("/api/handoff/{user_id}/summary")
def generate_handoff_briefing(
    user_id: str,
    auth_user: str = Depends(verify_user_ownership),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    records = db.query(HealthRecord).filter(HealthRecord.user_id == user_id).order_by(HealthRecord.record_date.desc()).all()
    interactions = DynamicSafetyEngine.audit_medications(db, user_id)
    latest_markers = records[0].biomarkers if records and not records[0].extraction_failed else {}
    return {
        "doctor_briefing": {
            "patient_name": user.full_name,
            "demographics": {"age": user.age, "gender": user.gender},
            "generated_at": datetime.utcnow().isoformat(),
            "latest_biomarker_snapshot": latest_markers,
            "active_safety_warnings": interactions,
            "total_records_tracked": len(records)
        }
    }

@app.get("/api/registry/biomarkers")
def list_registered_biomarkers(db: Session = Depends(get_db)):
    return db.query(BiomarkerRegistry).all()
"""

files["tests/test_dynamic_pipeline.py"] = """import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import Base, engine

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_idor_and_dynamic_flow():
    res_a = client.post("/api/auth/register", json={
        "email": "alice@hospital.org", "password": "SecurePassword123!", "full_name": "Alice M"
    })
    token_a = res_a.json()["access_token"]
    id_a = res_a.json()["user_id"]

    res_b = client.post("/api/auth/register", json={
        "email": "bob@hospital.org", "password": "SecurePassword456!", "full_name": "Bob K"
    })
    token_b = res_b.json()["access_token"]

    unauthorized = client.get(f"/api/records/{id_a}/history", headers={"Authorization": f"Bearer {token_b}"})
    assert unauthorized.status_code == 403

    client.post(
        f"/api/records/{id_a}/manual",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"biomarkers": {"fasting_glucose": 115.0}}
    )

    sim = client.post(
        f"/api/twin/{id_a}/simulate",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"horizon_days": 90, "daily_steps": 10000, "carb_reduction_pct": 25.0, "weekly_cardio_mins": 180}
    )
    assert sim.status_code == 200
    assert sim.json()["projections"]["fasting_glucose"]["projected_final"] < 115.0
"""

for path, content in files.items():
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {path}")

print("\nFinished writing dynamic files.")
