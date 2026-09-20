from typing import Dict, Any, List
import uuid
from datetime import datetime

class FHIRExporter:
    @staticmethod
    def generate_patient_bundle(user_data: Dict[str, Any], lab_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Exports user clinical health records as a valid HL7 FHIR R4 Transaction Bundle.
        """
        bundle_id = str(uuid.uuid4())
        patient_id = str(user_data.get("id", "patient-001"))
        timestamp = datetime.utcnow().isoformat() + "Z"

        entries = [
            {
                "fullUrl": f"urn:uuid:{patient_id}",
                "resource": {
                    "resourceType": "Patient",
                    "id": patient_id,
                    "gender": user_data.get("gender", "unknown"),
                    "birthDate": user_data.get("birth_date", "1990-01-01")
                },
                "request": {"method": "PUT", "url": f"Patient/{patient_id}"}
            }
        ]

        for lab in lab_results:
            for marker, val in lab.get("biomarkers", {}).items():
                obs_id = str(uuid.uuid4())
                entries.append({
                    "fullUrl": f"urn:uuid:{obs_id}",
                    "resource": {
                        "resourceType": "Observation",
                        "id": obs_id,
                        "status": "final",
                        "code": {"text": marker},
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "valueQuantity": {"value": val}
                    },
                    "request": {"method": "POST", "url": "Observation"}
                })

        return {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "transaction",
            "timestamp": timestamp,
            "entry": entries
        }
