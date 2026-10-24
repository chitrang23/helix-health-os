# models/orm.py
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    dob = Column(String(50), nullable=True)
    gender = Column(String(20), nullable=True)
    role = Column(String(20), default="patient", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Scoped Provenance Relationships
    source_documents = relationship("SourceDocument", back_populates="owner", cascade="all, delete-orphan")
    clinical_observations = relationship("ClinicalObservation", back_populates="owner", cascade="all, delete-orphan")
    chat_logs = relationship("ChatLog", back_populates="user", cascade="all, delete-orphan")
    stress_logs = relationship("StressLog", back_populates="user", cascade="all, delete-orphan")
    lifestyle_entries = relationship("LifestyleEntry", back_populates="owner", cascade="all, delete-orphan")
    user_medications = relationship("UserMedication", back_populates="owner", cascade="all, delete-orphan")
    corrections_made = relationship("ObservationCorrectionHistory", back_populates="corrected_by_user", cascade="all, delete-orphan")

    # Backward-compatibility aliases for legacy routes
    lab_reports = relationship("SourceDocument", back_populates="owner", viewonly=True)
    health_records = relationship("ClinicalObservation", back_populates="owner", viewonly=True)


class SourceDocument(Base):
    """
    Step 2 Provenance Contract:
    Stores document metadata, SHA-256 fingerprint (to prevent silent duplicates),
    and strictly distinguishes collection, observation, issue, and upload dates.
    """
    __tablename__ = "source_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    file_sha256 = Column(String(64), nullable=True, index=True)

    # Provenance Timestamps & Dates
    collection_date = Column(DateTime, nullable=True)
    observation_date = Column(DateTime, nullable=True)
    issue_date = Column(DateTime, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_date_confirmed = Column(Boolean, default=False, nullable=False)
    date_clarification_note = Column(String(255), nullable=True)

    # Facility Context
    facility_name = Column(String(255), nullable=True)
    patient_name_on_doc = Column(String(150), nullable=True)
    parser_version = Column(String(50), nullable=True)
    raw_extracted_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="source_documents")
    observations = relationship("ClinicalObservation", back_populates="source_doc", cascade="all, delete-orphan")

    # Legacy compatibility getters
    @property
    def report_date(self):
        target = self.observation_date or self.collection_date or self.issue_date
        return target.strftime("%Y-%m-%d") if target else None

    @property
    def patient_name(self):
        return self.patient_name_on_doc

    @property
    def file_path(self):
        return self.storage_path


class ClinicalObservation(Base):
    """
    Step 2 Provenance Contract:
    Every observation carries its source document link, authenticated owner ID,
    original text/value, normalized value/unit, observation timestamp, analyte name
    exactly as written, parser confidence, extraction method, verification status,
    and references to its immutable correction history.
    """
    __tablename__ = "clinical_observations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=True, index=True)

    # Exact Terminology & LOINC mapping
    analyte_as_written = Column(String(200), nullable=False, index=True)
    canonical_key = Column(String(100), nullable=True, index=True)
    loinc_code = Column(String(50), nullable=True, index=True)
    category = Column(String(50), nullable=True)

    # Immutable Raw & Derived Values
    original_value = Column(String(100), nullable=False)
    normalized_numeric_value = Column(Float, nullable=True)
    original_unit = Column(String(50), nullable=True)
    normalized_unit = Column(String(50), nullable=True)
    unit_conversion_factor = Column(Float, nullable=True)

    # Document-printed Reference Context (Never fabricated)
    printed_reference_range = Column(String(100), nullable=True)
    laboratory_flag = Column(String(50), nullable=True)  # e.g., 'Normal', 'High', 'Low', 'Critical'

    # Effective Timing
    effective_date = Column(DateTime, nullable=True, index=True)

    # Provenance Categorization
    # data_source_type: 'document_extraction', 'user_entered', 'calculated'
    data_source_type = Column(String(50), nullable=False, default="document_extraction")
    # extraction_method: 'ocr_digital', 'vision_multimodal', 'manual_portal'
    extraction_method = Column(String(50), nullable=False, default="ocr_digital")
    confidence_score = Column(Float, nullable=False, default=1.0)
    # verification_status: 'unreviewed', 'user_verified', 'disputed'
    verification_status = Column(String(50), nullable=False, default="unreviewed")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="clinical_observations")
    source_doc = relationship("SourceDocument", back_populates="observations")
    corrections = relationship("ObservationCorrectionHistory", back_populates="observation", cascade="all, delete-orphan")

    # Legacy Compatibility Properties
    @property
    def test_name(self):
        return self.analyte_as_written

    @property
    def biomarker_name(self):
        return self.analyte_as_written

    @property
    def value(self):
        return self.normalized_numeric_value if self.normalized_numeric_value is not None else self.original_value

    @property
    def unit(self):
        return self.original_unit

    @property
    def recorded_at(self):
        return self.effective_date

    @property
    def report(self):
        return self.source_doc


