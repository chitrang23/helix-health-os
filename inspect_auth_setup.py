import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

print("--- REGISTERED AUTH ROUTES ---")
for route in main.app.routes:
    if "auth" in getattr(route, "path", "") or "register" in getattr(route, "path", ""):
        print(f"Path: {getattr(route, 'path', '')} | Name: {getattr(route, 'name', '')}")

print("\n--- POST /api/auth/register RESPONSE ---")
res = client.post("/api/auth/register", json={
    "email": "alice@hospital.org", "password": "SecurePassword123!", "full_name": "Alice M"
})
print("Status Code:", res.status_code)
print("JSON Output:", res.json())
