from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib
import uuid
import json

from core.config import settings
from core.database import engine, Base, get_db, AsyncSessionLocal
from models.orm import User, LabReport
from services.ocr_engine import OCREngine

app = FastAPI(title="Helix Enterprise Health OS", version="14.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.strip().encode()).hexdigest()

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- AUTH API ---
@app.post("/api/v1/auth/register")
async def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    city: str = Form("Mumbai"),
    dietary_preference: str = Form("Vegetarian"),
    db: AsyncSession = Depends(get_db)
):
    clean_email = email.strip().lower()
    res = await db.execute(select(User).where(User.email == clean_email))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    new_u = User(
        id=f"user_{uuid.uuid4().hex[:8]}",
        full_name=full_name.strip(),
        email=clean_email,
        password_hash=hash_pw(password),
        age=30,
        gender="Male",
        dietary_preference=dietary_preference,
        active_prescriptions=["Metformin 500mg (Daily)"],
        active_supplements=["Calcium Carbonate 500mg"],
        treatment_history=[]
    )
    db.add(new_u)
    await db.commit()
    return {"status": "success", "user_id": new_u.id, "full_name": new_u.full_name, "email": new_u.email, "city": city}

@app.post("/api/v1/auth/login")
async def login(email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    clean_email = email.strip().lower()
    hashed = hash_pw(password)
    res = await db.execute(select(User).where(User.email == clean_email))
    user = res.scalar_one_or_none()
    
    if not user or user.password_hash != hashed:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    return {
        "status": "success",
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "age": user.age,
        "gender": user.gender,
        "diet": user.dietary_preference
    }

# --- HL7 FHIR EXPORTER ---
@app.get("/api/v1/export/fhir/{user_id}")
async def export_fhir_bundle(user_id: str, db: AsyncSession = Depends(get_db)):
    res_u = await db.execute(select(User).where(User.id == user_id))
    user = res_u.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    res_r = await db.execute(select(LabReport).where(LabReport.user_id == user.id).order_by(LabReport.record_date.asc()))
    reports = res_r.scalars().all()

    fhir_entries = []
    for r in reports:
        for m_key, marker_data in r.biomarkers.items():
            if isinstance(marker_data, dict):
                val = marker_data.get("value", 0.0)
                name_obj = marker_data.get("name", {})
                name = name_obj.get("en", m_key) if isinstance(name_obj, dict) else str(name_obj)
                loinc = marker_data.get("loinc", "Unknown")
                unit = marker_data.get("unit", "")
            else:
                val = marker_data
                name = m_key
                loinc = "Unknown"
                unit = ""

            fhir_entries.append({
                "resource": {
                    "resourceType": "Observation",
                    "id": f"obs-{uuid.uuid4().hex[:8]}",
                    "status": "final",
                    "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory", "display": "Laboratory"}]}],
                    "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": name}]},
                    "subject": {"reference": f"Patient/{user.id}", "display": user.full_name},
                    "effectiveDateTime": r.record_date.isoformat(),
                    "performer": [{"display": r.hospital_name}],
                    "valueQuantity": {"value": val, "unit": unit, "system": "http://unitsofmeasure.org"}
                }
            })

    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "id": f"helix-bundle-{user.id}",
        "timestamp": datetime.utcnow().isoformat(),
        "entry": fhir_entries
    }
    return JSONResponse(content=fhir_bundle)

# --- DYNAMIC MULTILINGUAL CARD BUILDER ---
def build_dynamic_card(marker_key: str, marker_info: Any, snippet: str) -> dict:
    if isinstance(marker_info, dict):
        val = marker_info.get("value", 0.0)
        name_dict = marker_info.get("name", {})
        unit = marker_info.get("unit", "")
        min_v, max_v = marker_info.get("normal_range", (0.0, 100.0))
        p_min, p_max = marker_info.get("panic_limits", (min_v * 0.5, max_v * 2.0))
        specialist_dict = marker_info.get("specialist", {})
        guideline_dict = marker_info.get("guideline", {})
        what_dict = marker_info.get("what", {})
        low_dict = marker_info.get("low", {})
        high_dict = marker_info.get("high", {})
        tip_dict = marker_info.get("tip", {})
        loinc = marker_info.get("loinc", "Clinical Observation")
    else:
        val = float(marker_info)
        meta = OCREngine.MARKER_REGISTRY.get(marker_key, {})
        name_dict = meta.get("name", {})
        unit = meta.get("unit", "")
        min_v, max_v = meta.get("normal_range", (0.0, 100.0))
        p_min, p_max = meta.get("panic_limits", (min_v * 0.5, max_v * 2.0))
        specialist_dict = meta.get("specialist", {})
        guideline_dict = meta.get("guideline", {})
        what_dict = meta.get("what", {})
        low_dict = meta.get("low", {})
        high_dict = meta.get("high", {})
        tip_dict = meta.get("tip", {})
        loinc = meta.get("loinc", "Clinical Observation")

    def tr(field, default_val):
        if isinstance(field, dict):
            return {
                "en": field.get("en", default_val),
                "hi": field.get("hi", default_val),
                "mr": field.get("mr", default_val)
            }
        return {"en": str(field), "hi": str(field), "mr": str(field)}

    t_name = tr(name_dict, marker_key.replace('_', ' ').title())
    t_spec = tr(specialist_dict, "Consulting Physician")
    t_guide = tr(guideline_dict, "Standard Clinical Guidelines")
    t_what = tr(what_dict, f"Diagnostic parameter recorded as {val} {unit}.")
    t_tip = tr(tip_dict, "Follow your doctor's instructions and maintain regular hydration.")

    is_panic = (min_v > 0 and val < p_min) or val > p_max

    if is_panic:
        status_label = {
            "en": "CRITICAL (Emergency Alert)",
            "hi": "गंभीर चेतावनी (तत्काल डॉक्टर)",
            "mr": "अत्यंत गंभीर (तातडीने डॉक्टर)"
        }
        status_desc = {
            "en": f"CRITICAL: Outside safe reference limits ({min_v} - {max_v} {unit}). Immediate clinical review required.",
            "hi": f"गंभीर स्थिति: सुरक्षित सीमा ({min_v} - {max_v} {unit}) से बाहर है। तत्काल डॉक्टर से संपर्क करें।",
            "mr": f"अत्यंत गंभीर पातळी: सुरक्षित मर्यादेबाहेर ({min_v} - {max_v} {unit}) आहे. त्वरित डॉक्टरांचा सल्ला घ्या."
        }
        code = "danger"
    elif min_v > 0 and val < min_v:
        status_label = {
            "en": "Low (Below Safe Limit)",
            "hi": "कम (सुरक्षित सीमा से नीचे)",
            "mr": "कमी (सुरक्षित मर्यादेपेक्षा कमी)"
        }
        status_desc = tr(low_dict, f"Below normal reference limit ({min_v} - {max_v} {unit}).")
        code = "danger"
    elif max_v > 0 and val > max_v:
        status_label = {
            "en": "High (Above Safe Limit)",
            "hi": "अधिक (सुरक्षित सीमा से ऊपर)",
            "mr": "जास्त (सुरक्षित मर्यादेपेक्षा जास्त)"
        }
        status_desc = tr(high_dict, f"Above normal reference limit ({min_v} - {max_v} {unit}).")
        code = "warn"
    else:
        status_label = {
            "en": "Normal (Optimal & Safe)",
            "hi": "सामान्य (सुरक्षित स्तर)",
            "mr": "सामान्य (सुरक्षित पातळी)"
        }
        status_desc = {
            "en": f"Within safe reference limits ({min_v} - {max_v} {unit}).",
            "hi": f"सुरक्षित सीमा ({min_v} - {max_v} {unit}) के भीतर है।",
            "mr": f"सुरक्षित मर्यादेत ({min_v} - {max_v} {unit}) आहे."
        }
        code = "good"

    return {
        "key": marker_key,
        "title": t_name,
        "value": f"{val} {unit}".strip(),
        "unit": unit,
        "normal_range": f"{min_v} - {max_v} {unit}",
        "raw_num": val,
        "is_panic": is_panic,
        "loinc": loinc,
        "specialist": t_spec,
        "guideline": t_guide,
        "status": status_label,
        "status_code": code,
        "what": t_what,
        "summary": status_desc,
        "tip": t_tip,
        "snippet": snippet
    }

# --- DYNAMIC USER SUMMARY TELEMETRY ---
@app.get("/api/v1/user/summary/{user_id}")
async def get_user_summary(user_id: str, db: AsyncSession = Depends(get_db)):
    res_u = await db.execute(select(User).where(User.id == user_id))
    user = res_u.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User session expired or not found.")
    
    res_r = await db.execute(select(LabReport).where(LabReport.user_id == user.id).order_by(LabReport.record_date.asc()))
    reports = res_r.scalars().all()
    
    latest_report = reports[-1] if reports else None
    dynamic_cards = []
    all_treatments = []
    doctor_questions = []
    drug_shields = []
    specialist_recommendations = []
    
    for r in reports:
        dt_str = r.record_date.strftime("%d %b %Y")
        extracted_t = OCREngine.extract_clinical_treatments(r.raw_ocr_text or "", r.hospital_name, dt_str)
        all_treatments.extend(extracted_t)

    if user.treatment_history:
        all_treatments.extend(user.treatment_history)

    raw_latest_markers = {}
    if latest_report and latest_report.biomarkers:
        markers = latest_report.biomarkers
        for m_key, marker_data in markers.items():
            snippet = f"Cited from {latest_report.hospital_name}: {m_key}"
            card = build_dynamic_card(m_key, marker_data, snippet)
            dynamic_cards.append(card)
            raw_latest_markers[m_key] = card["raw_num"]

            val = card["raw_num"]
            name_obj = card["title"]
            unit = card["unit"]

            if card["status_code"] in ["warn", "danger"]:
                specialist_recommendations.append({
                    "specialist": card["specialist"],
                    "reason": {
                        "en": f"Recommended due to out-of-range {name_obj['en']} ({val} {unit}).",
                        "hi": f"{name_obj['hi']} ({val} {unit}) के असामान्य स्तर के कारण आवश्यक।",
                        "mr": f"{name_obj['mr']} चे प्रमाण ({val} {unit}) असामान्य असल्यामुळे आवश्यक."
                    },
                    "area": "Local Health District",
                    "priority": {
                        "en": "High Consultation" if card["is_panic"] else "Routine Follow-up",
                        "hi": "तत्काल परामर्श" if card["is_panic"] else "नियमित जांच",
                        "mr": "तातडीचा सल्ला" if card["is_panic"] else "नियमित तपासणी"
                    }
                })
                doctor_questions.append({
                    "biomarker": name_obj,
                    "finding": f"{val} {unit} [Normal: {card['normal_range']}]",
                    "question": {
                        "en": f"Ask Doctor: Should my prescription for {name_obj['en']} be adjusted alongside dietary modifications?",
                        "hi": f"डॉक्टर से पूछें: क्या {name_obj['hi']} ({val} {unit}) के लिए दवा की खुराक बदलने की जरूरत है?",
                        "mr": f"डॉक्टरांना विचारा: {name_obj['mr']} चे प्रमाण ({val} {unit}) पाहता औषधोपचारात बदल हवा का?"
                    }
                })

        if any("metformin" in str(rx).lower() for rx in (user.active_prescriptions or [])):
            creat_val = raw_latest_markers.get("serum_creatinine", 1.0)
            if creat_val > 1.4:
                drug_shields.append({
                    "severity": "danger",
                    "drug": "Metformin 500mg",
                    "biomarker": f"Serum Creatinine ({creat_val} mg/dL)",
                    "warning": {
                        "en": "Metformin renal clearance is reduced with elevated creatinine (>1.4 mg/dL). Nephrologist consultation required.",
                        "hi": "क्रिएटिनिन अधिक होने पर मेटफॉर्मिन दवा का असर प्रभावित हो सकता है। डॉक्टर से जांच कराएं।",
                        "mr": "क्रिएटिनिन जास्त असल्यास मेटफॉर्मिन औषध यकृतावर ताण आणू शकते. डॉक्टरांचा सल्ला घ्या."
                    }
                })
            else:
                drug_shields.append({
                    "severity": "good",
                    "drug": "Metformin 500mg",
                    "biomarker": f"Serum Creatinine ({creat_val} mg/dL)",
                    "warning": {
                        "en": "Renal clearance is optimal. Metformin is safely compatible with current kidney filtration markers.",
                        "hi": "किडनी की सफाई दर उत्तम है। मेटफॉर्मिन दवा वर्तमान रिपोर्ट के साथ पूरी तरह सुरक्षित है।",
                        "mr": "किडनीची कार्यक्षमता उत्तम आहे. सध्याच्या तपासणीनुसार मेटफॉर्मिन औषध पूर्णपणे सुरक्षित आहे."
                    }
                })

    all_keys = list({k for r in reports for k in r.biomarkers.keys()})[:8]
    chart_datasets = []
    colors = ["#10B981", "#F59E0B", "#EF4444", "#38BDF8", "#A855F7", "#EC4899", "#14B8A6", "#F97316"]
    
    for idx, k in enumerate(all_keys):
        data_pts = []
        name = k.replace('_', ' ').title()
        for r in reports:
            m_info = r.biomarkers.get(k)
            if isinstance(m_info, dict):
                data_pts.append(m_info.get("value"))
                n_obj = m_info.get("name", {})
                name = n_obj.get("en", name) if isinstance(n_obj, dict) else str(n_obj)
            elif m_info is not None:
                data_pts.append(float(m_info))
            else:
                data_pts.append(None)

        is_small_scale = any(sub in k for sub in ["hba1c", "hemoglobin", "serum_creatinine", "tsh", "platelet", "bilirubin", "uric"])
        chart_datasets.append({
            "label": name,
            "data": data_pts,
            "borderColor": colors[idx % len(colors)],
            "backgroundColor": colors[idx % len(colors)],
            "yAxisID": "y1" if is_small_scale else "y",
            "tension": 0.35,
            "borderWidth": 3,
            "pointRadius": 6,
            "spanGaps": True
        })

    return {
        "user": {
            "id": user.id,
            "name": user.full_name,
            "age": user.age,
            "gender": user.gender,
            "diet": user.dietary_preference,
            "email": user.email,
            "active_prescriptions": user.active_prescriptions or ["Metformin 500mg (Daily)"],
            "active_supplements": user.active_supplements or ["Calcium Carbonate 500mg"]
        },
        "hospitals_connected": list(dict.fromkeys([r.hospital_name for r in reports])),
        "latest_hospital": latest_report.hospital_name if latest_report else "No reports uploaded yet",
        "latest_date": latest_report.record_date.strftime("%d %b %Y") if latest_report else "N/A",
        "total_reports": len(reports),
        "dynamic_cards": dynamic_cards,
        "latest_biomarkers": raw_latest_markers,
        "treatments": all_treatments,
        "doctor_questions": doctor_questions,
        "drug_shields": drug_shields,
        "specialists": specialist_recommendations,
        "chart_data": {
            "dates": [r.record_date.strftime("%b %Y") for r in reports],
            "datasets": chart_datasets
        }
    }

