import os

print("Deploying Elite Clinical Triage & 3D UI Enhancements...")

# 1. Create the Advanced Clinical Panic & Pharmacovigilance Engine
panic_engine_path = "services/clinical_panic_engine.py"
panic_engine_code = '''# Advanced Clinical Panic Triage & Pharmacovigilance Engine
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
'''
with open(panic_engine_path, "w", encoding="utf-8") as f:
    f.write(panic_engine_code)
print("Created services/clinical_panic_engine.py")

# 2. Wire Clinical Panic Endpoint into routes/clinical.py
clinical_route_path = "routes/clinical.py"
if os.path.exists(clinical_route_path):
    with open(clinical_route_path, "r", encoding="utf-8") as f:
        c_code = f.read()
    
    panic_endpoint = '''
from services.clinical_panic_engine import ClinicalPanicEngine

@router.post("/api/clinical/evaluate-panic")
async def evaluate_clinical_panic(payload: dict):
    labs = payload.get("labs", {})
    meds = payload.get("meds", [])
    return ClinicalPanicEngine.evaluate_panics_and_interactions(labs, meds)
'''
    if "evaluate-panic" not in c_code:
        c_code += "\n" + panic_endpoint
        with open(clinical_route_path, "w", encoding="utf-8") as f:
            f.write(c_code)
        print("Wired clinical panic evaluation endpoint into routes/clinical.py")

# 3. Enhance 3D UI Styling in public/css/styles.css
css_path = "public/css/styles.css"
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        css_data = f.read()
    
    three_d_enhancements = '''
/* 3D Immersive UI & Depth Enhancements */
.card, .dashboard-card, .metric-box, .glass-panel {
    transform-style: preserve-3d;
    perspective: 1000px;
    transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.4s ease;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08), 0 1px 8px rgba(0,0,0,0.04);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.18);
}
.card:hover, .dashboard-card:hover, .metric-box:hover {
    transform: translateY(-6px) rotateX(2deg) rotateY(-2deg);
    box-shadow: 0 20px 40px rgba(13, 110, 253, 0.15), 0 5px 15px rgba(0,0,0,0.08);
}
.badge-critical {
    background: linear-gradient(135deg, #ff416c, #ff4b2b);
    color: white;
    font-weight: bold;
    animation: pulseGlow 2s infinite;
}
@keyframes pulseGlow {
    0% { box-shadow: 0 0 0 0 rgba(255, 65, 108, 0.4); }
    70% { box-shadow: 0 0 0 12px rgba(255, 65, 108, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 65, 108, 0); }
}
'''
    if "3D Immersive UI" not in css_data:
        css_data += "\n" + three_d_enhancements
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(css_data)
        print("Enhanced 3D UI perspective, depth shadows, and interactive tilt styles in public/css/styles.css")

print("Elite Doctor & Developer Upgrades successfully deployed!")
