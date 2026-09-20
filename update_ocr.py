file_path = "services/ocr_engine.py"

code = """from typing import Dict, Any, List

CANONICAL_BIOMARKER_MAP = {
    "fbs": "fasting_glucose",
    "fasting blood sugar": "fasting_glucose",
    "fasting glucose": "fasting_glucose",
    "hba1c": "hba1c",
    "glycated hemoglobin": "hba1c",
    "tsh": "tsh",
    "thyroid stimulating hormone": "tsh",
    "total cholesterol": "total_cholesterol",
    "cholesterol": "total_cholesterol"
}

UNIT_CONVERSIONS = {
    "fasting_glucose": {
        "mmol/l": lambda x: round(x * 18.0182, 2)  # Convert mmol/L to mg/dL
    }
}

class OCREngine:
    def normalize_biomarker_name(self, raw_name: str) -> str:
        clean = raw_name.strip().lower()
        return CANONICAL_BIOMARKER_MAP.get(clean, clean.replace(" ", "_"))

    def normalize_value_and_unit(self, canonical_name: str, value: float, unit: str) -> Dict[str, Any]:
        unit_clean = unit.strip().lower() if unit else ""
        if canonical_name in UNIT_CONVERSIONS and unit_clean in UNIT_CONVERSIONS[canonical_name]:
            normalized_val = UNIT_CONVERSIONS[canonical_name][unit_clean](value)
            return {"value": normalized_val, "unit": "mg/dL", "converted": True}
        return {"value": value, "unit": unit, "converted": False}

    def parse_extracted_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        parsed = {}
        for k, v in raw_data.items():
            canonical_key = self.normalize_biomarker_name(k)
            if isinstance(v, dict) and "value" in v:
                norm = self.normalize_value_and_unit(canonical_key, float(v["value"]), v.get("unit", ""))
                parsed[canonical_key] = norm
            elif isinstance(v, (int, float)):
                parsed[canonical_key] = {"value": float(v), "unit": "standard", "converted": False}
        return parsed
"""

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Step 1: Updated services/ocr_engine.py with Canonical Mapping & Unit Normalization!")
