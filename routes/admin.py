from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

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

    model_config = ConfigDict(from_attributes=True)

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