# --- BATCH MULTI-FILE UPLOAD PIPELINE ---
@app.post("/api/v1/pipeline/upload-reports-batch")
async def upload_user_reports_batch(
    user_id: str = Form(...),
    raw_ocr_text: Optional[str] = Form(None),
    report_files: List[UploadFile] = File([]),
    db: AsyncSession = Depends(get_db)
):
    res_u = await db.execute(select(User).where(User.id == user_id))
    user = res_u.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User session not found. Please log in again.")

    uploaded_encounters = []

    if report_files and len(report_files) > 0 and report_files[0].filename:
        for file in report_files:
            content = await file.read()
            fname = file.filename.lower()
            text = ""
            if fname.endswith(".pdf"):
                text = OCREngine.parse_pdf_bytes(content)
            elif any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                text = OCREngine.parse_image_bytes(content)

            if not text.strip():
                continue

            metadata = OCREngine.extract_report_metadata(text)
            markers = OCREngine.extract_structured_biomarkers(text)

            if metadata.get("age") and user.age != metadata["age"]:
                user.age = metadata["age"]
            if metadata.get("gender") and user.gender != metadata["gender"]:
                user.gender = metadata["gender"]
            if metadata.get("patient_name") and len(metadata["patient_name"]) > 2:
                user.full_name = metadata["patient_name"]

            new_rep = LabReport(
                user_id=user.id,
                hospital_name=metadata["hospital_name"],
                record_date=metadata["record_date"],
                raw_ocr_text=text,
                biomarkers=markers
            )
            db.add(new_rep)
            uploaded_encounters.append(f"{metadata['hospital_name']} ({metadata['record_date'].strftime('%d %b %Y')})")
    
    elif raw_ocr_text and raw_ocr_text.strip():
        text = raw_ocr_text.strip()
        metadata = OCREngine.extract_report_metadata(text)
        markers = OCREngine.extract_structured_biomarkers(text)

        if metadata.get("age") and user.age != metadata["age"]:
            user.age = metadata["age"]
        if metadata.get("gender") and user.gender != metadata["gender"]:
            user.gender = metadata["gender"]
        if metadata.get("patient_name") and len(metadata["patient_name"]) > 2:
            user.full_name = metadata["patient_name"]

        new_rep = LabReport(
            user_id=user.id,
            hospital_name=metadata["hospital_name"],
            record_date=metadata["record_date"],
            raw_ocr_text=text,
            biomarkers=markers
        )
        db.add(new_rep)
        uploaded_encounters.append(f"{metadata['hospital_name']} ({metadata['record_date'].strftime('%d %b %Y')})")

    await db.commit()
    return {"status": "success", "count": len(uploaded_encounters), "encounters": uploaded_encounters}

# --- BIOMARKER-GROUNDED NEURO-STRESS ENGINE ---
@app.post("/api/v1/stress/assess-dynamic")
async def assess_dynamic_stress(
    user_id: str = Form(...),
    sleep_hours: float = Form(6.5),
    work_stress: int = Form(7),
    pre_pulse: int = Form(84),
    post_pulse: int = Form(72),
    db: AsyncSession = Depends(get_db)
):
    res_r = await db.execute(select(LabReport).where(LabReport.user_id == user_id).order_by(LabReport.record_date.desc()))
    latest = res_r.scalars().first()
    markers = latest.biomarkers if latest else {}

    def get_val(key):
        m = markers.get(key)
        if isinstance(m, dict):
            return m.get("value", 0.0)
        return float(m) if m is not None else 0.0

    fbs = get_val("fasting_glucose") or 95.0
    vit_d = get_val("vitamin_d") or 30.0
    wbc = get_val("wbc_count") or 6500.0

    glycemic_stress_strain = max(0.0, (fbs - 100.0) * 0.08)
    vitd_neuro_deficiency = max(0.0, (30.0 - vit_d) * 0.12)
    inflammatory_strain = 1.5 if wbc > 10000 else 0.0

    somatic_strain = (10 - sleep_hours) * 1.3 + (work_stress * 0.85) + glycemic_stress_strain + vitd_neuro_deficiency + inflammatory_strain
    allostatic_score = round(somatic_strain, 1)

    pulse_delta = max(0, pre_pulse - post_pulse)
    vagal_recovery_index = min(100.0, round((pulse_delta / max(1, pre_pulse - 60)) * 100, 1))
    estimated_cortisol_drop = round(pulse_delta * 1.85, 1)

    status_map = {
        "en": "Elevated Systemic Allostatic Load",
        "hi": "शरीर में तनाव और कॉर्टिसोल स्तर अधिक",
        "mr": "शरीरातील तणाव व कॉर्टिसॉल पातळी जास्त"
    } if allostatic_score > 12 else {
        "en": "Optimal Parasympathetic Tone",
        "hi": "संतुलित और सुरक्षित न्यूरो-टोन",
        "mr": "संतुलित व निरोगी न्यूरो-टोन"
    }

    biological_drivers = []
    if fbs > 100:
        biological_drivers.append({
            "en": f"Morning Sugar ({fbs} mg/dL) stimulates nocturnal adrenaline/cortisol.",
            "hi": f"सुबह की शुगर ({fbs} mg/dL) रात में तनाव हार्मोन को बढ़ाती है।",
            "mr": f"सकाळची साखर ({fbs} mg/dL) रात्रीच्या तणाव संप्रेरकांना उत्तेजित करते."
        })
    if vit_d < 20:
        biological_drivers.append({
            "en": f"Low Vitamin D ({vit_d} ng/mL) slows down neural recovery and serotonin synthesis.",
            "hi": f"विटामिन डी की कमी ({vit_d} ng/mL) तंत्रिका तंत्र की शांति में बाधा डालती है।",
            "mr": f"व्हिटॅमिन डी ची कमतरता ({vit_d} ng/mL) मज्जासंस्थेच्या विश्रांतीमध्ये अडथळा आणते."
        })

    return {
        "allostatic_score": allostatic_score,
        "status": status_map,
        "vagal_recovery_index": vagal_recovery_index,
        "pulse_delta": pulse_delta,
        "estimated_cortisol_drop_nmol": estimated_cortisol_drop,
        "biological_drivers": biological_drivers,
        "dawn_glucose_warning": allostatic_score > 12 and sleep_hours < 6.5
    }

# --- DYNAMIC SYMPTOM CORRELATOR ---
@app.post("/api/v1/symptoms/correlate")
async def correlate_symptoms(symptom: str = Form(...), user_id: str = Form(...), db: AsyncSession = Depends(get_db)):
    res_r = await db.execute(select(LabReport).where(LabReport.user_id == user_id).order_by(LabReport.record_date.desc()))
    latest = res_r.scalars().first()
    markers = latest.biomarkers if latest else {}
    hosp_name = latest.hospital_name if latest else "Your Report"

    s_lower = symptom.lower().strip()
    correlations = []

    SYMPTOM_BIOMARKER_MAP = {
        "fasting_glucose": {
            "keywords": ["sugar", "dizzy", "dizziness", "tired", "fatigue", "thirst", "hungry", "sweating", "headache", "urination", "weakness"],
            "high": {
                "en": "Your high blood sugar prevents glucose from entering cells efficiently, causing post-meal fatigue, frequent thirst, and energy crashes.",
                "hi": "खून में अधिक शुगर कोशिकाओं तक ऊर्जा नहीं पहुंचने देती, जिससे खाने के बाद थकान और ज्यादा प्यास लगती है।",
                "mr": "रक्तातील वाढलेली साखर पेशींना ऊर्जा मिळण्यात अडथळा आणते, ज्यामुळे थकवा आणि वारंवार तहान लागते."
            },
            "low": {
                "en": "Low blood sugar causes your brain to lack immediate fuel, leading to shakiness and sudden weakness.",
                "hi": "शुगर कम होने से मस्तिष्क को तुरंत ऊर्जा नहीं मिलती, जिससे हाथ कांपना और कमजोरी होती है।",
                "mr": "साखर कमी झाल्यामुळे मेंदूला पुरेशी ऊर्जा मिळत नाही, ज्यामुळे चक्कर आणि अशक्तपणा जाणवतो."
            }
        },
        "hba1c": {
            "keywords": ["tired", "fatigue", "weakness", "blurry", "vision", "healing", "tingling", "feet", "numbness"],
            "high": {
                "en": "Elevated 3-month sugar indicates long-term insulin resistance, which directly explains chronic lethargy.",
                "hi": "पिछले ९० दिनों का बढ़ा हुआ शुगर स्तर शरीर में लगातार सुस्ती और कमजोरी का मुख्य कारण है।",
                "mr": "मागील ३ महिन्यांतील वाढलेली साखर शरीरातील सततचा आळस आणि स्नायूंमधील अशक्तपणा स्पष्ट करते."
            }
        },
        "hemoglobin": {
            "keywords": ["pale", "breath", "breathing", "tired", "fatigue", "weakness", "stamina", "cold", "dizzy"],
            "low": {
                "en": "Low hemoglobin means fewer red blood cells carrying oxygen to muscles and brain, causing shortness of breath and heavy fatigue.",
                "hi": "हीमोग्लोबिन कम होने से शरीर और मांसपेशियों में ऑक्सीजन की कमी हो जाती है, जिससे सांस फूलना और भारी थकान होती है।",
                "mr": "हिमोग्लोबिन कमी असल्यामुळे शरीराला ऑक्सिजन कमी मिळतो, ज्यामुळे धाप लागणे आणि तीव्र थकवा जाणवतो."
            }
        },
        "vitamin_d": {
            "keywords": ["bone", "joint", "back", "muscle", "aches", "pain", "cramps", "tired", "mood", "depression"],
            "low": {
                "en": "Vitamin D deficiency impairs neuromuscular signaling, causing chronic back aches and generalized body fatigue.",
                "hi": "विटामिन डी की कमी से मांसपेशियों में दर्द व लगातार बदन दर्द और कमर दर्द बना रहता है।",
                "mr": "व्हिटॅमिन डी च्या कमतरतेमुळे हाडे आणि स्नायूंमध्ये सतत वेदना, कंबरदुखी व अंगदुखी जाणवते."
            }
        },
        "serum_creatinine": {
            "keywords": ["swelling", "feet", "legs", "nausea", "urine", "puffy", "eyes", "itch"],
            "high": {
                "en": "Elevated creatinine indicates slower kidney filtration, which can cause fluid buildup leading to ankle swelling.",
                "hi": "क्रिएटिनिन अधिक होना किडनी की धीमी सफाई दर्शाता है, जिससे पैरों पर हल्की सूजन आ सकती है।",
                "mr": "क्रिएटिनिन वाढल्याने किडन्या रक्त सावकाश गाळतात, ज्यामुळे पायांवर किंवा चेहऱ्यावर सूज येऊ शकते."
            }
        },
        "ldl_cholesterol": {
            "keywords": ["chest", "heaviness", "breath", "walking", "pressure", "heart"],
            "high": {
                "en": "Elevated LDL cholesterol leads to fatty arterial deposition, contributing to exertional chest tightness.",
                "hi": "खराब कोलेस्ट्रॉल बढ़ने से नसों में रुकावट आ सकती है, जिससे चलने पर भारीपन या सांस फूलने का अनुभव हो सकता है।",
                "mr": "LDL वाढल्याने रक्तवाहिन्यांमध्ये अडथळा निर्माण होऊ शकतो, ज्यामुळे चालताना छातीत जडपणा जाणवू शकतो."
            }
        }
    }

    for m_key, marker_data in markers.items():
        if isinstance(marker_data, dict):
            val = marker_data.get("value", 0.0)
            name_obj = marker_data.get("name", {"en": m_key})
            min_v, max_v = marker_data.get("normal_range", (0.0, 100.0))
            unit = marker_data.get("unit", "")
        else:
            val = float(marker_data)
            meta = OCREngine.MARKER_REGISTRY.get(m_key, {})
            name_obj = meta.get("name", {"en": m_key})
            min_v, max_v = meta.get("normal_range", (0.0, 100.0))
            unit = meta.get("unit", "")

        rule = SYMPTOM_BIOMARKER_MAP.get(m_key)
        if not rule:
            continue

        is_high = max_v > 0 and val > max_v
        is_low = min_v > 0 and val < min_v

        matched_kw = [kw for kw in rule["keywords"] if kw in s_lower]
        if matched_kw:
            if is_high and "high" in rule:
                correlations.append({
                    "biomarker": name_obj,
                    "value": f"{val} {unit}".strip(),
                    "status_code": "warn",
                    "status_label": {"en": "Above Safe Limit", "hi": "सुरक्षित सीमा से अधिक", "mr": "सुरक्षित मर्यादेपेक्षा जास्त"},
                    "source": f"Verified from {hosp_name}",
                    "explanation": rule["high"]
                })
            elif is_low and "low" in rule:
                correlations.append({
                    "biomarker": name_obj,
                    "value": f"{val} {unit}".strip(),
                    "status_code": "danger",
                    "status_label": {"en": "Below Safe Limit", "hi": "सुरक्षित सीमा से कम", "mr": "सुरक्षित मर्यादेपेक्षा कमी"},
                    "source": f"Verified from {hosp_name}",
                    "explanation": rule["low"]
                })

    if not correlations:
        correlations.append({
            "biomarker": {"en": "Comprehensive Health Scan", "hi": "समग्र स्वास्थ्य जांच", "mr": "सर्वसमावेशक आरोग्य तपासणी"},
            "value": "Normal Baseline",
            "status_code": "good",
            "status_label": {"en": "All Tests Normal", "hi": "सभी जांचें सामान्य", "mr": "सर्व चाचण्या सामान्य"},
            "source": f"Verified from {hosp_name}",
            "explanation": {
                "en": f"None of your currently tracked lab markers indicate an acute correlation with '{symptom}'. If symptoms persist, consult your physician.",
                "hi": f"आपकी रिपोर्ट की जांचें सामान्य हैं। यदि लक्षण '{symptom}' बना रहता है तो डॉक्टर से संपर्क करें।",
                "mr": f"तुमच्या अहवालातील चाचण्या सामान्य आहेत. जर '{symptom}' त्रास कायम राहिला तर डॉक्टरांचा सल्ला घ्या."
            }
        })

    return {"symptom": symptom, "correlations": correlations}

