# Helix: Enterprise Health Intelligence & Metabolic Decision Support OS

Helix is a source-grounded health intelligence platform that unifies multi-hospital diagnostic records, calculates biomarker velocity, simulates 90-day metabolic recovery trajectories, and generates HL7 FHIR-compliant clinical summaries.

## Core Features
- **Dynamic OCR & Biomarker Registry**: Parses lab reports across clinics with standard LOINC entity mapping.
- **90-Day Metabolic Twin Simulator**: Mathematical glycemic and lipid recovery forecasting based on caloric deficit and resistance exercise.
- **Panic Alert & Drug Toxicity Shield**: Flags critical clinical values and active medication contraindications (e.g., Metformin renal clearance checks).
- **HL7 FHIR Interoperability**: One-click standard JSON Observation bundle exporter for hospital EMRs.
- **Tri-Lingual Localization**: Native translation across English, Hindi, and Marathi.
- **Neuro-Somatic Studio**: 4-4-4-4 Box Breathing vagal pacer and Circadian Cortisol curve modeling.

## Tech Stack
- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite / Async SQLAlchemy
- **Frontend**: HTML5, Vanilla JavaScript, Bootstrap 5, Chart.js

## Getting Started
```bash
# Install dependencies
pip install fastapi uvicorn sqlalchemy aiosqlite pypdf pillow

# Run the local server
uvicorn main:app --reload --port 8000
