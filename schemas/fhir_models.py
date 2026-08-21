from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Coding(BaseModel):
    system: str = "http://loinc.org"
    code: str
    display: str

class CodeableConcept(BaseModel):
    coding: List[Coding]

class Quantity(BaseModel):
    value: float
    unit: str
    system: str = "http://unitsofmeasure.org"

class ReferenceRange(BaseModel):
    low: Optional[Quantity] = None
    high: Optional[Quantity] = None
    text: Optional[str] = None

class FHIRObservation(BaseModel):
    resourceType: str = "Observation"
    id: str
    status: str = "final"
    code: CodeableConcept
    subject: Dict[str, str] = Field(..., example={"reference": "Patient/helix-u-1092"})
    effectiveDateTime: str
    valueQuantity: Quantity
    referenceRange: Optional[List[ReferenceRange]] = None
    interpretation: Optional[List[Dict[str, Any]]] = None

class ClinicalSBAR(BaseModel):
    patient_id: str
    encounter_timestamp: str
    situation: str = Field(..., description="Acute symptom presentation and trigger threshold")
    background: Dict[str, Any] = Field(..., description="Active prescriptions, LOINC lab history, baseline comorbidities")
    assessment: Dict[str, Any] = Field(..., description="Velocity analysis, organ filtration status, drug-lab interactions")
    recommendation: List[str] = Field(..., description="Actionable clinical queries and specialist consult requests")
