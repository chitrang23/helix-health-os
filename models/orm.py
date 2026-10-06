from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lab_reports = relationship("LabReport", back_populates="user", cascade="all, delete-orphan")
    chat_logs = relationship("ChatLog", back_populates="user", cascade="all, delete-orphan")
    health_records = relationship("HealthRecord", back_populates="user", cascade="all, delete-orphan")
    stress_logs = relationship("StressLog", back_populates="user", cascade="all, delete-orphan")


class LabReport(Base):
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    patient_name = Column(String(100), nullable=True)
    report_date = Column(String(50), nullable=True)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="lab_reports")


class BiomarkerRegistryModel(Base):
    __tablename__ = "biomarker_registry"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=True)
    min_ref = Column(Float, nullable=True)
    max_ref = Column(Float, nullable=True)
    loinc = Column(String(50), nullable=True)
    loinc_code = Column(String(50), nullable=True)
    display_name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    patterns = Column(JSON, nullable=True)

    def __init__(self, **kwargs):
        cls_cols = {col.key for col in self.__table__.columns}
        for key, val in kwargs.items():
            if key in cls_cols:
                setattr(self, key, val)


class DrugRuleModel(Base):
    __tablename__ = "drug_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(50), nullable=False)
    trigger_a = Column(String(100), nullable=False, index=True)
    trigger_b = Column(String(100), nullable=True)
    biomarker_key = Column(String(50), nullable=True)
    operator = Column(String(10), nullable=True)
    threshold = Column(Float, nullable=True)
    severity = Column(String(20), default="high")
    pair_label = Column(String(255), nullable=False)
    mechanism = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        cls_cols = {col.key for col in self.__table__.columns}
        for key, val in kwargs.items():
            if key in cls_cols:
                setattr(self, key, val)

DrugInteractionRule = DrugRuleModel


class SimulationCoefficient(Base):
    __tablename__ = "simulation_coefficients"

    id = Column(Integer, primary_key=True, index=True)
    biomarker_name = Column(String, nullable=False, index=True)
    target_biomarker = Column(String, nullable=False)
    coefficient = Column(Float, default=0.0)
    intercept = Column(Float, default=0.0)


class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    biomarker_name = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="health_records")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_logs")


class StressLog(Base):
    __tablename__ = "stress_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stress_score = Column(Integer, nullable=False)  # Scale 1-10
    perceived_triggers = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="stress_logs")