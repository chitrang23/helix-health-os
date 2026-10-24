# tests/test_audit_and_security.py
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from core.database import get_db
from models.orm import Base, User, ClinicalObservation, DrugRuleModel
from core.security import get_password_hash, create_access_token

# Use a clean, isolated SQLite test database
TEST_DATABASE_URL = "sqlite:///./test_helix.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def prepare_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()
    # 1. Create Patient A
    user_a = User(
        username="patient_a",
        email="patient_a@test.com",
        hashed_password=get_password_hash("ValidPass123!"),
        role="patient",
        is_active=True
    )
    # 2. Create Patient B
    user_b = User(
        username="patient_b",
        email="patient_b@test.com",
        hashed_password=get_password_hash("ValidPass456!"),
        role="patient",
        is_active=True
    )
    db.add_all([user_a, user_b])
    db.commit()

    # 3. Seed verified drug interaction safety rule
    rule = DrugRuleModel(
        rule_type="drug_drug",
        trigger_a="warfarin",
        trigger_b="aspirin",
        severity="danger",
        pair_label="Warfarin + Aspirin",
        mechanism="Substantial bleeding risk elevation when combined.",
        is_active=True
    )
    db.add(rule)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


def test_empty_account_shows_zero_fake_data():
    """Verifies that an empty account returns zero synthetic/demo points."""
    token_a = create_access_token({"sub": "patient_a@test.com"})
    res = client.get(
        "/api/metrics/history?test_name=Hemoglobin",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["data_points"] == []
    assert data["history"] == []
    assert "no source data provided" in data["provenance"].lower()


def test_idor_cross_patient_isolation():
    """Verifies that Patient A cannot access Patient B's observations."""
    db = TestingSessionLocal()
    user_b = db.query(User).filter(User.email == "patient_b@test.com").first()
    
    obs_b = ClinicalObservation(
        user_id=user_b.id,
        analyte_as_written="Fasting Blood Glucose",
        original_value="142",
        normalized_numeric_value=142.0,
        original_unit="mg/dL",
        data_source_type="document_extraction",
        extraction_method="ocr_digital",
        confidence_score=0.98
    )
    db.add(obs_b)
    db.commit()
    db.close()

    # Patient A queries glucose -> Must receive 0 points (No cross-tenant leak)
    token_a = create_access_token({"sub": "patient_a@test.com"})
    res_a = client.get(
        "/api/metrics/history?test_name=Fasting Blood Glucose",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_a.status_code == 200
    assert len(res_a.json()["data_points"]) == 0

    # Patient B queries glucose -> Receives their authentic observation
    token_b = create_access_token({"sub": "patient_b@test.com"})
    res_b = client.get(
        "/api/metrics/history?test_name=Fasting Blood Glucose",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b.status_code == 200
    assert len(res_b.json()["data_points"]) == 1
    assert res_b.json()["data_points"][0]["raw_value"] == "142"


def test_unauthenticated_requests_blocked():
    """Verifies that requests without a Bearer token are rejected."""
    res = client.get("/api/metrics/history?test_name=Hemoglobin")
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_soap_notes_empty_account_honesty():
    """Verifies SOAP notes show unavailable states when observations are missing."""
    token_a = create_access_token({"sub": "patient_a@test.com"})
    res = client.get("/api/soap/generate", headers={"Authorization": f"Bearer {token_a}"})
    if res.status_code == 404:
        # Fallback check in case the route is mounted at /notes
        res = client.get("/api/soap/notes", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert "not available" in data["objective"][0].lower()


def test_drug_safety_rule_evaluation():
    """Verifies safety engine flags real contraindications without inventing data."""
    token_a = create_access_token({"sub": "patient_a@test.com"})
    res = client.post(
        "/api/drug-safety/audit",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"medications": ["Warfarin 5mg", "Aspirin 81mg"], "supplements": []}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["interactions_found"] is True
    assert any("Warfarin + Aspirin" in f["combination"] for f in data["findings"])