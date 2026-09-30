from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    birthday = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    records = relationship("LabRecord", back_populates="user")
    diagnoses = relationship("DiagnosisHistory", back_populates="user")

class LabRecord(Base):
    __tablename__ = "lab_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    extracted_biomarkers = Column(JSON)
    raw_ocr_text = Column(Text)
    hospital_name = Column(String, default="Unknown Facility")
    report_date = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="records")

class DiagnosisHistory(Base):
    __tablename__ = "diagnosis_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    diagnosis_title = Column(String, nullable=False)
    description = Column(Text)
    hospital_name = Column(String)
    diagnosis_date = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    user = relationship("User", back_populates="diagnoses")
