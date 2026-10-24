from datetime import datetime
from typing import Dict, Any, List, Optional

class HandoffEngine:
    """
    Source-Grounded Clinical Handoff & Physician Briefing Engine.
    Structures handoffs strictly around verified observations, confirmed active regimens,
    and explicit patient-reported inputs. Never assumes diagnoses or baseline biomarkers.
    """

    @staticmethod
    def build_source_grounded_handoff(patient_data: Dict[str, Any], records: List[Any]) -> Dict[str, Any]:
        """
        Builds a comprehensive, owner-scoped clinical briefing from authentic documents and observations.
        """
        patient_id = patient_data.get("id") or patient_data.get("user_id") or "Unspecified ID"
        user_email = patient_data.get("email") or "Unspecified Email"

        if not records:
            return {
                "document_type": "CLINICAL_HANDOFF_BRIEFING",
                "status": "INCOMPLETE",
                "patient_context": {
                    "patient_id": patient_id,
                    "email": user_email
                },
                "generated_at": datetime.utcnow().isoformat(),
                "message": "Not available — no source records or uploaded documents available in vault to construct handoff.",
                "documented_observations": [],
                "unverified_fields": ["Allergies", "Active Prescriptions", "Prior Medical History"],
                "consent_notice": "Requires explicit patient authorization before exporting or transmitting to receiving clinical team."
            }

        # Normalize across ORM objects (ClinicalObservation/SourceDocument) or legacy dictionaries
        extracted_highlights = []
        hospital_encounters = set()
        unverified_fields = []

        for r in records:
            # Handle ORM ClinicalObservation instances
            if hasattr(r, "analyte_as_written"):
                dt = r.effective_date.strftime("%Y-%m-%d") if getattr(r, "effective_date", None) else "Undated on report"
                unit = r.original_unit or ""
                src_name = r.source_doc.filename if getattr(r, "source_doc", None) else "Direct Entry"
                ref_txt = f" (Ref: {r.printed_reference_range})" if r.printed_reference_range else ""
                extracted_highlights.append(f"{r.analyte_as_written}: {r.original_value} {unit}{ref_txt} [Observed: {dt}, Source: {src_name}]")
                if getattr(r, "source_doc", None) and r.source_doc.facility_name:
                    hospital_encounters.add(f"{dt}: {r.source_doc.facility_name}")

            # Handle legacy report dictionaries with 'biomarkers' map
            elif isinstance(r, dict):
                dt = r.get("diagnosis_date") or r.get("report_date") or "Undated"
                hosp = r.get("hospital_name")
                if hosp and hosp != "Not stated on report":
                    hospital_encounters.add(f"{dt}: {hosp}")

                biomarkers = r.get("biomarkers", {})
                for k, v in biomarkers.items():
                    val = v.get("value") if isinstance(v, dict) else v
                    unit = v.get("unit", "") if isinstance(v, dict) else ""
                    extracted_highlights.append(f"{k}: {val} {unit} [Date: {dt}]")

        # Patient demographic details (never assume defaults)
        age = patient_data.get("age")
        gender = patient_data.get("gender")
        demographics = {}
        if age is not None:
            demographics["age"] = age
        else:
            unverified_fields.append("Age (Not documented)")

        if gender:
            demographics["gender"] = gender
        else:
            unverified_fields.append("Gender (Not documented)")

        # Prescriptions & Supplements verification
        prescriptions = patient_data.get("active_prescriptions") or patient_data.get("prescriptions") or []
        supplements = patient_data.get("active_supplements") or patient_data.get("supplements") or []
        
        if not prescriptions:
            unverified_fields.append("Active Prescriptions (Self-report or clinician review required)")
        if not supplements:
            unverified_fields.append("Supplements / Vitamins (None documented)")
        unverified_fields.append("Allergies (Requires explicit confirmation)")

        # Action points grounded strictly in recorded data
        action_checklist = [
            "Review verified observations and compare with external laboratory records.",
            "Confirm active prescriptions and allergies directly with patient during intake."
        ]
        if any("Undated" in item for item in extracted_highlights):
            action_checklist.append("Clarify specimen collection dates on undated or ambiguous laboratory reports.")

        return {
            "document_type": "CLINICAL_HANDOFF_BRIEFING",
            "status": "VERIFIED_SOURCE_GROUNDED",
            "generated_at": datetime.utcnow().isoformat(),
            "patient_context": {
                "patient_id": patient_id,
                "email": user_email,
                **demographics
            },
            "active_regimen": {
                "prescriptions": prescriptions if prescriptions else ["None documented in vault"],
                "supplements": supplements if supplements else ["None documented in vault"]
            },
            "documented_encounters": list(hospital_encounters) if hospital_encounters else ["No diagnostic facility names specified on reports"],
            "longitudinal_highlights": extracted_highlights[:15] if extracted_highlights else ["Zero clinical observations on record"],
            "doctor_action_checklist": action_checklist,
            "unverified_fields": unverified_fields,
            "consent_notice": "Requires explicit patient authorization before exporting or transmitting to receiving clinical team."
        }

    @classmethod
    def build_doctor_briefing(cls, patient_data: dict, records: list) -> dict:
        """
        Backwards-compatible alias for existing export routes (e.g., routes/export.py).
        Translates to the verified source-grounded format without inventing values.
        """
        handoff = cls.build_source_grounded_handoff(patient_data, records)
        
        # Preserve legacy top-level keys for export template rendering
        handoff["document"] = "HELIX CLINICAL 1-PAGE SUMMARY"
        handoff["timestamp"] = handoff["generated_at"]
        handoff["patient"] = handoff["patient_context"]
        handoff["prescriptions"] = handoff["active_regimen"]["prescriptions"]
        handoff["supplements"] = handoff["active_regimen"]["supplements"]
        handoff["hospital_encounters"] = handoff["documented_encounters"]
        return handoff