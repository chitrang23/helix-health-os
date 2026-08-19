from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class PatientCreate(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    dietary_preference: str = "Vegetarian"
    active_prescriptions: List[str] = []
    active_supplements: List[str] = []

class LabReportCreate(BaseModel):
    patient_id: str
    hospital_name: str
    record_date: datetime
    biomarkers: Dict[str, float]
    raw_ocr_text: Optional[str] = None

class SimulationInput(BaseModel):
    exercise_days_per_week: int = Field(..., ge=0, le=7)
    daily_sugar_reduction_pct: float = Field(..., ge=0, le=100)
    caloric_deficit_kcal: int = Field(default=300, ge=0, le=1500)

class DrugSafetyQuery(BaseModel):
    prescriptions: List[str]
    supplements: List[str]

class ChatQuery(BaseModel):
    question: str
    language: str = "en"
