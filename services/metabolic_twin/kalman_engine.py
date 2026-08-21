import numpy as np
from typing import Dict, Tuple

class AdaptiveMetabolicKalmanFilter:
    def __init__(self, dt: float = 1.0):
        self.dt = dt
        # State vector x: [Fasting Glucose, Active Insulin Sensitivity, Allostatic Load Score]
        self.x = np.array([[100.0], [1.0], [5.0]]) 
        
        # State Transition Matrix (F)
        self.F = np.eye(3)
        
        # Process Noise Covariance (Q) - Captures biological variance
        self.Q = np.diag([0.05, 0.001, 0.02])
        
        # Measurement Covariance (R) - Sensor / Lab reading error
        self.R = np.diag([2.0, 0.5])
        self.P = np.eye(3) * 5.0

    def predict(self, caloric_burn: float, resistance_training_minutes: float) -> np.ndarray:
        insulin_sens_boost = 0.005 * (resistance_training_minutes / 30.0)
        hepatic_clearance = -0.02 * (caloric_burn / 500.0)
        
        self.F[0, 1] = hepatic_clearance
        self.F[1, 1] = 1.0 + insulin_sens_boost
        
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, cgm_glucose: float, hrv_stress_proxy: float) -> Tuple[np.ndarray, np.ndarray]:
        z = np.array([[cgm_glucose], [hrv_stress_proxy]])
        H = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0]
        ])
        
        y = z - (H @ self.x)
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)
        
        self.x = self.x + (K @ y)
        self.P = (np.eye(3) - (K @ H)) @ self.P
        return self.x, self.P
