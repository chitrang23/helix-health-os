from typing import Dict, Any

class SimulationEngine:
    def simulate_intervention(self, current_biomarkers: Dict[str, float], intervention_type: str) -> Dict[str, Any]:
        """
        Simulates multi-biomarker coupled physiological changes based on lifestyle interventions.
        """
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
