import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

print("Initializing Custom Clinical Machine Learning Training Pipeline...")

# 1. Ensure models directory exists
os.makedirs("models", exist_ok=True)
model_path = "models/clinical_risk_model.pkl"

def train_and_save_model():
    print("Generating synthetic clinical training dataset...")
    np.random.seed(42)
    n_samples = 2000
    
    # Features: [glucose, hba1c, creatinine, potassium]
    glucose = np.random.normal(100, 35, n_samples).clip(40, 450)
    hba1c = np.random.normal(5.6, 1.2, n_samples).clip(3.5, 15.0)
    creatinine = np.random.normal(0.9, 0.4, n_samples).clip(0.4, 6.0)
    potassium = np.random.normal(4.2, 0.6, n_samples).clip(2.5, 7.0)
    
    X = np.column_stack((glucose, hba1c, creatinine, potassium))
    
    # Target definition: 1 if any marker is in critical panic range, 0 otherwise
    y = []
    for g, h, c, p in X:
        is_critical = (g < 60 or g > 250) or (h > 8.5) or (c > 1.8) or (p < 3.0 or p > 6.0)
        y.append(1 if is_critical else 0)
    y = np.array(y)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Classifier for Clinical Triage...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    accuracy = clf.score(X_test, y_test)
    print(f"Model trained successfully! Test Accuracy: {accuracy * 100:.2f}%")
    
    # Save model artifact
    joblib.dump(clf, model_path)
    print(f"Trained model artifact saved to {model_path}")

if __name__ == "__main__":
    train_and_save_model()
