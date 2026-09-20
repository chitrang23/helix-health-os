# 1. Update services/simulation_engine.py
sim_code = """from typing import Dict, Any

class SimulationEngine:
    def simulate_intervention(self, current_biomarkers: Dict[str, float], intervention_type: str) -> Dict[str, Any]:
        \"\"\"
        Simulates multi-biomarker coupled physiological changes based on lifestyle interventions.
        \"\"\"
        simulated = current_biomarkers.copy()
        impact_summary = []

        if intervention_type == "aerobic_exercise_3x_week":
            if "fasting_glucose" in simulated:
                simulated["fasting_glucose"] = round(simulated["fasting_glucose"] * 0.92, 2)
                impact_summary.append("Fasting Glucose projected to drop by ~8% via improved insulin sensitivity.")
            if "hba1c" in simulated:
                simulated["hba1c"] = round(simulated["hba1c"] - 0.3, 2)
                impact_summary.append("HbA1c projected to decrease by ~0.3%.")
            if "total_cholesterol" in simulated:
                simulated["total_cholesterol"] = round(simulated["total_cholesterol"] * 0.95, 2)
                impact_summary.append("Total Cholesterol projected to decrease by ~5%.")

        elif intervention_type == "mediterranean_diet":
            if "fasting_glucose" in simulated:
                simulated["fasting_glucose"] = round(simulated["fasting_glucose"] * 0.95, 2)
            if "total_cholesterol" in simulated:
                simulated["total_cholesterol"] = round(simulated["total_cholesterol"] * 0.90, 2)
                impact_summary.append("Lipid profile expected to improve by ~10%.")

        return {
            "intervention": intervention_type,
            "simulated_biomarkers": simulated,
            "clinical_impacts": impact_summary
        }
"""

with open("services/simulation_engine.py", "w", encoding="utf-8") as f:
    f.write(sim_code)

# 2. Update services/translation_engine.py
trans_code = """from typing import Dict, Any

class TranslationEngine:
    def translate_report(self, biomarker_key: str, value: float, mode: str = "simple") -> str:
        \"\"\"
        Translates biomarker clinical values into plain explanations based on health literacy levels.
        Modes: 'simple', 'detailed', 'clinical'
        \"\"\"
        key_clean = biomarker_key.lower()
        
        explanations = {
            "fasting_glucose": {
                "simple": f"Your fasting blood sugar is {value}. This measures how much sugar is in your blood after not eating.",
                "detailed": f"Fasting glucose is {value} mg/dL. Values above 100 mg/dL indicate early insulin resistance.",
                "clinical": f"Fasting plasma glucose recorded at {value} mg/dL. Assess glycemic control and impaired fasting glucose (IFG) thresholds."
            },
            "hba1c": {
                "simple": f"Your HbA1c is {value}%. This shows your average blood sugar levels over the past 3 months.",
                "detailed": f"HbA1c is {value}%. A level between 5.7% and 6.4% indicates prediabetes.",
                "clinical": f"Glycated hemoglobin (HbA1c) measured at {value}%. Evaluates long-term glycemic state and diabetes management."
            }
        }

        if key_clean in explanations:
            return explanations[key_clean].get(mode, explanations[key_clean]["simple"])
        
        return f"{biomarker_key} recorded at {value}."
"""

with open("services/translation_engine.py", "w", encoding="utf-8") as f:
    f.write(trans_code)

print("✅ Step 5: Updated services/simulation_engine.py & services/translation_engine.py!")
