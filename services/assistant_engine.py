class HealthAssistantEngine:
    @staticmethod
    def process_query(question: str) -> dict:
        q = question.lower()
        if any(w in q for w in ["sugar", "glucose", "hba1c"]):
            ans = "Per ADA guidelines: Fasting glucose > 100 mg/dL or HbA1c 5.7%-6.4% indicates prediabetes. Consistent sleep, resistance/aerobic exercise, and complex carbohydrates optimize insulin sensitivity."
        elif any(w in q for w in ["cholesterol", "ldl", "lipid"]):
            ans = "Per AHA guidelines: Increasing soluble fiber (oats, legumes, flaxseeds) and lowering saturated fatty acids mitigates elevated LDL profiles."
        else:
            ans = "Helix aligns your dynamic biomarker trajectory against established clinical health guidelines."

        return {
            "clinical_response": ans,
            "safety_guardrail": "⚠️ Helix is a supportive health companion, not an autonomous physician. Always consult your doctor for diagnosis and clinical prescriptions."
        }
