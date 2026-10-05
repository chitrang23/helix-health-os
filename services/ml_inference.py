import os
import joblib
import numpy as np

MODEL_PATH = "models/clinical_risk_model.pkl"

class TrainedClinicalPredictor:
    @staticmethod
    def predict_risk(labs: dict) -> dict:
        if not os.path.exists(MODEL_PATH):
            return {"error": "Trained model not found. Run train_model.py first."}
        try:
            model = joblib.load(MODEL_PATH)
            g = float(labs.get("glucose", 95.0))
            h = float(labs.get("hba1c", 5.5))
            c = float(labs.get("creatinine", 0.9))
            p = float(labs.get("potassium", 4.0))
            features = np.array([[g, h, c, p]])
            prediction = int(model.predict(features)[0])
            probabilities = model.predict_proba(features)[0]
            risk_probability = float(probabilities[1])
            return {
                "model_type": "RandomForestClassifier (Locally Trained)",
                "is_high_risk": bool(prediction == 1),
                "critical_risk_probability": round(risk_probability * 100, 2),
                "risk_label": "CRITICAL EMERGENCY - IMMEDIATE ACTION REQUIRED" if prediction == 1 else "STABLE - BASELINE PARAMETERS NORMAL"
            }
        except Exception as e:
            return {"error": str(e)}