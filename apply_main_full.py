# -*- coding: utf-8 -*-
with open("main.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

ui_start = content.find('<!DOCTYPE html>')
ui_end = content.find('</html>') + 7
portal_html = content[ui_start:ui_end]

main_full_code = f"""# -*- coding: utf-8 -*-
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from core.config import settings
from core.database import engine, Base, get_db, SessionLocal
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
)
from models.orm import User, LabReport, BiomarkerRegistryModel, DrugRuleModel
from services.knowledge_seeder import seed_db_if_empty

Base.metadata.create_all(bind=engine)

with SessionLocal() as db_session:
    seed_db_if_empty(db_session)

app = FastAPI(title="Helix Enterprise Health OS", version="9.1.0-dynamic")

cors_origins = getattr(settings, "ALLOWED_CORS_ORIGINS", None) or getattr(settings, "cors_origin_list", ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user

def assert_owns_resource(current_user: User, user_id: str):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: Identity mismatch.")

# --- DYNAMIC KNOWLEDGE BASE LOADERS ---
def get_db_biomarker_registry(db: Session) -> dict:
    records = db.query(BiomarkerRegistryModel).all()
    reg = {{}}
    for r in records:
        reg[r.key] = {{
            "name": r.name,
            "loinc": r.loinc,
            "unit": r.unit,
            "patterns": r.patterns or [],
            "normal_range": (r.normal_low, r.normal_high),
            "panic_limits": (r.panic_low, r.panic_high),
            "guideline": r.guideline,
            "scale_bucket": r.scale_bucket,
            "en": r.translations.get("en", {{}}),
            "hi": r.translations.get("hi", {{}}),
            "mr": r.translations.get("mr", {{}}),
            "symptom_rules": r.symptom_rules or {{}}
        }}
    return reg

def extract_biomarkers_with_registry(text: str, reg: dict) -> dict:
    found = {{}}
    for key, meta in reg.items():
        for pat in meta.get("patterns", []):
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    found[key] = float(m.group(1))
                    break
                except (ValueError, IndexError):
                    continue
    return found

# --- AUTH API ---
@app.post("/api/v1/auth/register")
def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    age: int = Form(30),
    gender: str = Form("Male"),
    dietary_preference: str = Form("Vegetarian"),
    db: Session = Depends(get_db)
):
    clean_email = email.strip().lower()
    if db.query(User).filter(User.email == clean_email).first():
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")

    new_u = User(
        id=f"user_{{uuid.uuid4().hex[:8]}}",
        full_name=full_name.strip(),
        email=clean_email,
        password_hash=hash_password(password),
        age=age,
        gender=gender,
        dietary_preference=dietary_preference,
        active_prescriptions=["Metformin 500mg (Daily)"],
        active_supplements=["Calcium Carbonate 500mg"],
        treatment_history=[]
    )
    db.add(new_u)
    db.commit()
    token = create_access_token({{"sub": new_u.id}})
    return {{
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user_id": new_u.id,
        "full_name": new_u.full_name,
        "email": new_u.email,
    }}

@app.post("/api/v1/auth/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token({{"sub": user.id}})
    return {{
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "age": user.age,
        "gender": user.gender,
        "diet": user.dietary_preference
    }}

# --- HL7 FHIR EXPORTER ---
@app.get("/api/v1/export/fhir/{{user_id}}")
def export_fhir_bundle(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_owns_resource(current_user, user_id)
    reports = db.query(LabReport).filter(LabReport.user_id == current_user.id).order_by(LabReport.record_date.asc()).all()
    reg = get_db_biomarker_registry(db)

    fhir_entries = []
    for r in reports:
        for m_key, val in (r.biomarkers or {{}}).items():
            meta = reg.get(m_key, {{"name": m_key, "loinc": "Unknown", "unit": ""}})
            fhir_entries.append({{
                "resource": {{
                    "resourceType": "Observation",
                    "id": f"obs-{{uuid.uuid4().hex[:8]}}",
                    "status": "final",
                    "code": {{"coding": [{{"system": "http://loinc.org", "code": meta.get("loinc", "Unknown"), "display": meta.get("name", m_key)}}]}},
                    "subject": {{"reference": f"Patient/{{current_user.id}}", "display": current_user.full_name}},
                    "effectiveDateTime": r.record_date.isoformat(),
                    "performer": [{{"display": r.hospital_name}}],
                    "valueQuantity": {{"value": val, "unit": meta.get("unit", ""), "system": "http://unitsofmeasure.org"}}
                }}
            }})

    return JSONResponse(content={{
        "resourceType": "Bundle",
        "type": "collection",
        "id": f"helix-bundle-{{current_user.id}}",
        "timestamp": datetime.utcnow().isoformat(),
        "entry": fhir_entries
    }})

# --- DYNAMIC CLINICAL CARD BUILDER ---
def build_dynamic_card(marker_key: str, value: float, snippet: str, reg: dict) -> dict:
    meta = reg.get(marker_key)
    if not meta:
        return {{
            "key": marker_key,
            "title": {{"en": marker_key.replace('_', ' ').title(), "hi": marker_key, "mr": marker_key}},
            "value": f"{{value}}",
            "unit": "",
            "status": {{"en": "Normal", "hi": "सामान्य", "mr": "सामान्य"}},
            "status_code": "good",
            "is_panic": False,
            "guideline": "Standard Clinical Reference Threshold",
            "what": {{"en": "Clinical parameter recorded in report.", "hi": "रिपोर्ट में दर्ज की गई जांच।", "mr": "अहवालात नोंदवलेली तपासणी."}},
            "summary": {{"en": f"Recorded value is {{value}}.", "hi": f"मान {{value}} दर्ज किया गया है।", "mr": f"मूल्य {{value}} नोंदवले आहे."}},
            "tip": {{"en": "Maintain balanced activity.", "hi": "संतुलित दिनचर्या रखें।", "mr": "नियमित संतुलित आहार ठेवा."}},
            "snippet": snippet
        }}

    min_v, max_v = meta["normal_range"]
    p_min, p_max = meta.get("panic_limits") or (min_v * 0.5, max_v * 2.0)
    is_panic = value < p_min or value > p_max

    if is_panic:
        st_en, st_hi, st_mr, code = "CRITICAL (Panic Alert)", "गंभीर चेतावनी", "गंभीर इशारा", "danger"
        desc_en = f"CRITICAL VALUE: Outside safe human range ({{min_v}} - {{max_v}} {{meta['unit']}})."
        desc_hi = "गंभीर स्थिति: सुरक्षित सीमा से बाहर है। तत्काल डॉक्टर से संपर्क करें।"
        desc_mr = "अत्यंत गंभीर पातळी: सुरक्षित मर्यादेबाहेर आहे. त्वरित डॉक्टरांचा सल्ला घ्या."
    elif value < min_v:
        st_en, st_hi, st_mr, code = "Low", "कम", "कमी", "danger"
        desc_en = meta["en"].get("low", "")
        desc_hi = meta["hi"].get("low", "")
        desc_mr = meta["mr"].get("low", "")
    elif value > max_v:
        st_en, st_hi, st_mr, code = "High", "अधिक", "जास्त", "warn"
        desc_en = meta["en"].get("high", "")
        desc_hi = meta["hi"].get("high", "")
        desc_mr = meta["mr"].get("high", "")
    else:
        st_en, st_hi, st_mr, code = "Normal (Optimal Range)", "सामान्य", "सामान्य", "good"
        desc_en = f"Within normal reference limit ({{min_v}} - {{max_v}} {{meta['unit']}})."
        desc_hi = f"सुरक्षित सीमा ({{min_v}} - {{max_v}} {{meta['unit']}}) के भीतर है।"
        desc_mr = f"सुरक्षित मर्यादेत ({{min_v}} - {{max_v}} {{meta['unit']}}) आहे."

    return {{
        "key": marker_key,
        "title": {{"en": meta["name"], "hi": meta["hi"].get("what", meta["name"])[:30], "mr": meta["mr"].get("what", meta["name"])[:30]}},
        "value": f"{{value}} {{meta['unit']}}",
        "unit": meta["unit"],
        "normal_range": f"{{min_v}} - {{max_v}} {{meta['unit']}}",
        "raw_num": value,
        "is_panic": is_panic,
        "loinc": meta.get("loinc", "N/A"),
        "guideline": meta.get("guideline", "WHO/ADA Clinical Guideline"),
        "status": {{"en": st_en, "hi": st_hi, "mr": st_mr}},
        "status_code": code,
        "what": {{"en": meta["en"].get("what", ""), "hi": meta["hi"].get("what", ""), "mr": meta["mr"].get("what", "")}},
        "summary": {{"en": desc_en, "hi": desc_hi, "mr": desc_mr}},
        "tip": {{"en": meta["en"].get("tip", ""), "hi": meta["hi"].get("tip", ""), "mr": meta["mr"].get("tip", "")}},
        "snippet": snippet
    }}

def audit_drug_shields_from_db(db: Session, user: User, latest_biomarkers: dict) -> list:
    rules = db.query(DrugRuleModel).all()
    user_rx = [str(x).lower() for x in (user.active_prescriptions or [])]
    user_supp = [str(x).lower() for x in (user.active_supplements or [])]
    all_meds = user_rx + user_supp

    shields = []
    for r in rules:
        if r.rule_type in ("drug_supplement", "drug_drug"):
            match_a = any(r.trigger_a in med for med in all_meds)
            match_b = any(r.trigger_b in med for med in all_meds) if r.trigger_b else False
            if match_a and match_b:
                shields.append({{
                    "severity": r.severity,
                    "drug": r.pair_label,
                    "biomarker": "Pharmacological Interaction",
                    "warning": r.mechanism
                }})
        elif r.rule_type == "drug_biomarker":
            match_a = any(r.trigger_a in med for med in all_meds)
            if match_a and r.biomarker_key in latest_biomarkers:
                val = latest_biomarkers[r.biomarker_key]
                violation = False
                if r.operator == ">" and val > r.threshold:
                    violation = True
                elif r.operator == "<" and val < r.threshold:
                    violation = True

                if violation:
                    shields.append({{
                        "severity": r.severity,
                        "drug": r.pair_label,
                        "biomarker": f"{{r.biomarker_key}} ({{val}})",
                        "warning": r.mechanism.replace("{{threshold}}", str(r.threshold)).replace("{{value}}", str(val))
                    }})
    return shields

# --- TELEMETRY SUMMARY ---
@app.get("/api/v1/user/summary/{{user_id}}")
def get_user_summary(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_owns_resource(current_user, user_id)
    reg = get_db_biomarker_registry(db)
    reports = db.query(LabReport).filter(LabReport.user_id == current_user.id).order_by(LabReport.record_date.asc()).all()
    
    latest_report = reports[-1] if reports else None
    dynamic_cards = []
    doctor_questions = []

    if latest_report and latest_report.biomarkers:
        markers = latest_report.biomarkers
        for m_key, val in markers.items():
            snippet = f"Cited from {{latest_report.hospital_name}}: {{m_key}} = {{val}}"
            card = build_dynamic_card(m_key, val, snippet, reg)
            dynamic_cards.append(card)
            
            meta = reg.get(m_key)
            if meta:
                min_v, max_v = meta["normal_range"]
                if val > max_v or val < min_v:
                    doctor_questions.append({{
                        "biomarker": meta["name"],
                        "finding": f"{{val}} {{meta['unit']}} ({{'Above limit' if val > max_v else 'Below recommended level'}})",
                        "question": {{
                            "en": f"Ask Doctor: Should my treatment for {{meta['name']}} be adjusted?",
                            "hi": f"डॉक्टर से पूछें: क्या {{meta['name']}} के स्तर ({{val}} {{meta['unit']}}) के लिए दवा की आवश्यकता है?",
                            "mr": f"डॉक्टरांना विचारा: {{meta['name']}} ची पातळी ({{val}} {{meta['unit']}}) पाहता उपचारात बदलाची गरज आहे का?"
                        }}
                    }})

    drug_shields = audit_drug_shields_from_db(db, current_user, latest_report.biomarkers if latest_report else {{}})

    all_keys = list({{k for r in reports for k in (r.biomarkers or {{}}).keys()}})[:6]
    chart_datasets = []
    colors = ["#10B981", "#F59E0B", "#EF4444", "#38BDF8", "#A855F7", "#EC4899"]
    
    for idx, k in enumerate(all_keys):
        meta = reg.get(k, {{"name": k.replace('_', ' ').title()}})
        data_pts = [r.biomarkers.get(k, None) if r.biomarkers else None for r in reports]
        is_small = k in ["hba1c", "hemoglobin", "serum_creatinine", "tsh_thyroid", "platelet_count"]
        chart_datasets.append({{
            "label": meta.get("name", k),
            "data": data_pts,
            "borderColor": colors[idx % len(colors)],
            "backgroundColor": colors[idx % len(colors)],
            "yAxisID": "y1" if is_small else "y",
            "tension": 0.35,
            "borderWidth": 3,
            "spanGaps": True
        }})

    return {{
        "user": {{
            "id": current_user.id,
            "name": current_user.full_name,
            "age": current_user.age,
            "gender": current_user.gender,
            "diet": current_user.dietary_preference,
            "email": current_user.email,
            "active_prescriptions": current_user.active_prescriptions or [],
            "active_supplements": current_user.active_supplements or []
        }},
        "hospitals_connected": [r.hospital_name for r in reports],
        "latest_hospital": latest_report.hospital_name if latest_report else "No reports uploaded yet",
        "latest_date": latest_report.record_date.strftime("%d %b %Y") if latest_report else "N/A",
        "total_reports": len(reports),
        "dynamic_cards": dynamic_cards,
        "latest_biomarkers": latest_report.biomarkers if latest_report else {{}},
        "treatments": current_user.treatment_history or [],
        "doctor_questions": doctor_questions,
        "drug_shields": drug_shields,
        "chart_data": {{
            "dates": [r.record_date.strftime("%b %Y") for r in reports],
            "datasets": chart_datasets
        }}
    }}

# --- INGEST REPORT ---
@app.post("/api/v1/pipeline/upload-report")
def upload_user_report(
    user_id: str = Form(...),
    hospital_name: str = Form(...),
    record_date: str = Form(...),
    raw_ocr_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_owns_resource(current_user, user_id)
    try:
        parsed_date = datetime.strptime(record_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="record_date must be in YYYY-MM-DD format.")

    reg = get_db_biomarker_registry(db)
    markers = extract_biomarkers_with_registry(raw_ocr_text or "", reg)
    extraction_failed = len(markers) == 0

    new_report = LabReport(
        id=f"rep_{{uuid.uuid4().hex[:8]}}",
        user_id=current_user.id,
        hospital_name=hospital_name,
        record_date=parsed_date,
        raw_ocr_text=raw_ocr_text,
        biomarkers=markers
    )
    db.add(new_report)
    db.commit()

    return {{
        "status": "success",
        "extracted_biomarkers": markers,
        "extraction_failed": extraction_failed,
        "warning": "Could not automatically read any markers. Please enter manually." if extraction_failed else None,
        "user_id": current_user.id,
    }}

# --- SYMPTOM CORRELATOR VIA DYNAMIC DB RULES ---
@app.post("/api/v1/symptoms/correlate")
def correlate_symptoms(
    symptom: str = Form(...),
    user_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_owns_resource(current_user, user_id)
    reg = get_db_biomarker_registry(db)
    latest = db.query(LabReport).filter(LabReport.user_id == user_id).order_by(LabReport.record_date.desc()).first()
    markers = latest.biomarkers if latest else {{}}
    hosp_name = latest.hospital_name if latest else "Your Report"

    s_lower = symptom.lower().strip()
    correlations = []

    for m_key, val in markers.items():
        meta = reg.get(m_key)
        if not meta or not meta.get("symptom_rules"):
            continue

        s_rule = meta["symptom_rules"]
        min_v, max_v = meta["normal_range"]
        is_high = val > max_v
        is_low = val < min_v

        matched = [kw for kw in s_rule.get("keywords", []) if kw in s_lower]
        if matched:
            if is_high and "high" in s_rule:
                correlations.append({{
                    "biomarker": meta["name"],
                    "value": f"{{val}} {{meta['unit']}}",
                    "status_code": "warn",
                    "status_label": {{"en": "Above Normal", "hi": "सामान्य से अधिक", "mr": "मर्यादेपेक्षा जास्त"}},
                    "source": f"Verified from {{hosp_name}}",
                    "explanation": s_rule["high"]
                }})
            elif is_low and "low" in s_rule:
                correlations.append({{
                    "biomarker": meta["name"],
                    "value": f"{{val}} {{meta['unit']}}",
                    "status_code": "danger",
                    "status_label": {{"en": "Below Normal", "hi": "सामान्य से कम", "mr": "मर्यादेपेक्षा कमी"}},
                    "source": f"Verified from {{hosp_name}}",
                    "explanation": s_rule["low"]
                }})
            else:
                correlations.append({{
                    "biomarker": meta["name"],
                    "value": f"{{val}} {{meta['unit']}}",
                    "status_code": "good",
                    "status_label": {{"en": "Normal & Safe", "hi": "सामान्य और सुरक्षित", "mr": "सामान्य आणि सुरक्षित"}},
                    "source": f"Verified from {{hosp_name}}",
                    "explanation": {{
                        "en": f"Your {{meta['name']}} is normal ({{val}} {{meta['unit']}}), ruling it out as the root cause of '{{symptom}}'.",
                        "hi": f"आपका {{meta['name']}} सामान्य है, इसलिए यह आपके लक्षण '{{symptom}}' का कारण नहीं है।",
                        "mr": f"तुमचे {{meta['name']}} सामान्य आहे, त्यामुळे हे लक्षणांचे मुख्य कारण नाही."
                    }}
                }})

    return {{"symptom": symptom, "correlations": correlations}}

# --- STRESS RECOVERY ENDPOINT ---
@app.post("/api/v1/stress/assess-dynamic")
def assess_dynamic_stress(
    user_id: str = Form(...),
    sleep_hours: float = Form(6.5),
    work_stress: int = Form(7),
    pre_pulse: int = Form(84),
    post_pulse: int = Form(72),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_owns_resource(current_user, user_id)
    latest = db.query(LabReport).filter(LabReport.user_id == user_id).order_by(LabReport.record_date.desc()).first()
    markers = latest.biomarkers if latest else {{}}

    fbs = markers.get("fasting_glucose", 95.0)
    vit_d = markers.get("vitamin_d", 30.0)
    wbc = markers.get("wbc_count", 6500.0)

    glycemic_strain = max(0.0, (fbs - 100.0) * 0.08)
    vitd_deficiency = max(0.0, (30.0 - vit_d) * 0.12)
    inflamm_strain = 1.5 if wbc > 10000 else 0.0

    somatic_strain = (10 - sleep_hours) * 1.3 + (work_stress * 0.85) + glycemic_strain + vitd_deficiency + inflamm_strain
    allostatic_score = round(somatic_strain, 1)

    pulse_delta = max(0, pre_pulse - post_pulse)
    vagal_recovery = min(100.0, round((pulse_delta / max(1, pre_pulse - 60)) * 100, 1))
    cortisol_drop = round(pulse_delta * 1.85, 1)

    return {{
        "allostatic_score": allostatic_score,
        "status": {{
            "en": "Elevated Allostatic Strain" if allostatic_score > 12 else "Optimal Parasympathetic Tone",
            "hi": "शरीर में तनाव भार अधिक" if allostatic_score > 12 else "संतुलित न्यूरो-टोन",
            "mr": "तणाव भार जास्त" if allostatic_score > 12 else "संतुलित न्यूरो-टोन"
        }},
        "vagal_recovery_index": vagal_recovery,
        "pulse_delta": pulse_delta,
        "estimated_cortisol_drop_nmol": cortisol_drop,
        "biological_drivers": [
            f"Fasting Sugar ({{fbs}} mg/dL) elevates sympathetic tone." if fbs > 100 else None,
            f"Low Vitamin D ({{vit_d}} ng/mL) impairs neural recovery." if vit_d < 20 else None
        ],
        "dawn_glucose_warning": allostatic_score > 12 and sleep_hours < 6.5
    }}

# --- ADMIN KNOWLEDGE BASE ENDPOINTS ---
@app.get("/api/v1/admin/biomarkers")
def list_biomarkers(db: Session = Depends(get_db)):
    return db.query(BiomarkerRegistryModel).all()

@app.get("/api/v1/admin/drug-interactions")
def list_drug_rules(db: Session = Depends(get_db)):
    return db.query(DrugRuleModel).all()

# --- APPLICATION UI ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def helix_portal():
    return \"\"\"{portal_html}\"\"\"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
"""

with open("main.py", "w", encoding="utf-8") as f:
    f.write(main_full_code)

print("Dynamic main.py successfully compiled and deployed.")
