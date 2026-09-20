# -*- coding: utf-8 -*-
import os

print("🚀 Starting Helix OS Upgrade Execution...")

# 1. Update/Write routes/admin.py
os.makedirs("routes", exist_ok=True)
admin_route_code = '''from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel

from core.database import get_db
from core.security import require_admin
from models.orm import DrugInteractionRule, User

admin_router = APIRouter(prefix="/api/v1/admin", tags=["Admin Rule Engine"])

class DrugRuleCreate(BaseModel):
    rule_type: str  # "drug_drug", "drug_supplement", "drug_biomarker"
    trigger_a: str
    trigger_b: Optional[str] = None
    biomarker_key: Optional[str] = None
    operator: Optional[str] = None  # ">", ">=", "<", "<="
    threshold: Optional[float] = None
    severity: str  # "high", "moderate", "low", "critical"
    pair_label: str
    mechanism: str

class DrugRuleResponse(DrugRuleCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

@admin_router.get("/drug-interactions", response_model=List[DrugRuleResponse])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Retrieve all interaction rules."""
    result = await db.execute(select(DrugInteractionRule))
    return result.scalars().all()

@admin_router.post("/drug-interactions", response_model=DrugRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: DrugRuleCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a new drug interaction or biomarker safety rule."""
    rule = DrugInteractionRule(**payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@admin_router.patch("/drug-interactions/{rule_id}/toggle", response_model=DrugRuleResponse)
async def toggle_rule_status(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Retire or re-activate an interaction rule without deleting it."""
    result = await db.execute(select(DrugInteractionRule).where(DrugInteractionRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Interaction rule not found.")
    
    rule.is_active = not getattr(rule, "is_active", True)
    await db.commit()
    await db.refresh(rule)
    return rule
'''

with open("routes/admin.py", "w", encoding="utf-8") as f:
    f.write(admin_route_code)
print("  ✅ routes/admin.py created.")

# 2. Write Unit Tests for SafetyEngine in tests/test_safety_engine.py
os.makedirs("tests", exist_ok=True)
test_code = '''import pytest
from unittest.mock import MagicMock
from services.safety_engine import SafetyEngine

@pytest.fixture
def sample_rules():
    rule_dd = MagicMock()
    rule_dd.rule_type = "drug_drug"
    rule_dd.trigger_a = "metformin"
    rule_dd.trigger_b = "contrast"
    rule_dd.severity = "high"
    rule_dd.pair_label = "Metformin + Iodinated Contrast"
    rule_dd.mechanism = "Risk of lactic acidosis."
    rule_dd.is_active = True

    rule_db = MagicMock()
    rule_db.rule_type = "drug_biomarker"
    rule_db.trigger_a = "metformin"
    rule_db.biomarker_key = "eGFR"
    rule_db.operator = "<"
    rule_db.threshold = 30.0
    rule_db.severity = "critical"
    rule_db.pair_label = "Metformin Renal Cutoff"
    rule_db.mechanism = "Contraindicated when eGFR < {threshold} mL/min (current: {value})."
    rule_db.is_active = True

    return [rule_dd, rule_db]

def test_drug_drug_interaction_detected(sample_rules):
    rx = ["Metformin 500mg", "Iodinated Contrast"]
    supplements = []
    alerts = SafetyEngine.evaluate_interactions(rx, supplements, sample_rules)
    
    assert len(alerts) == 1
    assert alerts[0]["level"] == "high"
    assert alerts[0]["pair"] == "Metformin + Iodinated Contrast"

def test_drug_biomarker_threshold_exceeded(sample_rules):
    rx = ["Metformin 500mg"]
    biomarkers = {"eGFR": 24.5}
    alerts = SafetyEngine.evaluate_interactions(rx, [], sample_rules, latest_biomarkers=biomarkers)

    assert len(alerts) == 1
    assert alerts[0]["level"] == "critical"
    assert "24.5" in alerts[0]["mechanism"]
'''

with open("tests/test_safety_engine.py", "w", encoding="utf-8") as f:
    f.write(test_code)
print("  ✅ tests/test_safety_engine.py created.")

# 3. Update main.py to register the admin router and portal route
if os.path.exists("main.py"):
    with open("main.py", "r", encoding="utf-8") as f:
        main_code = f.read()

    # Ensure admin router is registered
    if "admin_router" not in main_code:
        import_line = "from routes.admin import admin_router\n"
        app_include = "\napp.include_router(admin_router)\n"
        main_code = import_line + main_code + app_include

    with open("main.py", "w", encoding="utf-8") as f:
        f.write(main_code)
    print("  ✅ main.py updated with Admin API router.")

print("\n🎉 Upgrade executed successfully! Run pytest to verify:")
print("   pytest tests/test_safety_engine.py")
