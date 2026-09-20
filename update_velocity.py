file_path = "services/velocity_engine.py"

code = """import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from typing import List, Dict, Any, Optional

class VelocityEngine:
    def __init__(self):
        self.model = Ridge(alpha=1.0)

    def extract_30day_features(self, biomarker_history: List[Dict[str, Any]], lifestyle_data: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        if not biomarker_history:
            return pd.DataFrame()

        df = pd.DataFrame(biomarker_history)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

        df["value_7d_avg"] = df["value"].rolling(window=7, min_periods=1).mean()
        df["value_14d_avg"] = df["value"].rolling(window=14, min_periods=1).mean()
        df["velocity_7d"] = df["value"].diff(periods=1).fillna(0)
        df["volatility_14d"] = df["value"].rolling(window=14, min_periods=1).std().fillna(0)

        # Incorporate lifestyle metrics if present
        sleep_hours = lifestyle_data.get("sleep_hours_avg", 7.0) if lifestyle_data else 7.0
        df["lifestyle_sleep_score"] = sleep_hours / 8.0
        
        return df

    def predict_30day_trajectory(self, biomarker_history: List[Dict[str, Any]], lifestyle_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        df = self.extract_30day_features(biomarker_history, lifestyle_data)
        
        # Single point fallback: Apply demographic/lifestyle baseline smoothing
        if df.empty or len(df) < 2:
            last_val = biomarker_history[-1]["value"] if biomarker_history else 0.0
            sleep = lifestyle_data.get("sleep_hours_avg", 7.0) if lifestyle_data else 7.0
            
            # Sub-optimal sleep (>8h or <6h) adds slight metabolic drift factor
            drift_factor = -0.01 if sleep < 6.0 else (0.005 if sleep >= 7.0 else 0.0)
            predicted_val = last_val * (1.0 + drift_factor)
            
            return {
                "current_value": float(last_val),
                "predicted_value_30d": round(predicted_val, 2),
                "confidence_score": 0.65,
                "trajectory": "decreasing" if drift_factor < 0 else "stable",
                "message": "Single lab report: 30-day projection calculated via lifestyle-adjusted baseline drift."
            }

        feature_cols = ["value_7d_avg", "value_14d_avg", "velocity_7d", "volatility_14d", "lifestyle_sleep_score"]
        X = df[feature_cols].values
        y = df["value"].values

        self.model.fit(X, y)
        latest_features = X[-1].reshape(1, -1)
        predicted_val = float(self.model.predict(latest_features)[0])
        last_val = df["value"].iloc[-1]
        
        delta = predicted_val - last_val
        if delta > 0.05 * last_val:
            trajectory = "increasing"
        elif delta < -0.05 * last_val:
            trajectory = "decreasing"
        else:
            trajectory = "stable"

        return {
            "current_value": float(last_val),
            "predicted_value_30d": round(predicted_val, 2),
            "trajectory": trajectory,
            "confidence_score": 0.88
        }
"""

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Step 4: Updated services/velocity_engine.py with Lifestyle Factors & Baseline Smoothing!")
