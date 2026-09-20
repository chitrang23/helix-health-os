from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models.orm import DrugRuleModel

MULTI_DRUG_INTERACTION_MATRIX = {
    ("statins", "fibrates"): {
        "severity": "critical",
        "issue": "Concomitant use significantly increases risk of severe rhabdomyolysis and liver toxicity."
    },
    ("ace_inhibitors", "spironolactone"): {
        "severity": "critical",
        "issue": "High risk of severe hyperkalemia."
    }
}

class DynamicSafetyEngine:
    def check_safety(self, db: Session, active_medications: List[str], biomarker_values: Dict[str, float]) -> Dict[str, Any]:
        alerts = []
        max_severity = "low"
        
        # 1. Single Drug-Biomarker Contraindication Check
        rules = db.query(DrugRuleModel).all()
        meds_clean = [m.strip().lower() for m in active_medications]
        
        for rule in rules:
            if rule.drug_name.lower() in meds_clean:
                bio_val = biomarker_values.get(rule.contraindicated_biomarker.lower())
                if bio_val is not None:
                    if (rule.min_threshold and bio_val < rule.min_threshold) or                        (rule.max_threshold and bio_val > rule.max_threshold):
                        alerts.append({
                            "type": "single_drug_contraindication",
                            "drug": rule.drug_name,
                            "biomarker": rule.contraindicated_biomarker,
                            "value": bio_val,
                            "severity": rule.severity,
                            "message": f"Medication '{rule.drug_name}' contraindicated with {rule.contraindicated_biomarker} value of {bio_val}."
                        })
                        if rule.severity == "critical":
                            max_severity = "critical"
                        elif rule.severity == "moderate" and max_severity != "critical":
                            max_severity = "moderate"

        # 2. Multi-Drug Interaction Matrix Check
        for i in range(len(meds_clean)):
            for j in range(i + 1, len(meds_clean)):
                pair = tuple(sorted([meds_clean[i], meds_clean[j]]))
                if pair in MULTI_DRUG_INTERACTION_MATRIX:
                    interaction = MULTI_DRUG_INTERACTION_MATRIX[pair]
                    alerts.append({
                        "type": "multi_drug_interaction",
                        "drugs": list(pair),
                        "severity": interaction["severity"],
                        "message": interaction["issue"]
                    })
                    max_severity = "critical"

        return {
            "safe": len(alerts) == 0,
            "overall_severity": max_severity if alerts else "none",
            "alerts": alerts
        }
