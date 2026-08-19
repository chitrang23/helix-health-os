class MetabolicTwinEngine:
    @staticmethod
    def simulate_trajectory(current_markers: dict, inputs: dict) -> dict:
        curr_fbs = current_markers.get("fasting_glucose", 100.0)
        curr_hba1c = current_markers.get("hba1c", 5.7)
        curr_ldl = current_markers.get("ldl_cholesterol", 120.0)

        fbs_reduction = (inputs["exercise_days_per_week"] * 2.0) + (inputs["daily_sugar_reduction_pct"] * 0.22)
        hba1c_reduction = (inputs["exercise_days_per_week"] * 0.06) + (inputs["daily_sugar_reduction_pct"] * 0.007)
        ldl_reduction = (inputs["exercise_days_per_week"] * 2.5) + (inputs["caloric_deficit_kcal"] * 0.012)

        return {
            "timeframe": "90 Days",
            "projected_metrics": {
                "fasting_glucose": {"baseline": curr_fbs, "projected": max(80.0, round(curr_fbs - fbs_reduction, 1))},
                "hba1c": {"baseline": curr_hba1c, "projected": max(4.8, round(curr_hba1c - hba1c_reduction, 2))},
                "ldl_cholesterol": {"baseline": curr_ldl, "projected": max(70.0, round(curr_ldl - ldl_reduction, 1))}
            },
            "status": "Trajectory shifts toward optimal physiological reference range."
        }
