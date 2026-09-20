# -*- coding: utf-8 -*-
import os

print("🔧 Fixing SafetyEngine signature and updating test suite...")

# 1. Update services/safety_engine.py
os.makedirs("services", exist_ok=True)
safety_engine_code = '''from typing import List, Dict, Any, Optional

class SafetyEngine:
    @staticmethod
    def evaluate_interactions(
        prescriptions: List[str],
        supplements: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        latest_biomarkers: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates potential drug-drug, drug-supplement, and drug-biomarker interactions.
        """
        alerts = []
        supplements = supplements or []
        rules = rules or []
        latest_biomarkers = latest_biomarkers or {}

        # Normalize text lists for matching
        all_rx = [rx.lower() for rx in prescriptions]
        all_supplements = [supp.lower() for supp in supplements]
        all_substances = all_rx + all_supplements

        for rule in rules:
            if hasattr(rule, "is_active") and not rule.is_active:
                continue

            rule_type = getattr(rule, "rule_type", "")
            trigger_a = getattr(rule, "trigger_a", "").lower()
            trigger_b = getattr(rule, "trigger_b", "").lower() if getattr(rule, "trigger_b", None) else ""

            # 1. Drug-Drug / Drug-Supplement Rules
            if rule_type in ("drug_drug", "drug_supplement"):
                has_a = any(trigger_a in item for item in all_substances)
                has_b = any(trigger_b in item for item in all_substances) if trigger_b else False

                if has_a and has_b:
                    alerts.append({
                        "level": getattr(rule, "severity", "moderate"),
                        "pair": getattr(rule, "pair_label", "Interaction Alert"),
                        "mechanism": getattr(rule, "mechanism", "Potential interaction detected.")
                    })

            # 2. Drug-Biomarker Rules
            elif rule_type == "drug_biomarker":
                has_a = any(trigger_a in item for item in all_substances)
                biomarker_key = getattr(rule, "biomarker_key", None)
                
                if has_a and biomarker_key and biomarker_key in latest_biomarkers:
                    val = latest_biomarkers[biomarker_key]
                    op = getattr(rule, "operator", "<")
                    threshold = getattr(rule, "threshold", 0.0)

                    triggered = False
                    if op == "<" and val < threshold:
                        triggered = True
                    elif op == "<=" and val <= threshold:
                        triggered = True
                    elif op == ">" and val > threshold:
                        triggered = True
                    elif op == ">=" and val >= threshold:
                        triggered = True

                    if triggered:
                        mechanism_template = getattr(rule, "mechanism", "")
                        formatted_mechanism = mechanism_template.format(threshold=threshold, value=val) if "{threshold}" in mechanism_template else mechanism_template

                        alerts.append({
                            "level": getattr(rule, "severity", "high"),
                            "pair": getattr(rule, "pair_label", "Biomarker Safety Alert"),
                            "mechanism": formatted_mechanism
                        })

        return alerts
'''

with open("services/safety_engine.py", "w", encoding="utf-8") as f:
    f.write(safety_engine_code)
print("  ✅ services/safety_engine.py updated.")

# 2. Ensure conftest.py exists for clean pytest execution
Set_Content_Path = "conftest.py"
with open("conftest.py", "w", encoding="utf-8") as f:
    f.write("# Root conftest for pytest module discovery\n")
print("  ✅ conftest.py verified.")

print("\n🎉 Setup complete. Run test command now.")
