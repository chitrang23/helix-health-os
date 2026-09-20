import os
import glob

print("🔧 Fixing database schema and syncing models...")

# 1. Update models/orm.py cleanly
os.makedirs("models", exist_ok=True)
orm_code = '''from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey, JSON
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

class LabReport(Base):
    __tablename__ = "lab_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    patient_name = Column(String(100), nullable=True)
    report_date = Column(String(50), nullable=True)
    extracted_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BiomarkerRegistryModel(Base):
    __tablename__ = "biomarker_registry"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=True)
    min_ref = Column(Float, nullable=True)
    max_ref = Column(Float, nullable=True)
    description = Column(Text, nullable=True)

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

# Compatibility alias
DrugInteractionRule = DrugRuleModel
'''

with open("models/orm.py", "w", encoding="utf-8") as f:
    f.write(orm_code)
print("  ✅ models/orm.py updated.")

# 2. Clear out existing stale SQLite database files
db_files = glob.glob("*.db") + glob.glob("core/*.db") + glob.glob("data/*.db")
for db_f in db_files:
    try:
        os.remove(db_f)
        print(f"  🗑️ Removed outdated database: {db_f}")
    except Exception as e:
        print(f"  ⚠️ Could not remove {db_f}: {e}")

# 3. Ensure database.py creates all tables on initialization
os.makedirs("core", exist_ok=True)
db_code = '''from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.orm import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./helix.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Re-create all tables matching ORM models
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

with open("core/database.py", "w", encoding="utf-8") as f:
    f.write(db_code)
print("  ✅ core/database.py updated with table auto-creation.")

print("\n🎉 Database schema synced! Try running pytest now.")
