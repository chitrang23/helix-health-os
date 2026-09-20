# -*- coding: utf-8 -*-
import os

print("🔧 Updating models/orm.py with required ORM models...")

os.makedirs("models", exist_ok=True)
orm_code = '''from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey
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

class DrugInteractionRule(Base):
    __tablename__ = "drug_interaction_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(50), nullable=False)  # 'drug_drug', 'drug_supplement', 'drug_biomarker'
    trigger_a = Column(String(100), nullable=False, index=True)
    trigger_b = Column(String(100), nullable=True)
    biomarker_key = Column(String(50), nullable=True)
    operator = Column(String(10), nullable=True)  # '<', '<=', '>', '>='
    threshold = Column(Float, nullable=True)
    severity = Column(String(20), default="high")  # 'low', 'moderate', 'high', 'critical'
    pair_label = Column(String(255), nullable=False)
    mechanism = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
'''

with open("models/orm.py", "w", encoding="utf-8") as f:
    f.write(orm_code)

print("  ✅ models/orm.py updated with DrugInteractionRule and User.")
