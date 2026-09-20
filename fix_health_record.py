import os

orm_path = os.path.join("models", "orm.py")

with open(orm_path, "r", encoding="utf-8") as f:
    orm_content = f.read()

if "class HealthRecord" not in orm_content:
    model_code = """

class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    biomarker_name = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=True)
"""
    with open(orm_path, "a", encoding="utf-8") as f:
        f.write(model_code)
    print("✅ Appended HealthRecord model to models/orm.py")
else:
    print("ℹ️ HealthRecord already present in models/orm.py")
