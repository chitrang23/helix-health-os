from pydantic import BaseModel, EmailStr, Field
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


class LifestyleData(BaseModel):
    activity_level: str  # e.g., "sedentary", "lightly_active", "moderately_active", "very_active"
    sleep_hours_avg: float  # e.g., 7.5
    diet_type: str  # e.g., "balanced", "keto", "vegetarian", "vegan", "mediterranean"
    smoking_status: str  # e.g., "never", "former", "current"
    alcohol_consumption: str  # e.g., "none", "occasional", "moderate", "heavy"
    primary_goal: Optional[str] = "general_wellness"
