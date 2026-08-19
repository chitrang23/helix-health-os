from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    age = Column(Integer, default=30)
    gender = Column(String, default="Not specified")
    dietary_preference = Column(String, default="Vegetarian")
    active_prescriptions = Column(JSON, default=list)
    active_supplements = Column(JSON, default=list)
    treatment_history = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    reports = relationship("LabReport", back_populates="user", cascade="all, delete-orphan", order_by="LabReport.record_date.asc()")

class LabReport(Base):
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    hospital_name = Column(String, nullable=False)
    record_date = Column(DateTime, nullable=False)
    raw_ocr_text = Column(String, nullable=True)
    biomarkers = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reports")
