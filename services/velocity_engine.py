from typing import List, Dict

class VelocityEngine:
    @staticmethod
    def calculate_longitudinal_trajectory(records: List[dict]) -> Dict[str, dict]:
        if len(records) < 2:
            return {"status": "insufficient_data", "message": "At least 2 reports required for velocity analysis"}

        sorted_records = sorted(records, key=lambda x: x["record_date"])
        first_rec = sorted_records[0]
        latest_rec = sorted_records[-1]

        days_delta = (latest_rec["record_date"] - first_rec["record_date"]).days
        months = max(days_delta / 30.43, 0.5)

        velocity_results = {}
        for marker, current_val in latest_rec["biomarkers"].items():
            if marker in first_rec["biomarkers"]:
                base_val = first_rec["biomarkers"][marker]
                net_change = round(current_val - base_val, 2)
                rate_per_month = round(net_change / months, 3)

                trend = "stable"
                if rate_per_month > 0.05:
                    trend = "accelerating_upwards"
                elif rate_per_month < -0.05:
                    trend = "declining"

                velocity_results[marker] = {
                    "baseline": base_val,
                    "current": current_val,
                    "net_change": net_change,
                    "rate_per_month": rate_per_month,
                    "trend": trend
                }
        return {"tracking_months": round(months, 1), "velocities": velocity_results}