class ObservationCorrectionHistory(Base):
    """
    Step 2 Provenance Contract:
    Retains an auditable, append-only history of corrections so the original
    raw extraction is never overwritten or lost.
    """
    __tablename__ = "observation_correction_history"

    id = Column(Integer, primary_key=True, index=True)
    observation_id = Column(Integer, ForeignKey("clinical_observations.id"), nullable=False, index=True)
    corrected_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    previous_value = Column(String(100), nullable=False)
    updated_value = Column(String(100), nullable=False)
    previous_unit = Column(String(50), nullable=True)
    updated_unit = Column(String(50), nullable=True)
    reason = Column(String(255), nullable=True)

    corrected_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    observation = relationship("ClinicalObservation", back_populates="corrections")
    corrected_by_user = relationship("User", back_populates="corrections_made")


class UserMedication(Base):
    """
    Tracks documented or patient-entered prescriptions & supplements
    for the Dynamic Drug Safety Shield.
    """
    __tablename__ = "user_medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    substance_name = Column(String(150), nullable=False, index=True)
    dosage = Column(String(50), nullable=True)
    frequency = Column(String(50), nullable=True)
    is_supplement = Column(Boolean, default=False, nullable=False)
    source_type = Column(String(50), nullable=False)  # 'document_extracted', 'user_entered'
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="user_medications")


class LifestyleEntry(Base):
    """
    Grounded lifestyle inputs (sleep, activity, nutrition) for the Digital Twin.
    No simulated values substituted if missing.
    """
    __tablename__ = "lifestyle_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    logged_date = Column(DateTime, nullable=False, index=True)
    sleep_hours = Column(Float, nullable=True)
    activity_level = Column(String(50), nullable=True)
    diet_pattern = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    data_source_type = Column(String(50), default="user_reported", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="lifestyle_entries")


class StressLog(Base):
    __tablename__ = "stress_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stress_score = Column(Integer, nullable=False)  # Scale 1-10
    perceived_triggers = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="stress_logs")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    source_citations = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="chat_logs")


class BiomarkerRegistryModel(Base):
    """
    Reference definitions and LOINC standard mappings.
    Contains clinical reference intervals—never to be presented as patient results.
    """
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
    guideline = Column(String(255), nullable=True)
    patterns = Column(JSON, nullable=True)

    def __init__(self, **kwargs):
        cls_cols = {col.key for col in self.__table__.columns}
        for key, val in kwargs.items():
            if key in cls_cols:
                setattr(self, key, val)


class DrugRuleModel(Base):
    """
    Clinical pharmacovigilance contraindications and drug-drug/biomarker rules.
    """
    __tablename__ = "drug_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(50), nullable=False)
    trigger_a = Column(String(100), nullable=False, index=True)
    trigger_b = Column(String(100), nullable=True)
    biomarker_key = Column(String(50), nullable=True)
    operator = Column(String(10), nullable=True)
    threshold = Column(Float, nullable=True)
    severity = Column(String(20), default="high", nullable=False)
    pair_label = Column(String(255), nullable=False)
    mechanism = Column(Text, nullable=True)
    evidence_source = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        cls_cols = {col.key for col in self.__table__.columns}
        for key, val in kwargs.items():
            if key in cls_cols:
                setattr(self, key, val)


class SimulationCoefficient(Base):
    __tablename__ = "simulation_coefficients"

    id = Column(Integer, primary_key=True, index=True)
    biomarker_name = Column(String(100), nullable=False, index=True)
    target_biomarker = Column(String(100), nullable=False)
    coefficient = Column(Float, default=0.0, nullable=False)
    intercept = Column(Float, default=0.0, nullable=False)


# Composite indexes for fast longitudinal lookup without cross-tenant leaks
Index("ix_obs_user_analyte_date", ClinicalObservation.user_id, ClinicalObservation.analyte_as_written, ClinicalObservation.effective_date)
Index("ix_docs_user_obsdate", SourceDocument.user_id, SourceDocument.observation_date)

# Compatibility Aliases for existing routes, services, and tests
LabReport = SourceDocument
HealthRecord = ClinicalObservation
BiomarkerRecord = ClinicalObservation
HealthReport = SourceDocument
DrugInteractionRule = DrugRuleModel