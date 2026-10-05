# Advanced Clinical Panic Triage & Pharmacovigilance Engine
# Designed by Clinical Advisory & Systems Architecture

class ClinicalPanicEngine:
    CRITICAL_THRESHOLDS = {
        "glucose": {"min": 50, "max": 400, "unit": "mg/dL", "risk": "Hyper/Hypoglycemic Crisis"},
        "hba1c": {"min": 4.0, "max": 14.0, "unit": "%", "risk": "Severe Glycemic Deregulation"},
        "creatinine": {"min": 0.5, "max": 5.0, "unit": "mg/dL", "risk": "Acute Kidney Injury Indicator"},
        "potassium": {"min": 2.8, "max": 6.5, "unit": "mmol/L", "risk": "Cardiac Arrhythmia Risk"}
    }

    @classmethod
    def evaluate_panics_and_interactions(cls, lab_results: dict, active_meds: list):
        alerts = []
        for marker, val in lab_results.items():
            m_lower = marker.lower()
            if m_lower in cls.CRITICAL_THRESHOLDS:
                cfg = cls.CRITICAL_THRESHOLDS[m_lower]
                if val < cfg["min"] or val > cfg["max"]:
                    alerts.append({
                        "marker": marker,
                        "value": val,
                        "risk_level": "CRITICAL EMERGENCY",
                        "description": f"Value {val} {cfg['unit']} exceeds safe limits. Risk: {cfg['risk']}",
                        "action": "Immediate physician consultation required."
                    })
        
        # Pharmacovigilance check
        drug_warnings = []
        for med in active_meds:
            if "metformin" in med.lower() and any(r.get("marker") == "creatinine" and r.get("value", 0) > 1.5 for r in alerts):
                drug_warnings.append({
                    "medication": med,
                    "warning": "Contraindication Warning: Elevated creatinine detected while on Metformin. Risk of lactic acidosis."
                })

        return {
            "panic_alerts": alerts,
            "pharmacovigilance_warnings": drug_warnings,
            "escalation_required": len(alerts) > 0 or len(drug_warnings) > 0
        }
