# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from models.orm import BiomarkerRegistryModel, DrugRuleModel
from seed_data import SEED_BIOMARKERS, SEED_DRUG_RULES

def seed_db_if_empty(db: Session):
    if db.query(BiomarkerRegistryModel).first() is None:
        for b in SEED_BIOMARKERS:
            model = BiomarkerRegistryModel(
                key=b["key"],
                name=b["name"],
                loinc=b["loinc"],
                unit=b["unit"],
                patterns=b.get("patterns", []),
                normal_low=b["normal_low"],
                normal_high=b["normal_high"],
                panic_low=b.get("panic_low"),
                panic_high=b.get("panic_high"),
                guideline=b["guideline"],
                scale_bucket=b.get("scale_bucket", "normal"),
                translations=b.get("translations", {}),
                symptom_rules=b.get("symptom_rules", {})
            )
            db.add(model)
        db.commit()

    if db.query(DrugRuleModel).first() is None:
        for r in SEED_DRUG_RULES:
            model = DrugRuleModel(
                rule_type=r["rule_type"],
                trigger_a=r["trigger_a"].strip().lower(),
                trigger_b=r.get("trigger_b", "").strip().lower() if r.get("trigger_b") else None,
                biomarker_key=r.get("biomarker_key"),
                operator=r.get("operator"),
                threshold=r.get("threshold"),
                severity=r["severity"],
                pair_label=r["pair_label"],
                mechanism=r["mechanism"]
            )
            db.add(model)
        db.commit()
