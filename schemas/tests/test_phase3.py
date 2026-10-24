import pytest
from services.fhir_exporter import FHIRExporter
from services.analytics_engine import AnalyticsEngine

def test_fhir_bundle_generation():
    user = {"id": 101, "gender": "male", "birth_date": "2000-01-01"}
    labs = [{"biomarkers": {"eGFR": 90.0, "HbA1c": 5.6}}]
    bundle = FHIRExporter.generate_patient_bundle(user, labs)
    
    assert bundle["resourceType"] == "Bundle"
    assert len(bundle["entry"]) == 3  # 1 Patient + 2 Observations

def test_biomarker_trend_analysis():
    history = [
        {"biomarkers": {"HbA1c": 5.2}},
        {"biomarkers": {"HbA1c": 5.8}}
    ]
    res = AnalyticsEngine.analyze_biomarker_trends(history)
    assert res["HbA1c"]["trend_status"] == "increasing"
    assert res["HbA1c"]["delta_percentage"] > 0
