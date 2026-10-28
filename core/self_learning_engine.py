# core/self_learning_engine.py
import json
import os
from datetime import datetime
from typing import Optional

STORE_FILE = "self_learning_knowledge_store.json"

class SelfLearningEngine:
    @staticmethod
    def _load_store():
        if os.path.exists(STORE_FILE):
            try:
                with open(STORE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"corrections": [], "verified_patterns": {}, "confidence_weights": {}}

    @staticmethod
    def _save_store(data):
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def record_interaction(cls, analyte: str, value: str, unit: str, explanation: str, user_corrected: bool = False):
        store = cls._load_store()
        key = analyte.strip().lower()

        if key not in store["verified_patterns"]:
            store["verified_patterns"][key] = []

        store["verified_patterns"][key].append({
            "value": value,
            "unit": unit,
            "explanation": explanation,
            "timestamp": datetime.utcnow().isoformat(),
            "user_corrected": user_corrected
        })

        current_weight = store["confidence_weights"].get(key, 1.0)
        store["confidence_weights"][key] = current_weight + (0.1 if not user_corrected else -0.2)

        cls._save_store(store)

    @classmethod
    def get_local_knowledge(cls, analyte: str) -> Optional[str]:
        store = cls._load_store()
        key = analyte.strip().lower()
        patterns = store.get("verified_patterns", {}).get(key, [])
        if patterns:
            return patterns[-1].get("explanation")
        return None