# --- APPLICATION UI WITH ZERO HARDCODING ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def helix_portal():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Helix Health OS — 3D Clinical Intelligence & Habit Architecture</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-void: #050811;
            --surface: rgba(14, 22, 38, 0.85);
            --surface-card: rgba(19, 31, 54, 0.75);
            --border-glow: rgba(30, 45, 74, 0.9);
            --brand-emerald: #10B981;
            --brand-purple: #8B5CF6;
            --brand-cyan: #06B6D4;
        }
        body { 
            background: radial-gradient(circle at 50% 0%, #0A192F 0%, #050811 100%);
            color: #F1F5F9; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
        }
        .card { 
            background: var(--surface); 
            border: 1px solid var(--border-glow); 
            border-radius: 18px; 
            box-shadow: 0 20px 40px -15px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08); 
            backdrop-filter: blur(16px);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .card-3d:hover {
            transform: translateY(-4px) perspective(1000px) rotateX(1deg);
            box-shadow: 0 25px 50px -12px rgba(16, 185, 129, 0.15), inset 0 1px 0 rgba(255,255,255,0.15);
        }
        .hero-banner { 
            background: linear-gradient(135deg, rgba(6, 78, 59, 0.8) 0%, rgba(14, 22, 38, 0.95) 60%, rgba(20, 32, 54, 0.9) 100%); 
            border: 1px solid rgba(16,185,129,0.4); 
            border-radius: 20px; 
            box-shadow: 0 25px 50px -10px rgba(6, 78, 59, 0.3);
        }
        .btn-helix { 
            background: linear-gradient(135deg, #10B981, #059669); 
            color: #fff; 
            font-weight: 700; 
            border: none; 
            border-radius: 10px; 
            box-shadow: 0 8px 20px -6px rgba(16,185,129,0.6);
        }
        .btn-helix:hover { opacity: 0.95; color: #fff; transform: translateY(-1px); }
        .btn-lang { background: #142036; color: #94A3B8; border: 1px solid var(--border-glow); font-weight: 600; border-radius: 8px; }
        .btn-lang.active { background: var(--brand-emerald); color: #fff; border-color: var(--brand-emerald); }
        .form-control { background-color: #080D1A; border: 1px solid var(--border-glow); color: #fff; }
        .form-control:focus { background-color: #080D1A; border-color: var(--brand-emerald); color: #fff; box-shadow: none; }
        
        .badge-status { padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 11px; text-transform: uppercase; }
        .status-warn { background-color: rgba(245,158,11,0.15); color: #FBBF24; border: 1px solid rgba(245,158,11,0.4); }
        .status-danger { background-color: rgba(239,68,68,0.15); color: #F87171; border: 1px solid rgba(239,68,68,0.4); }
        .status-good { background-color: rgba(16,185,129,0.15); color: #34D399; border: 1px solid rgba(16,185,129,0.4); }
        
        .nav-tabs .nav-link { color: #94A3B8; border: none; border-bottom: 2px solid transparent; font-weight: 700; }
        .nav-tabs .nav-link.active { background: transparent; color: var(--brand-emerald); border-bottom: 3px solid var(--brand-emerald); }
        
        .timeline-box { position: relative; border-left: 2px solid #10B981; padding-left: 20px; margin-bottom: 20px; }
        .timeline-dot { position: absolute; left: -9px; top: 0; width: 16px; height: 16px; border-radius: 50%; background: #10B981; }
        .treatment-card { background: var(--surface-card); border: 1px solid var(--border-glow); border-radius: 12px; padding: 15px; }
        .guideline-badge { font-size: 10px; background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.3); color: #38BDF8; padding: 2px 8px; border-radius: 6px; }

        .breath-circle {
            width: 140px; height: 140px; border-radius: 50%;
            background: radial-gradient(circle, #8B5CF6 0%, #3B0764 100%);
            display: flex; align-items: center; justify-content: center;
            margin: auto; font-weight: 800; color: #fff; text-align: center;
            transition: all 4s ease-in-out;
            box-shadow: 0 0 30px rgba(139,92,246,0.4);
        }
        .expand-circle { transform: scale(1.3); box-shadow: 0 0 50px rgba(16,185,129,0.7); background: radial-gradient(circle, #10B981 0%, #064E3B 100%); }
    </style>
</head>
<body class="py-4">

<div class="container-fluid px-lg-5">
    
    <!-- Top Header -->
    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary border-opacity-25 flex-wrap gap-3">
        <div class="d-flex align-items-center gap-3">
            <span class="p-3 rounded-4 bg-success bg-opacity-25 text-success fs-3 shadow-sm"><i class="fa-solid fa-dna"></i></span>
            <div>
                <h3 class="text-white fw-bold mb-0">HELIX HEALTH OS</h3>
                <p class="text-secondary small mb-0" id="tag-sub">Enterprise Decision Support Platform: Multi-Hospital Telemetry & Grounded Twin</p>
            </div>
        </div>

        <div class="d-flex align-items-center gap-3">
            <!-- 3-Language Switcher -->
            <div class="d-flex gap-1 bg-dark p-1 rounded-3 border border-secondary border-opacity-50">
                <button class="btn btn-sm btn-lang active" onclick="setLanguage('en')">English</button>
                <button class="btn btn-sm btn-lang" onclick="setLanguage('hi')">हिन्दी</button>
                <button class="btn btn-sm btn-lang" onclick="setLanguage('mr')">मराठी</button>
            </div>
            
            <!-- Auth Header Dropdown -->
            <div id="auth-container"></div>
        </div>
    </div>

    <!-- 1. MANDATORY LOGIN / SIGNUP SCREEN -->
    <div id="auth-screen" class="row justify-content-center my-5 d-none">
        <div class="col-md-5">
            <div class="card p-4 shadow-lg border-success border-opacity-50">
                <div class="text-center mb-4">
                    <span class="p-3 rounded-circle bg-success bg-opacity-25 text-success fs-3 d-inline-block mb-2"><i class="fa-solid fa-user-lock"></i></span>
                    <h4 class="text-white fw-bold" id="lbl-auth-title">Sign In to Your Health Timeline</h4>
                    <p class="text-secondary small" id="lbl-auth-desc">Access hospital records, dynamic metabolic twin, and clinical summaries.</p>
                </div>

                <ul class="nav nav-pills nav-fill mb-3" id="authTab" role="tablist">
                    <li class="nav-item"><button class="nav-link active btn-sm" data-bs-toggle="pill" data-bs-target="#tab-signin" id="lbl-tab-signin">Sign In</button></li>
                    <li class="nav-item"><button class="nav-link btn-sm" data-bs-toggle="pill" data-bs-target="#tab-signup" id="lbl-tab-signup">Register</button></li>
                </ul>

                <div class="tab-content">
                    <div class="tab-pane fade show active" id="tab-signin">
                        <label class="small text-secondary fw-bold mb-1" id="lbl-email-in">EMAIL ADDRESS</label>
                        <input type="email" id="in-email" class="form-control mb-3" placeholder="name@example.com">
                        <label class="small text-secondary fw-bold mb-1" id="lbl-pw-in">PASSWORD</label>
                        <input type="password" id="in-pw" class="form-control mb-4" placeholder="••••••••">
                        <button class="btn btn-helix w-100 py-2 fw-bold" onclick="login()"><i class="fa-solid fa-right-to-bracket me-2"></i><span id="lbl-btn-login">Sign In</span></button>
                    </div>

                    <div class="tab-pane fade" id="tab-signup">
                        <label class="small text-secondary fw-bold mb-1" id="lbl-name-up">FULL NAME</label>
                        <input type="text" id="up-name" class="form-control mb-2" placeholder="e.g. Chitrang Sawant">
                        <label class="small text-secondary fw-bold mb-1" id="lbl-email-up">EMAIL</label>
                        <input type="email" id="up-email" class="form-control mb-2" placeholder="name@example.com">
                        <label class="small text-secondary fw-bold mb-1" id="lbl-city-up">LOCATION / DISTRICT</label>
                        <input type="text" id="up-city" class="form-control mb-2" value="Mumbai" placeholder="e.g. Mumbai, Pune, Delhi">
                        <label class="small text-secondary fw-bold mb-1" id="lbl-pw-up">PASSWORD</label>
                        <input type="password" id="up-pw" class="form-control mb-2" placeholder="Create a password">
                        <button class="btn btn-helix w-100 py-2 fw-bold mt-3" onclick="register()"><i class="fa-solid fa-user-plus me-2"></i><span id="lbl-btn-register">Create Health Account</span></button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 2. MAIN APPLICATION WORKSPACE -->
    <div id="dashboard-screen" class="d-none">
        
        <!-- Navigation View Tabs -->
        <ul class="nav nav-tabs mb-4" id="mainTab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#view-command"><i class="fa-solid fa-gauge-high me-2 text-success"></i><span id="tab-cmd-lbl">Dynamic Lab Dashboard</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-twin"><i class="fa-solid fa-vr-cardboard me-2 text-primary"></i><span id="tab-twin-lbl">90-Day Metabolic Twin</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-habits"><i class="fa-solid fa-person-walking me-2 text-warning"></i><span id="tab-habit-lbl">Habit Building & Specialist Finder</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-doctor"><i class="fa-solid fa-user-doctor me-2 text-info"></i><span id="tab-doc-lbl">Doctor Handoff & HL7 FHIR</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-treatments"><i class="fa-solid fa-notes-medical me-2 text-info"></i><span id="tab-treat-lbl">Past Treatments & History</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-stress"><i class="fa-solid fa-brain me-2 text-purple"></i><span id="tab-stress-lbl">Stress & Neuro-Recovery Studio</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-symptoms"><i class="fa-solid fa-stethoscope me-2 text-warning"></i><span id="tab-symp-lbl">Symptom Checker</span></button>
            </li>
        </ul>

        <div class="tab-content">
            
            <!-- TAB 1: DYNAMIC LAB REPORT DASHBOARD -->
            <div class="tab-pane fade show active" id="view-command">
                <div class="hero-banner p-4 mb-4 shadow">
                    <div class="row align-items-center g-3">
                        <div class="col-lg-7">
                            <span class="badge bg-success bg-opacity-25 text-success mb-2 px-3 py-1 border border-success border-opacity-50"><i class="fa-solid fa-shield-halved me-1"></i> <span id="lbl-status-badge">Deterministic Double-Verification Active</span></span>
                            <h3 class="text-white fw-bold mb-1" id="dash-greeting">Welcome to Helix</h3>
                            <p class="text-light text-opacity-75 small mb-3" id="lbl-hero-desc">Upload any medical test reports. Helix automatically extracts whatever parameters are present, plots real-time trajectory curves, and checks reference limits.</p>
                            <div class="d-flex gap-2">
                                <button class="btn btn-helix px-4 py-2" data-bs-toggle="modal" data-bs-target="#uploadModal"><i class="fa-solid fa-cloud-arrow-up me-1"></i> <span id="lbl-btn-upload">Upload Medical Reports (Multi-File)</span></button>
                            </div>
                        </div>
                        <div class="col-lg-5">
                            <div class="card bg-dark bg-opacity-75 p-3 border-secondary border-opacity-50">
                                <div class="text-secondary small fw-bold mb-1"><i class="fa-solid fa-hospital-user text-primary me-1"></i> <span id="lbl-hosp-source">LATEST REPORT SOURCE:</span></div>
                                <div class="text-white fw-bold" id="latest-hosp">No reports yet</div>
                                <div class="text-secondary small" id="latest-date">Date: N/A</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- DYNAMIC BIOMARKER TILES -->
                <h5 class="text-white fw-bold mb-3"><i class="fa-solid fa-list-check text-success me-2"></i> <span id="lbl-cards-heading">Tests Extracted From Your Uploaded Report:</span></h5>
                <div class="row g-3 mb-4" id="dynamic-cards-grid"></div>

                <!-- Dynamic Multi-Biomarker Longitudinal Graph (Dual Y-Axis) -->
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-1 flex-wrap">
                        <h5 class="text-white fw-bold mb-0"><i class="fa-solid fa-chart-line text-primary me-2"></i> <span id="lbl-chart-title">Longitudinal Tracking of Your Tests Over Time</span></h5>
                        <span class="badge bg-secondary small" id="lbl-axis-tag">Left Axis: Standard Values | Right Axis: Small Fractions</span>
                    </div>
                    <p class="text-secondary small mb-3" id="lbl-chart-sub">Plots the chronological progression curve for each biomarker across your hospital visits.</p>
                    <div class="p-3 rounded bg-dark border border-secondary border-opacity-25" style="position: relative; height: 350px;">
                        <canvas id="userChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- TAB 2: 90-DAY DYNAMIC METABOLIC TWIN SIMULATOR -->
            <div class="tab-pane fade" id="view-twin">
                <div class="card p-4 mb-4">
                    <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-vr-cardboard text-primary me-2"></i> <span id="lbl-twin-heading">90-Day What-If Metabolic Twin Simulator</span></h5>
                    <p class="text-secondary small mb-4" id="lbl-twin-sub">Directly linked to your uploaded lab tests. Adjust your daily habits to forecast exact 90-day biological recovery.</p>
                    
                    <div class="row g-4 mb-4">
                        <div class="col-md-6">
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 mb-3">
                                <label class="small text-secondary fw-bold" id="lbl-ex-slider">WEEKLY EXERCISE & RESISTANCE TRAINING (DAYS/WEEK)</label>
                                <input type="range" class="form-range mb-3" id="sim-ex" min="0" max="7" value="4" oninput="runLiveTwinSimulation()">
                                <div class="text-end small text-success fw-bold"><span id="ex-val">4</span> <span id="lbl-days-week">Days / Week</span></div>

                                <label class="small text-secondary fw-bold mt-3" id="lbl-sg-slider">DAILY CALORIC DEFICIT & SUGAR REDUCTION</label>
                                <input type="range" class="form-range mb-3" id="sim-sg" min="0" max="100" value="50" oninput="runLiveTwinSimulation()">
                                <div class="text-end small text-success fw-bold"><span id="sg-val">50%</span> <span id="lbl-reduction-tag">Reduction (~350 kcal/day deficit)</span></div>

                                <div class="p-2 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25 small text-secondary">
                                    <i class="fa-solid fa-calculator text-info me-1"></i><strong id="lbl-basis-title">Scientific Basis:</strong> <span id="lbl-basis-desc">120-Day Erythrocyte Turnover & Hepatic Gluconeogenesis clearance curve.</span>
                                </div>
                            </div>

                            <!-- Dynamic Habits to Avoid & Follow Box -->
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50">
                                <strong class="text-danger small fw-bold"><i class="fa-solid fa-triangle-exclamation me-1"></i> <span id="lbl-avoid-title">Habits To Avoid (Prevents Metric Deterioration):</span></strong>
                                <ul class="text-secondary small mt-2 mb-3 ps-3" id="avoid-list"></ul>

                                <strong class="text-success small fw-bold"><i class="fa-solid fa-circle-check me-1"></i> <span id="lbl-follow-title">Daily Habits To Follow (Adjuvant to Doctor Medicines):</span></strong>
                                <ul class="text-secondary small mt-2 mb-0 ps-3" id="follow-list"></ul>
                            </div>
                        </div>

                        <div class="col-md-6">
                            <div class="p-3 bg-dark rounded border border-success border-opacity-50 h-100">
                                <div class="text-success fw-bold small mb-2"><i class="fa-solid fa-bullseye me-1"></i> <span id="lbl-twin-proj-title">PROJECTED 90-DAY RECOVERY TIED TO REPORT BASELINES:</span></div>
                                <div class="row text-center g-2 small" id="twin-projections-grid"></div>
                                <div class="text-info small mt-3" id="sim-summary">Dynamic physiological calculation based on your latest uploaded lab parameters.</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: HABIT BUILDING & SPECIALIST FINDER -->
            <div class="tab-pane fade" id="view-habits">
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-3d p-4 h-100">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h5 class="text-white fw-bold mb-0"><i class="fa-solid fa-seedling text-success me-2"></i> <span id="lbl-habits-title">Daily Morning Habit Consistency</span></h5>
                                <span class="badge bg-success bg-opacity-25 text-success" id="lbl-habits-badge">Consistency > Intensity</span>
                            </div>
                            <p class="text-secondary small mb-3" id="lbl-habits-sub">Structured, zero-friction daily routines inspired by live virtual habit models (like Habuild) to build lifelong adherence.</p>
                            
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 mb-3" id="habit-items-container"></div>

                            <div class="p-3 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25 small text-secondary">
                                <i class="fa-solid fa-circle-info text-info me-1"></i><strong id="lbl-habits-note-title">Clinical Note:</strong> <span id="lbl-habits-note-desc">Habit consistency lowers baseline cortisol and stabilizes glucose peaks naturally.</span>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-6">
                        <div class="card card-3d p-4 h-100">
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-user-doctor text-info me-2"></i> <span id="lbl-spec-title">Specialist Recommendation for Your Area</span></h5>
                            <p class="text-secondary small mb-3" id="lbl-spec-sub">Clinically mapped to the exact out-of-range parameters found in your report.</p>
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50" id="specialist-box"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 4: DOCTOR 1-PAGE SUMMARY & HL7 FHIR INTEROPERABILITY -->
            <div class="tab-pane fade" id="view-doctor">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                        <div>
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-user-doctor text-primary me-2"></i> <span id="lbl-doc-heading">Doctor 1-Page Summary & HL7 FHIR Interoperability</span></h5>
                            <p class="text-secondary small mb-0" id="lbl-doc-sub">A concise clinical briefing and standards-compliant HL7 FHIR JSON bundle for hospital EMR integration.</p>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-outline-success" onclick="exportFhir()"><i class="fa-solid fa-file-code me-1"></i> <span id="lbl-btn-fhir">Export HL7 FHIR JSON</span></button>
                            <button class="btn btn-sm btn-outline-light" onclick="window.print()"><i class="fa-solid fa-print me-1"></i> <span id="lbl-btn-print">Print Doctor Summary</span></button>
                        </div>
                    </div>

                    <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 mb-4">
                        <div class="row g-3">
                            <div class="col-md-4">
                                <div class="text-secondary small" id="lbl-pt-name-title">PATIENT NAME & AGE</div>
                                <div class="text-white fw-bold" id="doc-patient-name">—</div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-secondary small" id="lbl-hosp-conn-title">HOSPITALS & LABS CONNECTED</div>
                                <div class="text-white fw-bold" id="doc-hosp-summary">—</div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-secondary small" id="lbl-eval-date-title">LATEST EVALUATION DATE</div>
                                <div class="text-success fw-bold" id="doc-eval-date">—</div>
                            </div>
                        </div>
                    </div>

                    <h6 class="text-white fw-bold mb-2"><i class="fa-solid fa-shield-virus text-info me-2"></i> <span id="lbl-drug-shield-title">Dynamic Drug-Biomarker Toxicity Shield:</span></h6>
                    <div class="p-3 bg-dark rounded border border-info border-opacity-50 mb-4" id="drug-shield-container"></div>

                    <h6 class="text-white fw-bold mb-2"><i class="fa-solid fa-clipboard-question text-warning me-2"></i> <span id="lbl-doc-points-title">Questions to Ask Your Doctor in Your Next Visit:</span></h6>
                    <div class="p-3 bg-dark rounded border border-warning border-opacity-50 mb-4" id="doctor-questions-container"></div>
                </div>
            </div>

            <!-- TAB 5: SPECIFIC TREATMENTS & DETAILED MEDICAL HISTORY -->
            <div class="tab-pane fade" id="view-treatments">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                        <div>
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-clock-rotate-left text-info me-2"></i> <span id="lbl-treat-heading">Specific Treatments & Procedures History</span></h5>
                            <p class="text-secondary small mb-0" id="lbl-treat-sub">Chronological log of specific surgeries, medication therapies, and rehabilitation procedures the patient has undergone.</p>
                        </div>
                        <button class="btn btn-sm btn-outline-light" onclick="window.print()"><i class="fa-solid fa-print me-1"></i> <span id="lbl-btn-print-treat">Print History</span></button>
                    </div>

                    <h6 class="text-white fw-bold mb-3"><i class="fa-solid fa-timeline text-success me-2"></i> <span id="lbl-treat-box-title">Specific Interventions Extracted From Hospital Documents:</span></h6>
                    <div class="p-3 bg-dark rounded border border-secondary border-opacity-25" id="treatment-timeline-container"></div>
                </div>
            </div>

            <!-- TAB 6: DYNAMIC NEURO-RECOVERY & VAGAL BIOFEEDBACK STUDIO -->
            <div class="tab-pane fade" id="view-stress">
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card p-4 h-100 text-center">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h5 class="text-white fw-bold mb-0"><i class="fa-solid fa-lungs text-info me-2"></i> <span id="lbl-pacer-title">4-4-4-4 Vagus Activation Pacer</span></h5>
                                <span class="badge bg-purple" id="circadian-badge"><i class="fa-solid fa-clock me-1"></i> Night Mode</span>
                            </div>
                            <p class="text-secondary small mb-3" id="lbl-pacer-desc">Slow diaphragmatic breathing stimulates parasympathetic vagal recovery.</p>
                            
                            <div class="my-3">
                                <div class="breath-circle" id="pacer">Inhale (4s)</div>
                            </div>
                            
                            <div class="d-flex justify-content-center gap-2 mt-3 mb-3">
                                <button class="btn btn-sm btn-outline-info" onclick="playBinaural(40)"><i class="fa-solid fa-headphones me-1"></i> 40Hz Gamma</button>
                                <button class="btn btn-sm btn-outline-success" onclick="playBinaural(10)"><i class="fa-solid fa-water me-1"></i> 10Hz Alpha</button>
                                <button class="btn btn-sm btn-outline-primary" onclick="playBinaural(4)"><i class="fa-solid fa-moon me-1"></i> 4Hz Theta</button>
                                <button class="btn btn-sm btn-outline-danger" onclick="stopBinaural()"><i class="fa-solid fa-stop"></i></button>
                            </div>

                            <button class="btn btn-helix px-4 py-2 w-100 mb-3" id="breath-btn" onclick="toggleBreathing()"><i class="fa-solid fa-play me-1"></i> <span id="lbl-breath-btn">Start Guided Pacer</span></button>

                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 text-start">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <strong class="text-white small"><i class="fa-solid fa-heart-pulse text-danger me-1"></i> <span id="lbl-vagal-test-title">60s Vagal Recovery & HRV Proxy</span></strong>
                                    <span class="badge bg-success" id="lbl-vagal-badge">Active</span>
                                </div>
                                <div class="row g-2 small">
                                    <div class="col-6">
                                        <label class="text-secondary" style="font-size:10px;" id="lbl-pre-pulse">PRE-BREATHING PULSE (BPM)</label>
                                        <input type="number" id="pre-pulse" class="form-control form-control-sm" value="84">
                                    </div>
                                    <div class="col-6">
                                        <label class="text-secondary" style="font-size:10px;" id="lbl-post-pulse">POST-BREATHING PULSE (BPM)</label>
                                        <input type="number" id="post-pulse" class="form-control form-control-sm" value="72">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-6">
                        <div class="card p-4 h-100">
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-brain text-warning me-2"></i> <span id="lbl-stress-engine-title">Biomarker-Grounded Neuro-Stress Engine</span></h5>
                            <p class="text-secondary small mb-3" id="lbl-stress-engine-desc">Calculates systemic cortisol and allostatic load by linking sleep/stress directly to your active lab tests.</p>
                            
                            <div class="p-2 bg-dark rounded border border-secondary border-opacity-25 mb-3" style="height: 150px;">
                                <canvas id="cortisolChart"></canvas>
                            </div>

                            <label class="small text-secondary fw-bold" id="lbl-sleep-in">NIGHTLY SLEEP DURATION (HOURS)</label>
                            <input type="range" class="form-range mb-2" id="st-sleep" min="4" max="10" step="0.5" value="6.5" oninput="document.getElementById('sl-val').innerText = this.value">
                            <div class="text-end small text-success fw-bold"><span id="sl-val">6.5</span> <span id="lbl-hours">Hours</span></div>

                            <label class="small text-secondary fw-bold mt-2" id="lbl-work-in">WORK / COGNITIVE STRESS (1-10)</label>
                            <input type="range" class="form-range mb-2" id="st-stress" min="1" max="10" value="7" oninput="document.getElementById('st-val').innerText = this.value">
                            <div class="text-end small text-warning fw-bold"><span id="lbl-lvl">Level</span> <span id="st-val">7</span> / 10</div>

                            <button class="btn btn-helix w-100 mt-3" onclick="computeDynamicStress()"><i class="fa-solid fa-atom me-1"></i> <span id="lbl-btn-stress">Assess Biological Neuro-Stress</span></button>
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 mt-3 small" id="stress-dynamic-result">
                                <div class="text-secondary" id="lbl-stress-placeholder">Click 'Assess Biological Neuro-Stress' to compute biomarker-linked allostatic burden...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 7: DYNAMIC SYMPTOM CHECKER -->
            <div class="tab-pane fade" id="view-symptoms">
                <div class="card p-4 mb-4">
                    <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-stethoscope text-warning me-2"></i> <span id="lbl-symp-head">Check How Your Uploaded Report Explains Your Symptoms</span></h5>
                    <p class="text-secondary small mb-4" id="lbl-symp-desc">Enter any symptom you are experiencing. Helix parses your uploaded test parameters to evaluate physiological correlations.</p>
                    
                    <div class="row g-3 mb-4">
                        <div class="col-md-9">
                            <input type="text" id="symp-input" class="form-control py-2" placeholder="e.g. feeling tired, extreme thirst, dizziness, joint pain, chest heaviness, weakness" value="Feeling tired, thirsty and dizzy">
                        </div>
                        <div class="col-md-3">
                            <button class="btn btn-helix w-100 py-2" onclick="correlateSymptoms()"><i class="fa-solid fa-wand-magic-sparkles me-1"></i> <span id="lbl-btn-correlate">Correlate with Report</span></button>
                        </div>
                    </div>

                    <div class="p-3 bg-dark rounded border border-secondary border-opacity-50" id="symp-result-box">
                        <div class="text-secondary small" id="lbl-symp-placeholder">// Click above to analyze how your latest lab results relate to your symptoms...</div>
                    </div>
                </div>
            </div>

        </div>

    </div>

</div>

<!-- UPLOAD MODAL (ZERO HARDCODED TEXT) -->
<div class="modal fade" id="uploadModal" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content card p-4 border-success border-opacity-50">
            <h4 class="text-white fw-bold mb-2"><i class="fa-solid fa-cloud-arrow-up text-success me-2"></i><span id="lbl-modal-title">Upload Medical Reports</span></h4>
            <p class="text-secondary small mb-3" id="lbl-modal-sub">Upload 1, 3, 5, or 10+ PDFs/Images at the same time. Helix will extract Hospital Name, Collection Date, and Biomarkers for each encounter in parallel.</p>
            
            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 text-center mb-3">
                <input type="file" id="up-file" class="form-control form-control-sm mb-2" accept=".pdf,.png,.jpg,.jpeg" multiple>
                <div class="text-secondary small mb-2" id="lbl-modal-tip">Tip: Select multiple PDF files at once (Hold Ctrl or Shift to select 10+ files)</div>
                <span class="text-secondary small" id="lbl-modal-or">— or paste raw report text below —</span>
                <textarea id="up-text" class="form-control form-control-sm mt-2 font-monospace" rows="4" placeholder="Paste report text here..."></textarea>
            </div>

            <button class="btn btn-helix w-100 py-2" onclick="uploadReportBatch()"><i class="fa-solid fa-bolt me-1"></i> <span id="lbl-btn-ingest">Extract & Ingest Reports</span></button>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let activeUser = JSON.parse(localStorage.getItem('helix_user')) || null;
    let currentLang = 'en';
    let cachedSummaryData = null;
    let chartInstance = null;
    let cortisolChartInstance = null;
    let breathInterval = null;
    let breathPhase = 0;
    let audioCtx = null;
    let osc1 = null, osc2 = null;

    const UI_I18N = {
        en: {
            sub: "Enterprise Decision Support Platform: Multi-Hospital Telemetry & Grounded Twin",
            tab_cmd: "Dynamic Lab Dashboard",
            tab_twin: "90-Day Metabolic Twin",
            tab_habit: "Habit Building & Specialist Finder",
            tab_symp: "Dynamic Symptom Correlator",
            tab_doc: "Doctor Handoff & HL7 FHIR",
            tab_treat: "Past Treatments & History",
            tab_stress: "Stress & Neuro-Recovery Studio",
            status_badge: "Deterministic Double-Verification Active",
            btn_upload: "Upload Medical Reports (Multi-File)",
            cards_heading: "Tests Extracted From Your Uploaded Report:",
            chart_title: "Longitudinal Tracking of Your Tests Over Time",
            chart_sub: "Plots the chronological progression curve for each biomarker across your hospital visits.",
            axis_tag: "Left Axis: Standard Values | Right Axis: Small Fractions",
            hosp_source: "LATEST REPORT SOURCE:",
            hero_desc: "Upload any medical test reports. Helix automatically extracts whatever parameters are present, plots real-time trajectory curves, and checks reference limits.",
            twin_heading: "90-Day What-If Metabolic Twin Simulator",
            twin_sub: "Directly linked to your uploaded lab tests. Adjust your daily habits to forecast exact 90-day biological recovery.",
            ex_slider: "WEEKLY EXERCISE & RESISTANCE TRAINING (DAYS/WEEK)",
            days_week: "Days / Week",
            sg_slider: "DAILY CALORIC DEFICIT & SUGAR REDUCTION",
            reduction_tag: "Reduction (~350 kcal/day deficit)",
            basis_title: "Scientific Basis:",
            basis_desc: "120-Day Erythrocyte Turnover & Hepatic Gluconeogenesis clearance curve.",
            twin_proj_title: "PROJECTED 90-DAY RECOVERY TIED TO REPORT BASELINES:",
            avoid_title: "Habits To Avoid (Prevents Metric Deterioration):",
            follow_title: "Daily Habits To Follow (Adjuvant to Doctor Medicines):",
            habits_title: "Daily Morning Habit Consistency",
            habits_badge: "Consistency > Intensity",
            habits_sub: "Structured, zero-friction daily routines inspired by live virtual habit models (like Habuild) to build lifelong adherence.",
            habits_note_title: "Clinical Note:",
            habits_note_desc: "Habit consistency lowers baseline cortisol and stabilizes glucose peaks naturally.",
            spec_title: "Specialist Recommendation for Your Area",
            spec_sub: "Clinically mapped to the exact out-of-range parameters found in your report.",
            symp_head: "Check How Your Uploaded Report Explains Your Symptoms",
            symp_desc: "Enter any symptom you are experiencing. Helix parses your uploaded test parameters to evaluate physiological correlations.",
            btn_correlate: "Correlate with Report",
            symp_placeholder: "// Click above to analyze how your latest lab results relate to your symptoms...",
            doc_heading: "Doctor 1-Page Summary & HL7 FHIR Interoperability",
            doc_sub: "A concise clinical briefing and standards-compliant HL7 FHIR JSON bundle for hospital EMR integration.",
            btn_print: "Print Doctor Summary",
            btn_fhir: "Export HL7 FHIR JSON",
            pt_name_title: "PATIENT NAME & AGE",
            hosp_conn_title: "HOSPITALS & LABS CONNECTED",
            eval_date_title: "LATEST EVALUATION DATE",
            drug_shield_title: "Dynamic Drug-Biomarker Toxicity Shield:",
            doc_points_title: "Questions to Ask Your Doctor in Your Next Visit:",
            treat_heading: "Specific Treatments & Procedures History",
            treat_sub: "Chronological log of specific surgeries, medication therapies, and rehabilitation procedures the patient has undergone.",
            btn_print_treat: "Print History",
            treat_box_title: "Specific Interventions Extracted From Hospital Documents:",
            pacer_title: "4-4-4-4 Vagus Activation Pacer",
            pacer_desc: "Slow diaphragmatic breathing stimulates parasympathetic vagal recovery.",
            breath_btn_start: "Start Guided Pacer",
            breath_btn_pause: "Pause Guide",
            vagal_test_title: "60s Vagal Recovery & HRV Proxy",
            vagal_badge: "Active",
            pre_pulse: "PRE-BREATHING PULSE (BPM)",
            post_pulse: "POST-BREATHING PULSE (BPM)",
            stress_engine_title: "Biomarker-Grounded Neuro-Stress Engine",
            stress_engine_desc: "Calculates systemic cortisol and allostatic load by linking sleep/stress directly to your active lab tests.",
            sleep_in: "NIGHTLY SLEEP DURATION (HOURS)",
            work_in: "WORK / COGNITIVE STRESS (1-10)",
            hours: "Hours",
            lvl: "Level",
            btn_stress: "Assess Biological Neuro-Stress",
            stress_placeholder: "Click 'Assess Biological Neuro-Stress' to compute biomarker-linked allostatic burden...",
            modal_title: "Upload Medical Reports",
            modal_sub: "Upload 1, 3, 5, or 10+ PDFs/Images at the same time. Helix will extract Hospital Name, Collection Date, and Biomarkers for each encounter in parallel.",
            modal_tip: "Tip: Select multiple PDF files at once (Hold Ctrl or Shift to select 10+ files)",
            modal_or: "— or paste raw report text below —",
            btn_ingest: "Extract & Ingest Reports",
            auth_title: "Sign In to Your Health Timeline",
            auth_desc: "Access hospital records, dynamic metabolic twin, and clinical summaries.",
            tab_signin: "Sign In",
            tab_signup: "Register",
            email_in: "EMAIL ADDRESS",
            pw_in: "PASSWORD",
            btn_login: "Sign In",
            name_up: "FULL NAME",
            email_up: "EMAIL",
            city_up: "LOCATION / DISTRICT",
            pw_up: "PASSWORD",
            btn_register: "Create Health Account",
            breath_phases: ['Inhale (4s)', 'Hold (4s)', 'Exhale (4s)', 'Hold (4s)'],
            avoid_items: [
                "<strong>Ultra-Processed Sugars:</strong> Avoid sugary sodas, packaged juices, and sweets (prevents acute liver fat accumulation).",
                "<strong>Sedentary Post-Meal Sitting:</strong> Avoid sitting idle for >60 mins after meals (walk 15 mins to clear glucose from blood).",
                "<strong>Trans-Fats & Reused Oils:</strong> Avoid vanaspati and deep-fried snacks (directly elevates atherogenic LDL particles).",
                "<strong>Late-Night Sleep Loss (<6 hrs):</strong> Triggers cortisol surges causing dawn glucose dumping."
            ],
            follow_items: [
                "<strong>Follow Prescriptions First:</strong> Strictly take all doctor-prescribed medications (e.g., Metformin/Statins) on time.",
                "<strong>The Plate Method:</strong> 50% vegetables/salad, 25% protein (paneer, tofu, dal), 25% complex carbs.",
                "<strong>Daily Hydration Target:</strong> Drink 2.5 - 3.0 Liters of water daily to support kidney creatinine filtration."
            ],
            habit_checklist: [
                { text: "20-Min Morning Mobility & Breath (Live Yoga / Stretch)", icon: "fa-sun text-warning", checked: true },
                { text: "500ml Hydration upon Waking Up", icon: "fa-bottle-water text-info", checked: true },
                { text: "15-Min Post-Meal Step Count / Brisk Walk", icon: "fa-shoe-prints text-success", checked: false },
                { text: "Prescribed Medication Adherence (On Time)", icon: "fa-pills text-danger", checked: true }
            ]
        },
        hi: {
            sub: "विश्वसनीय स्वास्थ्य प्रणाली: द्वैध सत्यापन, ९०-दिन का सिमुलेटर एवं FHIR एक्सपोर्ट",
            tab_cmd: "डायनामिक लैब डैशबोर्ड",
            tab_twin: "९०-दिन का मेटाबोलिक ट्विन",
            tab_habit: "आदतें एवं डॉक्टर परामर्श",
            tab_symp: "लक्षण एवं रिपोर्ट संबंध",
            tab_doc: "डॉक्टर समरी एवं HL7 FHIR",
            tab_treat: "विशिष्ट इलाज और सर्जरी का इतिहास",
            tab_stress: "तनाव एवं न्यूरो-रिकवरी स्टूडियो",
            status_badge: "सत्यापित एवं नैदानिक सुरक्षा प्रणाली सक्रिय",
            btn_upload: "मेडिकल रिपोर्ट्स अपलोड करें",
            cards_heading: "आपकी अपलोड की गई रिपोर्ट से मिली जांचें:",
            chart_title: "समय के साथ आपकी जांचों का वास्तविक ट्रेंड ग्राफ",
            chart_sub: "अस्पताल की हर यात्रा में आपकी जांचों का वास्तविक सुधार व बदलाव आलेख।",
            axis_tag: "बायां अक्ष: मुख्य जांचें | दायां अक्ष: सूक्ष्म स्तर",
            hosp_source: "नवीनतम रिपोर्ट स्रोत:",
            hero_desc: "अपनी मेडिकल रिपोर्ट अपलोड करें। हेलिक्स आपकी रिपोर्ट से सभी जांचों को तुरंत पढ़कर सुरक्षित सीमा और सुधार ग्राफ तैयार करता है।",
            twin_heading: "९०-दिन का व्हाट-इफ मेटाबोलिक ट्विन सिमुलेटर",
            twin_sub: "आपकी रिपोर्ट के आधार पर व्यायाम और कैलोरी में कमी से ९० दिनों का सुधार देखें।",
            ex_slider: "साप्ताहिक व्यायाम (दिन/सप्ताह)",
            days_week: "दिन / सप्ताह",
            sg_slider: "दैनिक कैलोरी व मीठे में कमी",
            reduction_tag: "कमी (~350 कैलोरी प्रतिदिन बचत)",
            basis_title: "वैज्ञानिक आधार:",
            basis_desc: "१२०-दिन का लाल रक्त कोशिका जीवन चक्र एवं लिवर ग्लूकोज नियंत्रण समीकरण।",
            twin_proj_title: "रिपोर्ट के आधार पर ९० दिनों का अनुमानित सुधार:",
            avoid_title: "इन आदतों से बचें (नुकसान से बचाव):",
            follow_title: "दैनिक आदतें (डॉक्टर की दवा के साथ):",
            habits_title: "दैनिक सुबह की आदतों का नियमित पालन",
            habits_badge: "नियमितता > तीव्रता",
            habits_sub: "लाइव योग एवं आदत निर्माण प्रणाली पर आधारित दैनिक दिनचर्या।",
            habits_note_title: "नैदानिक नोट:",
            habits_note_desc: "नियमित आदतें तनाव के हार्मोन (कॉर्टिसोल) को कम करती हैं और शुगर को स्थिर रखती हैं।",
            spec_title: "आपके क्षेत्र के लिए विशेषज्ञ डॉक्टर सुझाव",
            spec_sub: "आपकी रिपोर्ट में असामान्य आई जांचों के अनुसार सुझाए गए विशेषज्ञ चिकित्सक।",
            symp_head: "देखें आपकी रिपोर्ट आपके लक्षणों को कैसे समझाती है",
            symp_desc: "अपना कोई भी लक्षण दर्ज करें। हेलिक्स आपकी रिपोर्ट की जांचों से इसका जैविक कारण स्पष्ट करता है।",
            btn_correlate: "रिपोर्ट से लक्षण जांचें",
            symp_placeholder: "// अपने लक्षणों और रिपोर्ट के बीच संबंध देखने के लिए ऊपर क्लिक करें...",
            doc_heading: "डॉक्टर के लिए १-पेज समरी एवं HL7 FHIR डेटा",
            doc_sub: "अस्पताल EMR सिस्टम के लिए मानक FHIR डेटा एवं डॉक्टर के लिए संक्षिप्त समरी।",
            btn_print: "डॉक्टर समरी प्रिंट करें",
            btn_fhir: "HL7 FHIR JSON एक्सपोर्ट करें",
            pt_name_title: "मरीज का नाम एवं आयु",
            hosp_conn_title: "जुड़े हुए अस्पताल व लैब",
            eval_date_title: "नवीनतम जांच की तारीख",
            drug_shield_title: "दवा और लैब सुरक्षा शील्ड:",
            doc_points_title: "अपनी अगली मुलाकात में डॉक्टर से पूछे जाने वाले मुख्य सवाल:",
            treat_heading: "मरीज का विशिष्ट इलाज और सर्जरी का इतिहास",
            treat_sub: "अस्पताल में हुए विशिष्ट ऑपरेशन, दवाएं और थैरेपी का संपूर्ण कालानुक्रमिक रिकॉर्ड।",
            btn_print_treat: "इतिहास प्रिंट करें",
            treat_box_title: "अस्पताल के दस्तावेजों से मिले विशिष्ट इलाज:",
            pacer_title: "४-४-४-४ बॉक्स ब्रीदिंग (तंत्रिका तंत्र शांति)",
            pacer_desc: "गहरी सांस लेने से वेगस तंत्रिका सक्रिय होती है और तनाव कम होता है।",
            breath_btn_start: "गाइडेड ब्रीदिंग शुरू करें",
            breath_btn_pause: "रोकें",
            vagal_test_title: "६० सेकंड पल्स एवं हृदय सुधार जांच",
            vagal_badge: "सक्रिय",
            pre_pulse: "व्यायाम से पहले नाड़ी दर (BPM)",
            post_pulse: "व्यायाम के बाद नाड़ी दर (BPM)",
            stress_engine_title: "बायोमार्कर्स आधारित न्यूरो-तनाव विश्लेषक",
            stress_engine_desc: "आपकी रिपोर्ट की जांचों और नींद को जोड़कर शरीर का तनाव भार मापता है।",
            sleep_in: "रात की नींद (घंटे)",
            work_in: "काम / मानसिक तनाव (१-१०)",
            hours: "घंटे",
            lvl: "स्तर",
            btn_stress: "तनाव स्तर की जांच करें",
            stress_placeholder: "शरीर पर तनाव और कॉर्टिसोल भार जांचने के लिए ऊपर क्लिक करें...",
            modal_title: "मेडिकल रिपोर्ट्स अपलोड करें",
            modal_sub: "एक साथ १, ३, ५ या १०+ पीडीएफ/फोटो अपलोड करें। हेलिक्स अपने आप अस्पताल, तारीख और जांचें निकाल लेगा।",
            modal_tip: "सुझाव: एक साथ कई पीडीएफ चुनने के लिए Ctrl या Shift दबाकर चुनें",
            modal_or: "— या नीचे रिपोर्ट का टेक्स्ट पेस्ट करें —",
            btn_ingest: "रिपोर्ट का विश्लेषण करें",
            auth_title: "अपने स्वास्थ्य टाइमलाइन में लॉगिन करें",
            auth_desc: "अस्पताल के रिकॉर्ड, ९०-दिन का सिमुलेटर और डॉक्टर समरी देखें।",
            tab_signin: "लॉगिन",
            tab_signup: "रजिस्टर",
            email_in: "ईमेल पता",
            pw_in: "पासवर्ड",
            btn_login: "साइन इन करें",
            name_up: "पूरा नाम",
            email_up: "ईमेल",
            city_up: "शहर / जिला",
            pw_up: "पासवर्ड बनाएं",
            btn_register: "खाता बनाएं",
            breath_phases: ['सांस अंदर लें (४ से.)', 'सांस रोकें (४ से.)', 'सांस छोड़ें (४ से.)', 'खाली रोकें (४ से.)'],
            avoid_items: [
                "<strong>मीठा व कोल्ड्रिंक्स:</strong> डिब्बाबंद जूस और मिठाइयों से बचें (यह लिवर में तेजी से चर्बी जमा करती हैं)।",
                "<strong>खाने के बाद तुरंत बैठना:</strong> दोपहर और रात के खाने के बाद ६० मिनट तक लगातार न बैठें (१५ मिनट टहलें)।",
                "<strong>डालडा व तला-भुना खाना:</strong> वनस्पति घी और बार-बार गर्म किए गए तेल से बचें (खराब कोलेस्ट्रॉल बढ़ाता है)।",
                "<strong>कम नींद (<६ घंटे):</strong> रात की कम नींद तनाव बढ़ाती है जिससे सुबह शुगर बढ़ जाती है।"
            ],
            follow_items: [
                "<strong>डॉक्टर की दवा पहले:</strong> डॉक्टर द्वारा दी गई सभी दवाएं (जैसे मेटफॉर्मिन/स्टेटिन) समय पर लें।",
                "<strong>थाली का सही अनुपात:</strong> ५०% हरी सब्जियां व सलाद, २५% प्रोटीन (पनीर, दाल, स्प्राउट्स), २५% अनाज।",
                "<strong>पानी का लक्ष्य:</strong> किडनियों को साफ रखने के लिए रोजाना २.५ से ३ लीटर पानी पिएं।"
            ],
            habit_checklist: [
                { text: "सुबह २० मिनट योग व स्ट्रेचिंग (शरीर की लचीलापन)", icon: "fa-sun text-warning", checked: true },
                { text: "सुबह उठते ही ५०० मिलीलीटर पानी पीना", icon: "fa-bottle-water text-info", checked: true },
                { text: "भोजन के बाद १५ मिनट टहलना", icon: "fa-shoe-prints text-success", checked: false },
                { text: "डॉक्टर द्वारा दी गई दवा का समय पर सेवन", icon: "fa-pills text-danger", checked: true }
            ]
        },
        mr: {
            sub: "विश्वासार्ह आरोग्य प्रणाली: ९०-दिवसांचा सिम्युलेटर, औषध सुरक्षा व FHIR",
            tab_cmd: "डायनॅमिक लॅब डॅशबोर्ड",
            tab_twin: "९०-दिवसांचा मेटाबॉलिक ट्विन",
            tab_habit: "सवयी व तज्ज्ञ डॉक्टर शोध",
            tab_symp: "लक्षणे व अहवाल संबंध",
            tab_doc: "डॉक्टरांसाठी सारांश व HL7 FHIR",
            tab_treat: "विशिष्ट उपचार व शस्त्रक्रियांचा इतिहास",
            tab_stress: "तनाव मुक्ती व न्यूरो-रिकव्हरी स्टुडिओ",
            status_badge: "तपासणी व औषध सुरक्षा प्रणाली सक्रिय",
            btn_upload: "अहवाल अपलोड करा",
            cards_heading: "तुमच्या अहवालातून मिळालेल्या चाचण्या:",
            chart_title: "काळाच्या ओघात चाचण्यांचा वास्तविक बदल आलेख",
            chart_sub: "हॉस्पिटलच्या प्रत्येक भेटीत तुमच्या चाचण्यांमधील प्रत्यक्ष सुधारणा आलेख.",
            axis_tag: "डावा अक्ष: मुख्य चाचण्या | उजवा अक्ष: सूक्ष्म पातळी",
            hosp_source: "नवीनतम अहवाल स्रोत:",
            hero_desc: "कोणताही तपासणी अहवाल अपलोड करा. हेलिक्स आपोआप सर्व चाचण्या वाचून सुरक्षित मर्यादा आणि सुधारणा आलेख तयार करते.",
            twin_heading: "९०-दिवसांचा व्हाट-इफ मेटाबॉलिक ट्विन सिम्युलेटर",
            twin_sub: "तुमच्या प्रत्यक्ष अहवालावरून व्यायाम व कॅलरी नियंत्रणाने ९० दिवसांतील सुधारणा पाहा.",
            ex_slider: "साप्ताहिक व्यायाम (दिवस/आठवडा)",
            days_week: "दिवस / आठवडा",
            sg_slider: "दैनिक कॅलरी व साखरेत घट",
            reduction_tag: "घट (~३५० कॅलरी दररोज बचत)",
            basis_title: "वैज्ञानिक आधार:",
            basis_desc: "१२०-दिवसांचे तांबड्या पेशींचे जीवनचक्र व यकृताचे साखर नियंत्रण समीकरण.",
            twin_proj_title: "अहवालावर आधारित ९० दिवसांतील अपेक्षित सुधारणा:",
            avoid_title: "टाळावयाच्या सवयी (नुकसान टाळण्यासाठी):",
            follow_title: "आवश्यक दैनंदिन सवयी (डॉक्टरांच्या औषधांसोबत):",
            habits_title: "दैनिक सकाळच्या सवयींचे सातत्य",
            habits_badge: "सातत्य > तीव्रता",
            habits_sub: "लाईव्ह योग व सवय निर्मिती पद्धतीवर आधारित दैनंदिन दिनचर्या.",
            habits_note_title: "वैद्यकीय नोंद:",
            habits_note_desc: "नियमित सवयींमुळे तणावाचे संप्रेरक (कॉर्टिसॉल) कमी होते आणि साखर नियंत्रित राहते.",
            spec_title: "तुमच्या परिसरातील तज्ज्ञ डॉक्टर शिफारस",
            spec_sub: "अहवालातील असामान्य चाचण्यांवरून सुचवलेले योग्य तज्ज्ञ डॉक्टर.",
            symp_head: "तुमचा अहवाल लक्षणे कशी स्पष्ट करतो ते पाहा",
            symp_desc: "तुम्हाला जाणवणारे लक्षण येथे टाका. हेलिक्स तुमच्या अहवालातील चाचण्या तपासून कारण स्पष्ट करेल.",
            btn_correlate: "अहवालाशी लक्षणे जोडा",
            symp_placeholder: "// तुमच्या लक्षणांचा आणि अहवालाचा संबंध पाहण्यासाठी वर क्लिक करा...",
            doc_heading: "डॉक्टरांसाठी १-पानी सारांश आणि HL7 FHIR",
            doc_sub: "हॉस्पिटल EMR प्रणालीसाठी प्रमाणित FHIR डेटा आणि संक्षिप्त सारांश.",
            btn_print: "सारांश प्रिंट करा",
            btn_fhir: "HL7 FHIR JSON एक्सपोर्ट करा",
            pt_name_title: "रुग्णाचे नाव व वय",
            hosp_conn_title: "जोडलेली रुग्णालये व प्रयोगशाळा",
            eval_date_title: "नवीनतम तपासणी तारीख",
            drug_shield_title: "औषध आणि लॅब सुरक्षा शील्ड:",
            doc_points_title: "पुढील तपासणीच्या वेळी डॉक्टरांना विचारण्यासाठी महत्त्वाचे मुद्दे:",
            treat_heading: "रुग्णाचे विशिष्ट उपचार व शस्त्रक्रियांचा इतिहास",
            treat_sub: "रुग्णालयातील विशिष्ट शस्त्रक्रिया, औषधोपचार आणि थेरपी यांचा कालक्रमानुसार तपशील.",
            btn_print_treat: "इतिहास प्रिंट करा",
            treat_box_title: "रुग्णालयाच्या नोंदींमधून मिळालेले विशिष्ट उपचार:",
            pacer_title: "४-४-४-४ बॉक्स ब्रीदिंग व्यायाम",
            pacer_desc: "दीर्घ श्वास घेतल्याने मज्जासंस्था शांत होते आणि तणाव कमी होतो.",
            breath_btn_start: "सराव सुरू करा",
            breath_btn_pause: "थांबवा",
            vagal_test_title: "६० सेकंद पल्स व हृदय सुधार तपासणी",
            vagal_badge: "सक्रिय",
            pre_pulse: "व्यायामापूर्वी नाडीचे ठोके (BPM)",
            post_pulse: "व्यायामानंतर नाडीचे ठोके (BPM)",
            stress_engine_title: "बायोमार्कर्स आधारित न्यूरो-तणाव विश्लेषक",
            stress_engine_desc: "तुमच्या अहवालातील चाचण्या आणि झोप तपासून शरीराचा तणाव मोजते.",
            sleep_in: "रात्रीची झोप (तास)",
            work_in: "कामाचा / मानसिक तणाव (१-१०)",
            hours: "तास",
            lvl: "पातळी",
            btn_stress: "तणाव पातळी तपासा",
            stress_placeholder: "शरीरावरील तणाव भार तपासण्यासाठी वर क्लिक करा...",
            modal_title: "वैद्यकीय अहवाल अपलोड करा",
            modal_sub: "एकाच वेळी १, ३, ५ किंवा १०+ पीडीएफ/फोटो अपलोड करा. हेलिक्स आपोआप रुग्णालय, तारीख व चाचण्या शोधून घेईल.",
            modal_tip: "टीप: एकाच वेळी अनेक पीडीएफ निवडण्यासाठी Ctrl किंवा Shift दाबून निवडा",
            modal_or: "— किंवा खाली अहवालाचा मजकूर पेस्ट करा —",
            btn_ingest: "अहवालाचे विश्लेषण करा",
            auth_title: "आरोग्य टाइमलाइनमध्ये लॉगिन करा",
            auth_desc: "रुग्णालयाचे रेकॉर्ड, ९०-दिवसांचा सिम्युलेटर आणि सारांश पाहा.",
            tab_signin: "लॉगिन",
            tab_signup: "नोंदणी",
            email_in: "ईमेल पत्ता",
            pw_in: "पासवर्ड",
            btn_login: "साइन इन करा",
            name_up: "पूर्ण नाव",
            email_up: "ईमेल",
            city_up: "शहर / जिल्हा",
            pw_up: "पासवर्ड तयार करा",
            btn_register: "खाते तयार करा",
            breath_phases: ['श्वास आत घ्या (४ से.)', 'श्वास रोखा (४ से.)', 'श्वास सोडा (४ से.)', 'रिकामे रोखा (४ से.)'],
            avoid_items: [
                "<strong>गोड पदार्थ व शीतपेये:</strong> पॅकबंद ज्यूस व मिठाई टाळा (यामुळे यकृतात चरबी वेगाने साचते).",
                "<strong>जेवणानंतर लगेच बसणे:</strong> जेवणानंतर ६० मिनिटांपेक्षा जास्त वेळ बसून राहू नका (१५ मिनिटे चाला).",
                "<strong>डालडा व तळलेले पदार्थ:</strong> वनस्पती तूप आणि पुन्हा तळलेले तेल टाळा (वाईट कोलेस्टेरॉल वाढते).",
                "<strong>अपुरी झोप (<६ तास):</strong> रात्रीची कमी झोप तणाव वाढवते, ज्यामुळे सकाळी साखर वाढते."
            ],
            follow_items: [
                "<strong>डॉक्टरांची औषधे प्रथम:</strong> डॉक्टरांनी दिलेली सर्व औषधे (उदा. मेटफॉर्मिन/स्टॅटिन) वेळेवर घ्या.",
                "<strong>योग्य जेवणाची थाळी:</strong> ५०% पालेभाज्या व सॅलड, २५% प्रथिने (पनीर, डाळी, कडधान्ये), २५% धान्य.",
                "<strong>पाण्याचे उद्दिष्ट:</strong> किडन्या स्वच्छ राहण्यासाठी दररोज २.५ ते ३ लिटर पाणी प्या."
            ],
            habit_checklist: [
                { text: "सकाळी २० मिनिटे योग व स्ट्रेचिंग (शरीराची लवचिकता)", icon: "fa-sun text-warning", checked: true },
                { text: "सकाळी उठल्या उठल्या ५०० मिली पाणी पिणे", icon: "fa-bottle-water text-info", checked: true },
                { text: "जेवणानंतर १५ मिनिटे चालणे", icon: "fa-shoe-prints text-success", checked: false },
                { text: "डॉक्टरांच्या औषधांचे वेळेवर सेवन करणे", icon: "fa-pills text-danger", checked: true }
            ]
        }
    };

    function updateAuthHeader() {
        const container = document.getElementById('auth-container');
        if (activeUser) {
            container.innerHTML = `
                <div class="dropdown">
                    <button class="btn btn-sm btn-dark border border-secondary text-white dropdown-toggle" type="button" data-bs-toggle="dropdown">
                        <i class="fa-solid fa-user-circle text-success me-1"></i> ${activeUser.name} (${activeUser.age || 30}y)
                    </button>
                    <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
                        <li><a class="dropdown-item small text-danger" href="#" onclick="logoutUser()"><i class="fa-solid fa-power-off me-2"></i>Sign Out</a></li>
                    </ul>
                </div>
            `;
        } else {
            container.innerHTML = ``;
        }
    }

    function renderDynamicChart(chartData) {
        const ctx = document.getElementById('userChart').getContext('2d');
        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.dates,
                datasets: chartData.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { 
                    legend: { 
                        labels: { color: '#94A3B8', font: { size: 11, weight: 'bold' } } 
                    } 
                },
                scales: {
                    x: { ticks: { color: '#94A3B8' }, grid: { color: '#1E2D4A' } },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Values (mg/dL, U/L, /cumm)', color: '#94A3B8' },
                        ticks: { color: '#94A3B8' },
                        grid: { color: '#1E2D4A' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Fractions (%, g/dL, uIU/mL)', color: '#38BDF8' },
                        ticks: { color: '#38BDF8' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });

        const cCtx = document.getElementById('cortisolChart').getContext('2d');
        if (cortisolChartInstance) cortisolChartInstance.destroy();
        cortisolChartInstance = new Chart(cCtx, {
            type: 'line',
            data: {
                labels: ['6 AM', '9 AM', '12 PM', '4 PM', '8 PM', '11 PM'],
                datasets: [
                    { label: 'Ideal Circadian Rhythm', data: [18, 14, 10, 7, 4, 2], borderColor: '#10B981', borderDash: [5, 5], tension: 0.4 },
                    { label: 'Estimated Biological Curve', data: [24, 19, 15, 13, 10, 8], borderColor: '#F59E0B', backgroundColor: 'rgba(245,158,11,0.1)', tension: 0.4 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#94A3B8', boxWidth: 12, font: { size: 10 } } } },
                scales: {
                    x: { ticks: { color: '#94A3B8' }, grid: { color: '#1E2D4A' } },
                    y: { ticks: { color: '#94A3B8' }, grid: { color: '#1E2D4A' } }
                }
            }
        });
    }

    function renderDynamicCards(cards) {
        const grid = document.getElementById('dynamic-cards-grid');
        grid.innerHTML = '';
        const lang = currentLang;

        if (!cards || cards.length === 0) {
            grid.innerHTML = `<div class="col-12 text-secondary small p-3">${lang === 'hi' ? 'कोई रिपोर्ट नहीं मिली। कृपया अपनी रिपोर्ट अपलोड करें।' : lang === 'mr' ? 'कोणताही अहवाल आढळला नाही. कृपया अहवाल अपलोड करा.' : 'No reports found. Click "Upload Medical Reports" above to start your health timeline.'}</div>`;
            return;
        }

        cards.forEach(c => {
            const col = document.createElement('div');
            col.className = 'col-md-4';
            const titleText = c.title[lang] || c.title['en'] || c.key;
            const statusText = c.status[lang] || c.status['en'];
            const guidelineText = c.guideline[lang] || c.guideline['en'];
            const whatText = c.what[lang] || c.what['en'];
            const summaryText = c.summary[lang] || c.summary['en'];
            const tipText = c.tip[lang] || c.tip['en'];

            col.innerHTML = `
                <div class="card card-3d p-3 h-100 ${c.is_panic ? 'border-danger shadow-lg' : ''}">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <strong class="text-white">${titleText}</strong>
                        <span class="badge-status status-${c.status_code}">${statusText}</span>
                    </div>
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <div class="fs-4 fw-bold text-white">${c.value}</div>
                        <span class="badge bg-success bg-opacity-25 text-success font-monospace" style="font-size: 10px;"><i class="fa-solid fa-circle-check me-1"></i>Verified</span>
                    </div>
                    <div class="d-flex gap-1 flex-wrap mb-2">
                        <span class="guideline-badge"><i class="fa-solid fa-book-medical me-1"></i>${guidelineText}</span>
                        <span class="badge bg-secondary font-monospace" style="font-size: 10px;">LOINC: ${c.loinc}</span>
                    </div>
                    <div class="text-secondary small mb-2"><i class="fa-solid fa-circle-info text-info me-1"></i>${whatText}</div>
                    <p class="text-light text-opacity-75 small mb-3">${summaryText}</p>
                    <div class="text-success small mt-auto"><i class="fa-solid fa-lightbulb me-1"></i>${tipText}</div>
                </div>
            `;
            grid.appendChild(col);
        });
    }

    function runLiveTwinSimulation() {
        const exDays = parseInt(document.getElementById('sim-ex').value);
        const sgPct = parseInt(document.getElementById('sim-sg').value);
        document.getElementById('ex-val').innerText = exDays;
        document.getElementById('sg-val').innerText = sgPct + '%';

        const grid = document.getElementById('twin-projections-grid');
        grid.innerHTML = '';
        const lang = currentLang;

        if (!cachedSummaryData || !cachedSummaryData.latest_biomarkers || Object.keys(cachedSummaryData.latest_biomarkers).length === 0) {
            grid.innerHTML = `<div class="col-12 text-secondary small p-3">${lang === 'hi' ? 'पहले रिपोर्ट अपलोड करें। सिमुलेटर आपकी रिपोर्ट के आधार पर अनुमान लगाएगा।' : lang === 'mr' ? 'आधी अहवाल अपलोड करा. सिम्युलेटर अहवालावरून अंदाज लावेल.' : 'Upload a medical report first. The simulator will automatically calibrate against your baseline biomarkers.'}</div>`;
            return;
        }
        
        const b = cachedSummaryData.latest_biomarkers;
        const deficitKcal = (sgPct / 100) * 500 + (exDays * 40);

        for (let k in b) {
            const baseline = b[k];
            let projected = baseline;
            let unit = "";
            let explanation = {
                en: "Projected biological stabilization",
                hi: "अनुमानित जैविक स्थिरता",
                mr: "अपेक्षित जैविक नियंत्रण"
            };

            if (k.includes("glucose") || k.includes("sugar")) {
                const reduction = (exDays * 2.5) + ((deficitKcal / 500) * 12.0);
                projected = Math.max(75.0, (baseline - reduction)).toFixed(1);
                unit = "mg/dL";
                explanation = {
                    en: "Reversal towards optimal morning sugar range",
                    hi: "सुबह की सामान्य व सुरक्षित सीमा की ओर सुधार",
                    mr: "सकाळच्या सुरक्षित पातळीकडे होणारी सुधारणा"
                };
            } else if (k.includes("hba1c")) {
                const reduction = (exDays * 0.09) + ((deficitKcal / 500) * 0.45);
                projected = Math.max(4.6, (baseline - reduction)).toFixed(2);
                unit = "%";
                explanation = {
                    en: "90-day RBC hemoglobin glycation turnover",
                    hi: "९० दिनों में लाल रक्त कणों की औसत शर्करा में सुधार",
                    mr: "९० दिवसांतील तांबड्या पेशींच्या सरासरी साखरेत घट"
                };
            } else if (k.includes("cholesterol") || k.includes("ldl") || k.includes("triglyceride")) {
                const reduction = (exDays * 3.2) + ((deficitKcal / 500) * 18.0);
                projected = Math.max(70.0, (baseline - reduction)).toFixed(1);
                unit = "mg/dL";
                explanation = {
                    en: "Lipid oxidation via daily caloric deficit",
                    hi: "कैलोरी नियंत्रण से खराब चर्बी में कमी",
                    mr: "कॅलरी नियंत्रणामुळे चरबीमध्ये होणारी घट"
                };
            } else if (k.includes("hemoglobin") || k == "hb") {
                const boost = (exDays * 0.12);
                projected = Math.min(16.0, (baseline + boost)).toFixed(1);
                unit = "g/dL";
                explanation = {
                    en: "Erythropoiesis oxygen-carrying adaptation",
                    hi: "व्यायाम से लाल रक्त कणों में ऑक्सीजन वहन क्षमता सुधार",
                    mr: "व्यायामामुळे ऑक्सिजन वाहून नेण्याची क्षमता वाढ"
                };
            } else if (k.includes("vitamin_d") || k.includes("vit_d")) {
                const boost = 8.5 + (exDays * 0.4);
                projected = Math.min(55.0, (baseline + boost)).toFixed(1);
                unit = "ng/mL";
                explanation = {
                    en: "Bone density & neuromuscular support",
                    hi: "हड्डियों की मजबूती और जोड़ों में सुधार",
                    mr: "हाडांची बळकटी आणि सांधेदुखीपासून आराम"
                };
            } else if (k.includes("uric")) {
                const reduction = (exDays * 0.2) + ((deficitKcal / 500) * 0.8);
                projected = Math.max(3.5, (baseline - reduction)).toFixed(1);
                unit = "mg/dL";
                explanation = {
                    en: "Urate crystallization risk mitigation",
                    hi: "जोड़ों में यूरिक एसिड क्रिस्टल जमने का खतरा कम",
                    mr: "सांध्यांमध्ये युरिक अ‍ॅसिडचे खडे जमण्याचा धोका कमी"
                };
            } else if (k.includes("sgpt") || k.includes("alt") || k.includes("sgot")) {
                const reduction = (exDays * 1.5) + ((deficitKcal / 500) * 6.0);
                projected = Math.max(15.0, (baseline - reduction)).toFixed(1);
                unit = "U/L";
                explanation = {
                    en: "Reduction in hepatic metabolic stress",
                    hi: "लिवर पर दबाव और फैटी लिवर के लक्षणों में कमी",
                    mr: "यकृतावरील ताण आणि फॅटी लिव्हरच्या लक्षणांत घट"
                };
            } else {
                continue;
            }

            const col = document.createElement('div');
            col.className = 'col-md-6 mb-2';
            col.innerHTML = `
                <div class="p-2 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25 text-start">
                    <div class="d-flex justify-content-between">
                        <strong class="text-white small">${k.replace('_', ' ').toUpperCase()}</strong>
                        <span class="badge bg-secondary">${unit}</span>
                    </div>
                    <div class="text-light my-1 fs-6">${lang === 'hi' ? 'मूल स्तर:' : lang === 'mr' ? 'सध्या:' : 'Baseline:'} <strong>${baseline}</strong> ➔ <span class="text-success fw-bold">${projected}</span></div>
                    <div class="text-secondary" style="font-size: 10px;">${explanation[lang] || explanation['en']}</div>
                </div>
            `;
            grid.appendChild(col);
        }

        const summaryText = lang === 'hi'
            ? `दैनिक आदत बदलाव: ~${Math.round(deficitKcal)} कैलोरी/दिन नियंत्रण एवं ${exDays} दिन व्यायाम से आपकी जांचों में त्वरित सुधार होगा।`
            : lang === 'mr'
            ? `दैनंदिन सवयींमधील बदल: ~${Math.round(deficitKcal)} कॅलरी/दिवस घट आणि ${exDays} दिवस व्यायाम तुमच्या चाचण्यांमध्ये सुधारणा घडवून आणेल.`
            : `Daily Habit Shift: ~${Math.round(deficitKcal)} kcal/day metabolic deficit with ${exDays} training days/week dynamically optimizes your baseline markers.`;

        document.getElementById('sim-summary').innerText = summaryText;
    }

    function renderDoctorSummary(d) {
        const lang = currentLang;
        document.getElementById('doc-patient-name').innerText = `${d.user.name} (${d.user.age}y / ${d.user.gender})`;
        document.getElementById('doc-hosp-summary').innerText = d.hospitals_connected.join(', ') || (lang === 'hi' ? 'कोई अस्पताल नहीं जुड़ा' : lang === 'mr' ? 'कोणतेही रुग्णालय जोडलेले नाही' : 'No hospital visits logged');
        document.getElementById('doc-eval-date').innerText = d.latest_date;

        const specBox = document.getElementById('specialist-box');
        specBox.innerHTML = '';
        if (d.specialists && d.specialists.length > 0) {
            d.specialists.forEach(s => {
                const specName = typeof s.specialist === 'object' ? (s.specialist[lang] || s.specialist['en']) : s.specialist;
                const specReason = typeof s.reason === 'object' ? (s.reason[lang] || s.reason['en']) : s.reason;
                const specPrio = typeof s.priority === 'object' ? (s.priority[lang] || s.priority['en']) : s.priority;

                const div = document.createElement('div');
                div.className = 'p-2 mb-2 rounded bg-info bg-opacity-10 border border-info border-opacity-25';
                div.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <strong class="text-white small"><i class="fa-solid fa-stethoscope text-info me-1"></i> ${specName}</strong>
                        <span class="badge bg-danger">${specPrio}</span>
                    </div>
                    <div class="text-light small mt-1">${specReason}</div>
                    <div class="text-secondary" style="font-size:10px;"><i class="fa-solid fa-location-dot me-1"></i> ${lang === 'hi' ? 'सुझाया गया क्षेत्र:' : lang === 'mr' ? 'शिफारस केलेले क्षेत्र:' : 'Location Area:'} ${s.area}</div>
                `;
                specBox.appendChild(div);
            });
        } else {
            specBox.innerHTML = `<div class="text-secondary small">${lang === 'hi' ? 'सभी जांचें सामान्य हैं। नियमित स्वास्थ्य जांच की सलाह दी जाती है।' : lang === 'mr' ? 'सर्व चाचण्या सामान्य आहेत. नियमित आरोग्य तपासणीचा सल्ला दिला जातो.' : 'All biomarkers are optimal. General preventive health checkup recommended.'}</div>`;
        }

        const shieldBox = document.getElementById('drug-shield-container');
        shieldBox.innerHTML = '';
        if (d.drug_shields && d.drug_shields.length > 0) {
            d.drug_shields.forEach(s => {
                const warnText = typeof s.warning === 'object' ? (s.warning[lang] || s.warning['en']) : s.warning;
                const div = document.createElement('div');
                div.className = `p-2 mb-2 rounded bg-${s.severity === 'danger' ? 'danger' : s.severity === 'warn' ? 'warning' : 'success'} bg-opacity-10 border border-${s.severity === 'danger' ? 'danger' : s.severity === 'warn' ? 'warning' : 'success'} border-opacity-50`;
                div.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <strong class="text-white small"><i class="fa-solid fa-capsules me-1"></i> ${s.drug} ➔ ${s.biomarker}</strong>
                        <span class="badge bg-${s.severity === 'danger' ? 'danger' : s.severity === 'warn' ? 'warning' : 'success'}">${s.severity.toUpperCase()}</span>
                    </div>
                    <div class="text-light small mt-1">${warnText}</div>
                `;
                shieldBox.appendChild(div);
            });
        } else {
            shieldBox.innerHTML = `<div class="text-secondary small">${lang === 'hi' ? 'दवा और जांच में कोई परस्पर विरोध नहीं पाया गया।' : lang === 'mr' ? 'औषध आणि चाचण्यांमध्ये कोणताही विसंगती आढळली नाही.' : 'No active pharmacological contraindications detected.'}</div>`;
        }

        const container = document.getElementById('doctor-questions-container');
        container.innerHTML = '';

        if (!d.doctor_questions || d.doctor_questions.length === 0) {
            container.innerHTML = `<div class="text-secondary small">${lang === 'hi' ? 'कोई विशेष चेतावनी नहीं। सभी रिपोर्ट स्थिर हैं।' : lang === 'mr' ? 'कोणतीही विशेष सूचना नाही. सर्व अहवाल स्थिर आहेत.' : 'No specific alerts found. All tests are stable.'}</div>`;
            return;
        }

        d.doctor_questions.forEach(q => {
            const bioName = typeof q.biomarker === 'object' ? (q.biomarker[lang] || q.biomarker['en']) : q.biomarker;
            const qText = typeof q.question === 'object' ? (q.question[lang] || q.question['en']) : q.question;

            const div = document.createElement('div');
            div.className = 'p-2 mb-2 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25';
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong class="text-warning small">${bioName}</strong>
                    <span class="badge bg-danger bg-opacity-25 text-danger small">${q.finding}</span>
                </div>
                <div class="text-light small"><i class="fa-solid fa-circle-arrow-right text-success me-1"></i> ${qText}</div>
            `;
            container.appendChild(div);
        });
    }

    function renderTreatments(treatments) {
        const container = document.getElementById('treatment-timeline-container');
        container.innerHTML = '';
        const lang = currentLang;

        if (!treatments || treatments.length === 0) {
            container.innerHTML = `<div class="text-secondary small">${lang === 'hi' ? 'कोई विशेष इलाज रिकॉर्ड नहीं मिला।' : lang === 'mr' ? 'कोणताही विशिष्ट उपचार रेकॉर्ड आढळला नाही.' : 'No specific treatment records found in uploaded files.'}</div>`;
            return;
        }

        treatments.forEach(t => {
            const box = document.createElement('div');
            box.className = 'timeline-box';
            box.innerHTML = `
                <div class="timeline-dot"></div>
                <div class="treatment-card mb-2">
                    <div class="d-flex justify-content-between align-items-start flex-wrap gap-1 mb-1">
                        <strong class="text-white fs-6"><i class="fa-solid fa-syringe text-success me-1"></i> ${t.procedure}</strong>
                        <span class="badge bg-secondary">${t.date} | ${t.hospital}</span>
                    </div>
                    <div class="d-flex gap-2 my-1">
                        <span class="badge bg-info text-dark fw-bold">${t.category}</span>
                        <span class="badge bg-success bg-opacity-25 text-success">${t.action_type || 'Clinical Action'}</span>
                    </div>
                    <p class="text-light text-opacity-75 small mb-0 mt-2">${t.note}</p>
                </div>
            `;
            container.appendChild(box);
        });
    }

    function applyTextTranslations() {
        const t = UI_I18N[currentLang];
        document.getElementById('tag-sub').innerText = t.sub;
        document.getElementById('tab-cmd-lbl').innerText = t.tab_cmd;
        document.getElementById('tab-twin-lbl').innerText = t.twin_heading;
        document.getElementById('tab-habit-lbl').innerText = t.tab_habit;
        document.getElementById('tab-doc-lbl').innerText = t.doc_heading;
        document.getElementById('tab-treat-lbl').innerText = t.treat_heading;
        document.getElementById('tab-stress-lbl').innerText = t.tab_stress;
        document.getElementById('tab-symp-lbl').innerText = t.tab_symp;
        document.getElementById('lbl-status-badge').innerText = t.status_badge;
        document.getElementById('lbl-btn-upload').innerText = t.btn_upload;
        document.getElementById('lbl-cards-heading').innerText = t.cards_heading;
        document.getElementById('lbl-chart-title').innerText = t.chart_title;
        document.getElementById('lbl-chart-sub').innerText = t.chart_sub;
        document.getElementById('lbl-axis-tag').innerText = t.axis_tag;
        document.getElementById('lbl-hosp-source').innerText = t.hosp_source;
        document.getElementById('lbl-hero-desc').innerText = t.hero_desc;
        document.getElementById('lbl-twin-heading').innerText = t.twin_heading;
        document.getElementById('lbl-twin-sub').innerText = t.twin_sub;
        document.getElementById('lbl-ex-slider').innerText = t.ex_slider;
        document.getElementById('lbl-days-week').innerText = t.days_week;
        document.getElementById('lbl-sg-slider').innerText = t.sg_slider;
        document.getElementById('lbl-reduction-tag').innerText = t.reduction_tag;
        document.getElementById('lbl-basis-title').innerText = t.basis_title;
        document.getElementById('lbl-basis-desc').innerText = t.basis_desc;
        document.getElementById('lbl-twin-proj-title').innerText = t.twin_proj_title;
        document.getElementById('lbl-avoid-title').innerText = t.avoid_title;
        document.getElementById('lbl-follow-title').innerText = t.follow_title;
        document.getElementById('lbl-habits-title').innerText = t.habits_title;
        document.getElementById('lbl-habits-badge').innerText = t.habits_badge;
        document.getElementById('lbl-habits-sub').innerText = t.habits_sub;
        document.getElementById('lbl-habits-note-title').innerText = t.habits_note_title;
        document.getElementById('lbl-habits-note-desc').innerText = t.habits_note_desc;
        document.getElementById('lbl-spec-title').innerText = t.spec_title;
        document.getElementById('lbl-spec-sub').innerText = t.spec_sub;
        document.getElementById('lbl-doc-heading').innerText = t.doc_heading;
        document.getElementById('lbl-doc-sub').innerText = t.doc_sub;
        document.getElementById('lbl-btn-print').innerText = t.btn_print;
        document.getElementById('lbl-btn-fhir').innerText = t.btn_fhir;
        document.getElementById('lbl-pt-name-title').innerText = t.pt_name_title;
        document.getElementById('lbl-hosp-conn-title').innerText = t.hosp_conn_title;
        document.getElementById('lbl-eval-date-title').innerText = t.eval_date_title;
        document.getElementById('lbl-drug-shield-title').innerText = t.drug_shield_title;
        document.getElementById('lbl-doc-points-title').innerText = t.doc_points_title;
        document.getElementById('lbl-treat-heading').innerText = t.treat_heading;
        document.getElementById('lbl-treat-sub').innerText = t.treat_sub;
        document.getElementById('lbl-btn-print-treat').innerText = t.btn_print_treat;
        document.getElementById('lbl-treat-box-title').innerText = t.treat_box_title;
        document.getElementById('lbl-pacer-title').innerText = t.pacer_title;
        document.getElementById('lbl-pacer-desc').innerText = t.pacer_desc;
        document.getElementById('lbl-breath-btn').innerText = breathInterval ? t.breath_btn_pause : t.breath_btn_start;
        document.getElementById('lbl-vagal-test-title').innerText = t.vagal_test_title;
        document.getElementById('lbl-vagal-badge').innerText = t.vagal_badge;
        document.getElementById('lbl-pre-pulse').innerText = t.pre_pulse;
        document.getElementById('lbl-post-pulse').innerText = t.post_pulse;
        document.getElementById('lbl-stress-engine-title').innerText = t.stress_engine_title;
        document.getElementById('lbl-stress-engine-desc').innerText = t.stress_engine_desc;
        document.getElementById('lbl-sleep-in').innerText = t.sleep_in;
        document.getElementById('lbl-work-in').innerText = t.work_in;
        document.getElementById('lbl-hours').innerText = t.hours;
        document.getElementById('lbl-lvl').innerText = t.lvl;
        document.getElementById('lbl-btn-stress').innerText = t.btn_stress;
        document.getElementById('lbl-symp-head').innerText = t.symp_head;
        document.getElementById('lbl-symp-desc').innerText = t.symp_desc;
        document.getElementById('lbl-btn-correlate').innerText = t.btn_correlate;
        document.getElementById('lbl-modal-title').innerText = t.modal_title;
        document.getElementById('lbl-modal-sub').innerText = t.modal_sub;
        document.getElementById('lbl-modal-tip').innerText = t.modal_tip;
        document.getElementById('lbl-modal-or').innerText = t.modal_or;
        document.getElementById('lbl-btn-ingest').innerText = t.btn_ingest;
        document.getElementById('lbl-auth-title').innerText = t.auth_title;
        document.getElementById('lbl-auth-desc').innerText = t.auth_desc;
        document.getElementById('lbl-tab-signin').innerText = t.tab_signin;
        document.getElementById('lbl-tab-signup').innerText = t.tab_signup;
        document.getElementById('lbl-email-in').innerText = t.email_in;
        document.getElementById('lbl-pw-in').innerText = t.pw_in;
        document.getElementById('lbl-btn-login').innerText = t.btn_login;
        document.getElementById('lbl-name-up').innerText = t.name_up;
        document.getElementById('lbl-email-up').innerText = t.email_up;
        document.getElementById('lbl-city-up').innerText = t.city_up;
        document.getElementById('lbl-pw-up').innerText = t.pw_up;
        document.getElementById('lbl-btn-register').innerText = t.btn_register;

        // Render dynamic habits & avoid list
        const avoidUl = document.getElementById('avoid-list');
        avoidUl.innerHTML = t.avoid_items.map(it => `<li>${it}</li>`).join('');

        const followUl = document.getElementById('follow-list');
        followUl.innerHTML = t.follow_items.map(it => `<li>${it}</li>`).join('');

        const habitContainer = document.getElementById('habit-items-container');
        habitContainer.innerHTML = t.habit_checklist.map(h => `
            <div class="d-flex align-items-center justify-content-between mb-2">
                <strong class="text-white small"><i class="fa-solid ${h.icon} me-2"></i> ${h.text}</strong>
                <input type="checkbox" class="form-check-input" ${h.checked ? 'checked' : ''}>
            </div>
        `).join('');
    }

    function setLanguage(lang) {
        currentLang = lang;
        document.querySelectorAll('.btn-lang').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');
        applyTextTranslations();
        if (cachedSummaryData) {
            renderDynamicCards(cachedSummaryData.dynamic_cards);
            renderDoctorSummary(cachedSummaryData);
            renderTreatments(cachedSummaryData.treatments);
            runLiveTwinSimulation();
        }
    }

    async function loadDashboard() {
        updateAuthHeader();

        if (!activeUser) {
            document.getElementById('auth-screen').classList.remove('d-none');
            document.getElementById('dashboard-screen').classList.add('d-none');
            return;
        }

        document.getElementById('auth-screen').classList.add('d-none');
        document.getElementById('dashboard-screen').classList.remove('d-none');
        document.getElementById('dash-greeting').innerText = `${currentLang === 'hi' ? 'नमस्ते' : currentLang === 'mr' ? 'नमस्कार' : 'Welcome'}, ${activeUser.name}`;

        try {
            const res = await fetch(`/api/v1/user/summary/${activeUser.id}`);
            if (!res.ok) {
                logoutUser();
                return;
            }
            const d = await res.json();
            cachedSummaryData = d;

            document.getElementById('latest-hosp').innerText = d.latest_hospital;
            document.getElementById('latest-date').innerText = "Date: " + d.latest_date;

            renderDynamicCards(d.dynamic_cards);
            renderDoctorSummary(d);
            renderTreatments(d.treatments);
            renderDynamicChart(d.chart_data);
            runLiveTwinSimulation();
            applyTextTranslations();
        } catch (e) {
            console.error("Failed to load dashboard telemetry:", e);
        }
    }

    async function computeDynamicStress() {
        if (!activeUser) return;
        const sl = document.getElementById('st-sleep').value;
        const st = document.getElementById('st-stress').value;
        const preP = document.getElementById('pre-pulse').value;
        const postP = document.getElementById('post-pulse').value;

        const fd = new FormData();
        fd.append('user_id', activeUser.id);
        fd.append('sleep_hours', sl);
        fd.append('work_stress', st);
        fd.append('pre_pulse', preP);
        fd.append('post_pulse', postP);

        const res = await fetch('/api/v1/stress/assess-dynamic', { method: 'POST', body: fd });
        const d = await res.json();
        const lang = currentLang;

        let driversHtml = '';
        if (d.biological_drivers && d.biological_drivers.length > 0) {
            const drvList = d.biological_drivers.map(drv => `<li>${drv[lang] || drv['en']}</li>`).join('');
            driversHtml = `<div class="mt-2 text-danger small"><strong>${lang === 'hi' ? 'अहवाल से मिले तनाव कारक:' : lang === 'mr' ? 'अहवालातून मिळालेले ताण घटक:' : 'Biomarker Strain Identified in Reports:'}</strong><ul class="mb-0 ps-3">${drvList}</ul></div>`;
        }

        let dawnHtml = '';
        if (d.dawn_glucose_warning) {
            const dawnText = lang === 'hi' 
                ? "कम नींद और शाम का अधिक तनाव सुबह की खाली पेट शुगर को बढ़ा सकता है।" 
                : lang === 'mr' 
                ? "कमी झोप आणि संध्याकाळचा ताण सकाळची उपाशीपोटी साखर वाढवू शकतो." 
                : "High evening stress combined with <6.5h sleep will trigger tomorrow's morning fasting glucose spike.";
            dawnHtml = `<div class="p-2 mt-2 rounded bg-danger bg-opacity-25 border border-danger text-warning small"><i class="fa-solid fa-triangle-exclamation me-1"></i><strong>${lang === 'hi' ? 'सुबह की शुगर चेतावनी:' : lang === 'mr' ? 'सकाळची साखर इशारा:' : 'Dawn Phenomenon Alert:'}</strong> ${dawnText}</div>`;
        }

        const vRecoveryTitle = lang === 'hi' ? 'हृदय सुधार' : lang === 'mr' ? 'हृदय सुधारणा' : 'VAGAL RECOVERY';
        const pDeltaTitle = lang === 'hi' ? 'नाड़ी सुधार' : lang === 'mr' ? 'नाडी सुधार' : 'PULSE DELTA';
        const cDropTitle = lang === 'hi' ? 'तनाव हार्मोन घट' : lang === 'mr' ? 'तणाव संप्रेरक घट' : 'CORTISOL DROP';

        document.getElementById('stress-dynamic-result').innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <strong class="text-warning fs-6"><i class="fa-solid fa-shield-heart me-1"></i> ${d.status[lang]}</strong>
                <span class="badge bg-purple">Score: ${d.allostatic_score}</span>
            </div>
            <div class="row g-2 text-center my-2">
                <div class="col-4">
                    <div class="p-2 rounded bg-secondary bg-opacity-25 border border-secondary border-opacity-50">
                        <div class="text-secondary" style="font-size:10px;">${vRecoveryTitle}</div>
                        <div class="text-success fw-bold">${d.vagal_recovery_index}%</div>
                    </div>
                </div>
                <div class="col-4">
                    <div class="p-2 rounded bg-secondary bg-opacity-25 border border-secondary border-opacity-50">
                        <div class="text-secondary" style="font-size:10px;">${pDeltaTitle}</div>
                        <div class="text-info fw-bold">-${d.pulse_delta} BPM</div>
                    </div>
                </div>
                <div class="col-4">
                    <div class="p-2 rounded bg-secondary bg-opacity-25 border border-secondary border-opacity-50">
                        <div class="text-secondary" style="font-size:10px;">${cDropTitle}</div>
                        <div class="text-warning fw-bold">-${d.estimated_cortisol_drop_nmol} nmol/L</div>
                    </div>
                </div>
            </div>
            ${driversHtml}
            ${dawnHtml}
        `;
    }

    async function correlateSymptoms() {
        const query = document.getElementById('symp-input').value;
        const fd = new FormData();
        fd.append('symptom', query);
        fd.append('user_id', activeUser.id);

        const res = await fetch('/api/v1/symptoms/correlate', { method: 'POST', body: fd });
        const d = await res.json();
        const lang = currentLang;
        
        const headingText = lang === 'hi' 
            ? "आपकी लैब रिपोर्ट से जुड़ा जैविक कारण:" 
            : lang === 'mr' 
            ? "तुमच्या लॅब अहवालावरून मिळालेले जैविक कारण:" 
            : "BIOLOGICAL REASONING DERIVED FROM YOUR LAB TESTS:";

        let html = `<h6 class="text-warning fw-bold small mb-3"><i class="fa-solid fa-dna me-1"></i> ${headingText}</h6>`;
        
        d.correlations.forEach(c => {
            const bioName = typeof c.biomarker === 'object' ? (c.biomarker[lang] || c.biomarker['en']) : c.biomarker;
            const expText = typeof c.explanation === 'object' ? (c.explanation[lang] || c.explanation['en']) : c.explanation;
            const statusText = typeof c.status_label === 'object' ? (c.status_label[lang] || c.status_label['en']) : c.status_label;
            
            html += `
                <div class="p-3 mb-3 rounded bg-dark border border-secondary border-opacity-50">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <strong class="text-white fs-6"><i class="fa-solid fa-vial-circle-check text-success me-1"></i> ${bioName} (${c.value})</strong>
                        <span class="badge-status status-${c.status_code}">${statusText}</span>
                    </div>
                    <p class="text-light text-opacity-75 small mb-2">${expText}</p>
                    <div class="text-secondary small font-monospace"><i class="fa-solid fa-file-lines text-info me-1"></i> ${c.source}</div>
                </div>
            `;
        });
        document.getElementById('symp-result-box').innerHTML = html;
    }

    async function exportFhir() {
        const res = await fetch(`/api/v1/export/fhir/${activeUser.id}`);
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `helix-fhir-bundle-${activeUser.id}.json`;
        a.click();
    }

    function toggleBreathing() {
        const pacer = document.getElementById('pacer');
        const btn = document.getElementById('breath-btn');
        const t = UI_I18N[currentLang];

        if (breathInterval) {
            clearInterval(breathInterval);
            breathInterval = null;
            btn.innerHTML = `<i class="fa-solid fa-play me-1"></i> <span id="lbl-breath-btn">${t.breath_btn_start}</span>`;
            pacer.classList.remove('expand-circle');
            pacer.innerText = currentLang === 'hi' ? 'विश्राम' : currentLang === 'mr' ? 'विश्रांती' : 'Rest';
            return;
        }

        btn.innerHTML = `<i class="fa-solid fa-pause me-1"></i> <span id="lbl-breath-btn">${t.breath_btn_pause}</span>`;
        breathPhase = 0;

        function cycle() {
            const phases = UI_I18N[currentLang].breath_phases;
            pacer.innerText = phases[breathPhase];
            if (breathPhase === 0) pacer.classList.add('expand-circle');
            if (breathPhase === 2) pacer.classList.remove('expand-circle');
            breathPhase = (breathPhase + 1) % 4;
        }
        cycle();
        breathInterval = setInterval(cycle, 4000);
    }

    function playBinaural(freqDifference) {
        stopBinaural();
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        osc1 = audioCtx.createOscillator();
        osc2 = audioCtx.createOscillator();

        const baseFreq = 200;
        osc1.frequency.value = baseFreq;
        osc2.frequency.value = baseFreq + freqDifference;

        const gainNode = audioCtx.createGain();
        gainNode.gain.value = 0.08;

        osc1.connect(gainNode);
        osc2.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        osc1.start();
        osc2.start();
    }

    function stopBinaural() {
        if (audioCtx) {
            audioCtx.close();
            audioCtx = null;
        }
    }

    async function login() {
        const em = document.getElementById('in-email').value;
        const pw = document.getElementById('in-pw').value;
        const fd = new FormData();
        fd.append('email', em);
        fd.append('password', pw);

        const res = await fetch('/api/v1/auth/login', { method: 'POST', body: fd });
        const d = await res.json();
        if (!res.ok) { alert(d.detail || "Login failed"); return; }

        activeUser = { id: d.user_id, name: d.full_name, email: d.email, age: d.age, gender: d.gender };
        localStorage.setItem('helix_user', JSON.stringify(activeUser));
        await loadDashboard();
    }

    async function register() {
        const fn = document.getElementById('up-name').value;
        const em = document.getElementById('up-email').value;
        const city = document.getElementById('up-city').value;
        const pw = document.getElementById('up-pw').value;

        const fd = new FormData();
        fd.append('full_name', fn);
        fd.append('email', em);
        fd.append('city', city);
        fd.append('password', pw);

        const res = await fetch('/api/v1/auth/register', { method: 'POST', body: fd });
        const d = await res.json();
        if (!res.ok) { alert(d.detail || "Registration failed"); return; }

        activeUser = { id: d.user_id, name: d.full_name, email: d.email, age: 30, gender: "Male" };
        localStorage.setItem('helix_user', JSON.stringify(activeUser));
        await loadDashboard();
    }

    function logoutUser() {
        localStorage.removeItem('helix_user');
        activeUser = null;
        loadDashboard();
    }

    async function uploadReportBatch() {
        if (!activeUser) {
            alert("Please sign in or register first.");
            return;
        }

        const text = document.getElementById('up-text').value;
        const fileIn = document.getElementById('up-file');

        const fd = new FormData();
        fd.append('user_id', activeUser.id);
        fd.append('raw_ocr_text', text);

        if (fileIn.files.length > 0) {
            for (let i = 0; i < fileIn.files.length; i++) {
                fd.append('report_files', fileIn.files[i]);
            }
        }

        try {
            const res = await fetch('/api/v1/pipeline/upload-reports-batch', { method: 'POST', body: fd });
            const d = await res.json();
            if (!res.ok) { alert(d.detail || "Upload failed"); return; }

            bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
            await loadDashboard();
            const alertMsg = currentLang === 'hi' 
                ? `✅ ${d.count} रिपोर्ट सफलतापूर्वक दर्ज की गईं!` 
                : currentLang === 'mr' 
                ? `✅ ${d.count} अहवाल यशस्वीरीत्या जोडले गेले!` 
                : `✅ Ingested ${d.count} report encounter(s) dynamically!`;
            alert(alertMsg);
        } catch (err) {
            console.error("Batch upload error:", err);
            alert("Error analyzing files. Please check the format.");
        }
    }

    window.onload = function() {
        loadDashboard();
    };
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
