from datetime import datetime

class HandoffEngine:
    @staticmethod
    def build_doctor_briefing(patient_data: dict, records: list) -> dict:
        sorted_records = sorted(records, key=lambda x: x.record_date)
        first = sorted_records[0]
        latest = sorted_records[-1]

        return {
            "document": "HELIX CLINICAL 1-PAGE SUMMARY",
            "timestamp": datetime.utcnow().isoformat(),
            "patient": {
                "id": patient_data["id"],
                "name": patient_data["name"],
                "age": patient_data["age"],
                "gender": patient_data["gender"]
            },
            "prescriptions": patient_data["active_prescriptions"],
            "supplements": patient_data["active_supplements"],
            "hospital_encounters": [f"{r.record_date.strftime('%Y-%m-%d')}: {r.hospital_name}" for r in sorted_records],
            "longitudinal_highlights": [
                f"Fasting Glucose: {first.biomarkers.get('fasting_glucose')} -> {latest.biomarkers.get('fasting_glucose')} mg/dL",
                f"HbA1c: {first.biomarkers.get('hba1c')}% -> {latest.biomarkers.get('hba1c')}%"
            ],
            "doctor_action_checklist": [
                "Evaluate upward glycemic velocity trend.",
                "Review Metformin timing relative to supplements.",
                "Order comprehensive metabolic panel if trajectory persists."
            ]
        }
