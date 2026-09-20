import os

orm_path = os.path.join("models", "orm.py")

with open(orm_path, "r", encoding="utf-8") as f:
    orm_content = f.read()

if "class SimulationCoefficient" not in orm_content:
    model_code = """

class SimulationCoefficient(Base):
    __tablename__ = "simulation_coefficients"

    id = Column(Integer, primary_key=True, index=True)
    biomarker_name = Column(String, nullable=False, index=True)
    target_biomarker = Column(String, nullable=False)
    coefficient = Column(Float, default=0.0)
    intercept = Column(Float, default=0.0)
"""
    with open(orm_path, "a", encoding="utf-8") as f:
        f.write(model_code)
    print("✅ Appended SimulationCoefficient model to models/orm.py")
else:
    print("ℹ️ SimulationCoefficient already present in models/orm.py")

# Update test_engines.py
engine_test_code = """import pytest

def test_engine_imports():
    from services import analytics_engine, fhir_exporter, safety_engine
    assert analytics_engine is not None
    assert fhir_exporter is not None
    assert safety_engine is not None

def test_simulation_engine_import():
    from services import simulation_engine
    assert simulation_engine is not None

def test_ocr_pipeline_import():
    from services import ocr_pipeline, ocr_engine
    assert ocr_pipeline is not None
    assert ocr_engine is not None
"""

with open(os.path.join("tests", "test_engines.py"), "w", encoding="utf-8") as f:
    f.write(engine_test_code)

print("✅ Updated tests/test_engines.py")
