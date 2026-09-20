from typing import Dict, Any

class TranslationEngine:
    def translate_report(self, biomarker_key: str, value: float, mode: str = "simple") -> str:
        """
        Translates biomarker clinical values into plain explanations based on health literacy levels.
        Modes: 'simple', 'detailed', 'clinical'
        """
        key_clean = biomarker_key.lower()
        
        explanations = {
            "fasting_glucose": {
                "simple": f"Your fasting blood sugar is {value}. This measures how much sugar is in your blood after not eating.",
                "detailed": f"Fasting glucose is {value} mg/dL. Values above 100 mg/dL indicate early insulin resistance.",
                "clinical": f"Fasting plasma glucose recorded at {value} mg/dL. Assess glycemic control and impaired fasting glucose (IFG) thresholds."
            },
            "hba1c": {
                "simple": f"Your HbA1c is {value}%. This shows your average blood sugar levels over the past 3 months.",
                "detailed": f"HbA1c is {value}%. A level between 5.7% and 6.4% indicates prediabetes.",
                "clinical": f"Glycated hemoglobin (HbA1c) measured at {value}%. Evaluates long-term glycemic state and diabetes management."
            }
        }

        if key_clean in explanations:
            return explanations[key_clean].get(mode, explanations[key_clean]["simple"])
        
        return f"{biomarker_key} recorded at {value}."
