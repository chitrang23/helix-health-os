import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import Base, engine

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_idor_and_dynamic_flow():
    res_a = client.post("/api/auth/register", json={
        "email": "alice@hospital.org", "password": "SecurePassword123!", "full_name": "Alice M"
    })
    token_a = res_a.json()["access_token"]
    id_a = res_a.json()["user_id"]

    res_b = client.post("/api/auth/register", json={
        "email": "bob@hospital.org", "password": "SecurePassword456!", "full_name": "Bob K"
    })
    token_b = res_b.json()["access_token"]

    unauthorized = client.get(f"/api/records/{id_a}/history", headers={"Authorization": f"Bearer {token_b}"})
    assert unauthorized.status_code == 403

    client.post(
        f"/api/records/{id_a}/manual",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"biomarkers": {"fasting_glucose": 115.0}}
    )

    sim = client.post(
        f"/api/twin/{id_a}/simulate",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"horizon_days": 90, "daily_steps": 10000, "carb_reduction_pct": 25.0, "weekly_cardio_mins": 180}
    )
    assert sim.status_code == 200
    assert sim.json()["projections"]["fasting_glucose"]["projected_final"] < 115.0
