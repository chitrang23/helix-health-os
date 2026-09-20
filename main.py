import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine, SessionLocal
from services.knowledge_seeder import seed_db_if_empty

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Helix Health Intelligence Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_session = SessionLocal()
try:
    seed_db_if_empty(db_session)
finally:
    db_session.close()

@app.get("/")
def read_root():
    return {"status": "Helix Engine Online", "version": "1.0.0"}

# Safely register available routers
from routes import auth, records, twin
app.include_router(auth.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(twin.router, prefix="/api")

# Load remaining sub-routers if present
try:
    from routes import export, user, pipeline, symptoms, stress, admin
    app.include_router(export.router, prefix="/api/v1")
    app.include_router(user.router, prefix="/api/v1")
    app.include_router(pipeline.router, prefix="/api/v1")
    app.include_router(symptoms.router, prefix="/api/v1")
    app.include_router(stress.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
except Exception as e:
    print(f"Optional router load note: {e}")
