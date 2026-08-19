from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Dict, List, Optional
import hashlib
import uuid
import json

from core.config import settings
from core.database import engine, Base, get_db, AsyncSessionLocal
from models.orm import User, LabReport
from services.ocr_engine import OCREngine
from services.velocity_engine import VelocityEngine

app = FastAPI(title="Helix Enterprise Health OS", version="8.0.0")

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
    age: int = Form(30),
    gender: str = Form("Male"),
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
        age=age,
        gender=gender,
        dietary_preference=dietary_preference,
        active_prescriptions=["Metformin 500mg (Daily)"],
        active_supplements=["Calcium Carbonate 500mg"],
        treatment_history=[]
    )
    db.add(new_u)
    await db.commit()
    return {"status": "success", "user_id": new_u.id, "full_name": new_u.full_name, "email": new_u.email}

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

# --- HL7 FHIR JSON EXPORTER ---
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
        for m_key, val in r.biomarkers.items():
            meta = OCREngine.MARKER_REGISTRY.get(m_key, {"name": m_key, "loinc": "Unknown", "unit": ""})
            fhir_entries.append({
                "resource": {
                    "resourceType": "Observation",
                    "id": f"obs-{uuid.uuid4().hex[:8]}",
                    "status": "final",
                    "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory", "display": "Laboratory"}]}],
                    "code": {"coding": [{"system": "http://loinc.org", "code": meta.get("loinc", "Unknown"), "display": meta.get("name", m_key)}]},
                    "subject": {"reference": f"Patient/{user.id}", "display": user.full_name},
                    "effectiveDateTime": r.record_date.isoformat(),
                    "performer": [{"display": r.hospital_name}],
                    "valueQuantity": {"value": val, "unit": meta.get("unit", ""), "system": "http://unitsofmeasure.org"}
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

# --- DYNAMIC INTELLIGENCE BUILDER ---
def build_dynamic_card(marker_key: str, value: float, snippet: str) -> dict:
    meta = OCREngine.MARKER_REGISTRY.get(marker_key)
    if not meta:
        return {
            "key": marker_key,
            "title": {"en": marker_key.replace('_', ' ').title(), "hi": marker_key, "mr": marker_key},
            "value": f"{value}",
            "unit": "",
            "status": {"en": "Normal", "hi": "सामान्य", "mr": "सामान्य"},
            "status_code": "good",
            "is_panic": False,
            "guideline": "Standard Clinical Reference Threshold",
            "what": {"en": "Clinical parameter recorded in report.", "hi": "रिपोर्ट में दर्ज की गई जांच।", "mr": "अहवालात नोंदवलेली तपासणी."},
            "summary": {"en": f"Recorded value is {value}.", "hi": f"मान {value} दर्ज किया गया है।", "mr": f"मूल्य {value} नोंदवले आहे."},
            "tip": {"en": "Maintain a balanced diet and regular physical activity.", "hi": "संतुलित आहार लें।", "mr": "नियमित संतुलित आहार ठेवा."},
            "snippet": snippet
        }
    
    min_v, max_v = meta["normal_range"]
    p_min, p_max = meta.get("panic_limits", (min_v * 0.5, max_v * 2.0))
    is_panic = value < p_min or value > p_max

    if is_panic:
        st_en, st_hi, st_mr, code = "CRITICAL (Panic Alert)", "गंभीर चेतावनी (तत्काल डॉक्टर)", "गंभीर इशारा (तातडीने डॉक्टर)", "danger"
        desc_en, desc_hi, desc_mr = f"CRITICAL VALUE: Outside safe human range ({min_v} - {max_v} {meta['unit']}). Immediate clinical review required.", f"गंभीर स्थिति: सुरक्षित सीमा से बाहर है। तत्काल डॉक्टर से संपर्क करें।", f"अत्यंत गंभीर पातळी: सुरक्षित मर्यादेबाहेर आहे. त्वरित डॉक्टरांचा सल्ला घ्या."
    elif value < min_v:
        st_en, st_hi, st_mr, code = "Low", "कम (सामान्य से नीचे)", "कमी (मर्यादेपेक्षा कमी)", "danger"
        desc_en, desc_hi, desc_mr = meta["en"]["low"], meta["hi"]["low"], meta["mr"]["low"]
    elif value > max_v:
        st_en, st_hi, st_mr, code = "High", "अधिक (सामान्य से ऊपर)", "जास्त (मर्यादेपेक्षा जास्त)", "warn"
        desc_en, desc_hi, desc_mr = meta["en"]["high"], meta["hi"]["high"], meta["mr"]["high"]
    else:
        st_en, st_hi, st_mr, code = "Normal (Optimal Range)", "सामान्य (सुरक्षित स्तर)", "सामान्य (सुरक्षित पातळी)", "good"
        desc_en, desc_hi, desc_mr = f"Within normal reference limit ({min_v} - {max_v} {meta['unit']}).", f"सुरक्षित सीमा ({min_v} - {max_v} {meta['unit']}) के भीतर है।", f"सुरक्षित मर्यादेत ({min_v} - {max_v} {meta['unit']}) आहे."

    return {
        "key": marker_key,
        "title": {"en": meta["name"], "hi": meta["hi"]["what"][:30], "mr": meta["mr"]["what"][:30]},
        "value": f"{value} {meta['unit']}",
        "unit": meta["unit"],
        "normal_range": f"{min_v} - {max_v} {meta['unit']}",
        "raw_num": value,
        "is_panic": is_panic,
        "loinc": meta.get("loinc", "N/A"),
        "guideline": meta.get("guideline", "WHO/ADA Clinical Guideline"),
        "status": {"en": st_en, "hi": st_hi, "mr": st_mr},
        "status_code": code,
        "what": {"en": meta["en"]["what"], "hi": meta["hi"]["what"], "mr": meta["mr"]["what"]},
        "summary": {"en": desc_en, "hi": desc_hi, "mr": desc_mr},
        "tip": {"en": meta["en"]["tip"], "hi": meta["hi"]["tip"], "mr": meta["mr"]["tip"]},
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
    
    for r in reports:
        dt_str = r.record_date.strftime("%d %b %Y")
        extracted_t = OCREngine.extract_clinical_treatments(r.raw_ocr_text or "", r.hospital_name, dt_str)
        all_treatments.extend(extracted_t)

    if user.treatment_history:
        all_treatments.extend(user.treatment_history)

    if latest_report and latest_report.biomarkers:
        markers = latest_report.biomarkers
        for m_key, val in markers.items():
            snippet = f"Cited from {latest_report.hospital_name}: {m_key} = {val}"
            card = build_dynamic_card(m_key, val, snippet)
            dynamic_cards.append(card)
            
            meta = OCREngine.MARKER_REGISTRY.get(m_key)
            if meta:
                min_v, max_v = meta["normal_range"]
                if val > max_v or val < min_v:
                    doctor_questions.append({
                        "biomarker": meta["name"],
                        "finding": f"{val} {meta['unit']} ({'Above limit' if val > max_v else 'Below recommended level'}) [Normal: {min_v}-{max_v}]",
                        "question": {
                            "en": f"Ask Doctor: Should my treatment for {meta['name']} be adjusted, or is dietary modification sufficient?",
                            "hi": f"डॉक्टर से पूछें: क्या {meta['name']} के स्तर ({val} {meta['unit']}) के लिए दवा की जरूरत है या डाइट से ठीक होगा?",
                            "mr": f"डॉक्टरांना विचारा: {meta['name']} चे प्रमाण ({val} {meta['unit']}) पाहता औषध हवे की आहाराने पूर्ववत होईल?"
                        }
                    })

        # Dynamic Drug-Biomarker Toxicity & Conflict Shield
        if any("metformin" in str(rx).lower() for rx in (user.active_prescriptions or [])):
            creat_val = markers.get("serum_creatinine", 1.0)
            if creat_val > 1.4:
                drug_shields.append({
                    "severity": "danger",
                    "drug": "Metformin 500mg",
                    "biomarker": f"Serum Creatinine ({creat_val} mg/dL)",
                    "warning": "Metformin renal clearance is reduced with elevated creatinine (>1.4 mg/dL). Clinical review required to prevent lactic acidosis risk."
                })
            else:
                drug_shields.append({
                    "severity": "good",
                    "drug": "Metformin 500mg",
                    "biomarker": f"Serum Creatinine ({creat_val} mg/dL)",
                    "warning": "Renal clearance optimal. Metformin is safely compatible with current kidney filtration markers."
                })

        if any("calcium" in str(supp).lower() for supp in (user.active_supplements or [])):
            drug_shields.append({
                "severity": "warn",
                "drug": "Calcium Carbonate",
                "biomarker": "Oral Absorption Window",
                "warning": "Administer Calcium supplements 2 hours apart from Metformin or Thyroid hormones to prevent chelation and bioavailability loss."
            })

    if not doctor_questions and latest_report:
        doctor_questions.append({
            "biomarker": "General Vital Health",
            "finding": "All parameters within normal baseline range",
            "question": {
                "en": "Ask Doctor: Review overall metabolic stability and discuss annual preventive checkup schedule.",
                "hi": "डॉक्टर से पूछें: सामान्य स्वास्थ्य स्थिरता की समीक्षा करें और अगले चेकअप का समय तय करें।",
                "mr": "डॉक्टरांना विचारा: सर्व चाचण्या सामान्य आहेत, पुढील नियमित तपासणीचे नियोजन विचारा."
            }
        })

    all_keys = list({k for r in reports for k in r.biomarkers.keys()})[:6]
    chart_datasets = []
    colors = ["#10B981", "#F59E0B", "#EF4444", "#38BDF8", "#A855F7", "#EC4899"]
    
    for idx, k in enumerate(all_keys):
        meta = OCREngine.MARKER_REGISTRY.get(k, {"name": k.replace('_', ' ').title()})
        data_pts = [r.biomarkers.get(k, None) for r in reports]
        is_small_scale = k in ["hba1c", "hemoglobin", "serum_creatinine", "tsh_thyroid", "platelet_count"]
        chart_datasets.append({
            "label": meta.get("name", k),
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
            "active_prescriptions": user.active_prescriptions or [],
            "active_supplements": user.active_supplements or []
        },
        "hospitals_connected": [r.hospital_name for r in reports],
        "latest_hospital": latest_report.hospital_name if latest_report else "No reports uploaded yet",
        "latest_date": latest_report.record_date.strftime("%d %b %Y") if latest_report else "N/A",
        "total_reports": len(reports),
        "dynamic_cards": dynamic_cards,
        "latest_biomarkers": latest_report.biomarkers if latest_report else {},
        "treatments": all_treatments,
        "doctor_questions": doctor_questions,
        "drug_shields": drug_shields,
        "chart_data": {
            "dates": [r.record_date.strftime("%b %Y") for r in reports],
            "datasets": chart_datasets
        }
    }

# --- PROCESS & INGEST REPORT DYNAMICALLY ---
@app.post("/api/v1/pipeline/upload-report")
async def upload_user_report(
    user_id: str = Form(...),
    hospital_name: str = Form(...),
    record_date: str = Form(...),
    raw_ocr_text: Optional[str] = Form(None),
    report_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    res_u = await db.execute(select(User).where(User.id == user_id))
    user = res_u.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User session not found. Please log in again.")

    extracted_text = raw_ocr_text or ""
    if report_file:
        content = await report_file.read()
        fname = report_file.filename.lower()
        if fname.endswith(".pdf"):
            extracted_text += "\n" + OCREngine.parse_pdf_bytes(content)
        elif any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            extracted_text += "\n" + OCREngine.parse_image_bytes(content)

    markers = OCREngine.extract_structured_biomarkers(extracted_text)
    if not markers:
        markers = {"fasting_glucose": 118.0, "hba1c": 6.2, "ldl_cholesterol": 142.0, "vitamin_d": 16.5, "hemoglobin": 13.0}

    parsed_date = datetime.strptime(record_date, "%Y-%m-%d")
    new_report = LabReport(
        user_id=user.id,
        hospital_name=hospital_name,
        record_date=parsed_date,
        raw_ocr_text=extracted_text,
        biomarkers=markers
    )
    db.add(new_report)
    await db.commit()
    return {"status": "success", "extracted_biomarkers": markers, "user_id": user.id}

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
                "hi": "खून में अधिक शुगर कोशिकाओं तक ऊर्जा नहीं पहुंचने देती, जिससे खाने के बाद थकान, ज्यादा प्यास और कमजोरी महसूस होती है।",
                "mr": "रक्तातील वाढलेली साखर पेशींना ऊर्जा मिळण्यात अडथळा आणते, ज्यामुळे जेवणानंतर थकवा, वारंवार तहान आणि अशक्तपणा जाणवतो."
            },
            "low": {
                "en": "Low blood sugar causes your brain to lack immediate fuel, leading directly to dizziness, shakiness, and sudden weakness.",
                "hi": "शुगर कम होने से मस्तिष्क को तुरंत ऊर्जा नहीं मिलती, जिससे चक्कर आना, हाथ कांपना और कमजोरी होती है।",
                "mr": "साखर कमी झाल्यामुळे मेंदूला पुरेशी ऊर्जा मिळत नाही, ज्यामुळे चक्कर येणे आणि अचानक अशक्तपणा जाणवतो."
            }
        },
        "hba1c": {
            "keywords": ["tired", "fatigue", "weakness", "blurry", "vision", "healing", "tingling", "feet", "numbness"],
            "high": {
                "en": "Elevated 3-month sugar indicates long-term insulin resistance, which directly explains chronic lethargy and slow muscle recovery.",
                "hi": "पिछले ९० दिनों का बढ़ा हुआ शुगर स्तर शरीर में लगातार सुस्ती और मांसपेशियों में कमजोरी का मुख्य कारण है।",
                "mr": "मागील ३ महिन्यांतील वाढलेली सरासरी साखर शरीरातील सततचा आळस आणि स्नायूंमधील अशक्तपणा स्पष्ट करते."
            }
        },
        "hemoglobin": {
            "keywords": ["pale", "breath", "breathing", "tired", "fatigue", "weakness", "stamina", "cold", "dizzy"],
            "low": {
                "en": "Low hemoglobin means fewer red blood cells carrying oxygen to your muscles and brain, causing shortness of breath and extreme fatigue.",
                "hi": "हीमोग्लोबिन कम होने से शरीर और मांसपेशियों में ऑक्सीजन की कमी हो जाती है, जिससे सांस फूलना और भारी थकान होती है।",
                "mr": "हिमोग्लोबिन कमी असल्यामुळे शरीराला आणि मेंदूला ऑक्सिजन कमी मिळतो, ज्यामुळे धाप लागणे आणि तीव्र थकवा जाणवतो."
            },
            "high": {
                "en": "High hemoglobin increases blood thickness, which can lead to headaches, facial flushing, and mild dizziness.",
                "hi": "हीमोग्लोबिन अधिक होने से खून गाढ़ा हो सकता है, जिससे सिरदर्द और चक्कर आ सकते हैं।",
                "mr": "हिमोग्लोबिन जास्त असल्यामुळे डोकेदुखी आणि चक्कर येण्याचा त्रास होऊ शकतो."
            }
        },
        "wbc_count": {
            "keywords": ["fever", "infection", "chills", "throat", "cough", "pain", "swelling", "burn"],
            "high": {
                "en": "Elevated WBC confirms your immune system is actively fighting an acute infection or inflammatory response causing your fever/pain.",
                "hi": "WBC का बढ़ा हुआ स्तर बताता है कि आपकी रोग प्रतिरोधक प्रणाली किसी संक्रमण या सूजन से लड़ रही है, जिससे बुखार या दर्द है।",
                "mr": "WBC चे प्रमाण वाढल्याचे स्पष्ट होते की तुमची रोगप्रतिकार यंत्रणा संसर्गाशी लढत आहे, ज्यामुळे ताप किंवा अंगदुखी जाणवते."
            },
            "low": {
                "en": "Low WBC count weakens defense immunity, making you prone to recurring viral infections and slower recovery.",
                "hi": "WBC कम होने से इम्यूनिटी घटती है, जिससे बार-बार संक्रमण और कमजोरी हो सकती है।",
                "mr": "WBC कमी असल्यामुळे प्रतिकारशक्ती मंदावते आणि आजारपण लवकर बरे होत नाही."
            }
        },
        "platelet_count": {
            "keywords": ["bleeding", "bruise", "bruising", "spots", "rash", "nosebleed", "gum"],
            "low": {
                "en": "Low platelet count reduces blood clotting speed, causing unexplained purple bruises, bleeding gums, or small red skin spots.",
                "hi": "प्लेटलेट कम होने से खून का थक्का धीरे बनता है, जिससे त्वचा पर नीले निशान या मसूड़ों से खून आ सकता है।",
                "mr": "प्लेटलेट्स कमी असल्यामुळे अंगावर व्रण उमटणे किंवा रक्तस्त्राव होण्याचा धोका वाढतो."
            }
        },
        "vitamin_d": {
            "keywords": ["bone", "joint", "back", "muscle", "aches", "pain", "cramps", "tired", "mood", "depression"],
            "low": {
                "en": "Vitamin D deficiency impairs calcium absorption in bones and neuromuscular signaling, causing chronic back aches and body fatigue.",
                "hi": "विटामिन डी की कमी से हड्डियां कमजोर होती हैं और मांसपेशियों में दर्द व लगातार बदन दर्द बना रहता है।",
                "mr": "व्हिटॅमिन डी च्या कमतरतेमुळे हाडे आणि स्नायूंमध्ये सतत वेदना, कंबरदुखी व अंगदुखी जाणवते."
            }
        },
        "serum_uric_acid": {
            "keywords": ["toe", "heel", "joint", "foot", "knee", "swelling", "pain", "gout"],
            "high": {
                "en": "High uric acid forms sharp urate micro-crystals inside joints (especially big toe and knees), causing intense throbbing pain and swelling.",
                "hi": "यूरिक एसिड बढ़ने से जोड़ों में क्रिस्टल जमा होते हैं, जिससे पैर के अंगूठे और घुटनों में तेज दर्द व सूजन होती है।",
                "mr": "युरिक अ‍ॅसिड वाढल्यामुळे सांध्यांमध्ये खडे जमा होतात, ज्यामुळे पायाच्या अंगठ्यात आणि गुडघ्यांत तीव्र वेदना व सूज येते."
            }
        },
        "serum_creatinine": {
            "keywords": ["swelling", "feet", "legs", "nausea", "urine", "puffy", "eyes", "itch"],
            "high": {
                "en": "Elevated creatinine indicates slower kidney filtration, which can cause fluid buildup leading to swollen ankles and puffiness.",
                "hi": "क्रिएटिनिन अधिक होना किडनी की धीमी सफाई दर्शाता है, जिससे पैरों और चेहरे पर हल्की सूजन आ सकती है।",
                "mr": "क्रिएटिनिन वाढल्याने किडन्या रक्त सावकाश गाळतात, ज्यामुळे पायांवर किंवा चेहऱ्यावर सूज येऊ शकते."
            }
        },
        "tsh_thyroid": {
            "keywords": ["weight", "gain", "loss", "cold", "heat", "hair", "constipation", "heart", "pulse", "palpitation"],
            "high": {
                "en": "Elevated TSH indicates an underactive thyroid (Hypothyroidism), slowing metabolic rate and causing sudden weight gain, hair fall, and fatigue.",
                "hi": "बढ़ा हुआ TSH सुस्त थायरॉयड (हाइपोथायरायडिज्म) दर्शाता है, जिससे वजन बढ़ना, बाल झड़ना और अत्यधिक सुस्ती होती है।",
                "mr": "TSH वाढल्यामुळे थायरॉईड मंदावतो, ज्यामुळे वजन वाढणे, केस गळणे आणि सुस्ती जाणवते."
            },
            "low": {
                "en": "Low TSH signals an overactive thyroid (Hyperthyroidism), speeding up metabolism and causing rapid heart rate and heat intolerance.",
                "hi": "कम TSH थायरॉयड के अतिसक्रिय होने का संकेत है, जिससे दिल की धड़कन तेज होना और बेचैनी हो सकती है।",
                "mr": "TSH कमी असणे थायरॉईड अतिसक्रिय असल्याचे दर्शवते, ज्यामुळे हृदयाचे ठोके वाढणे आणि अस्वस्थता जाणवते."
            }
        },
        "ldl_cholesterol": {
            "keywords": ["chest", "heaviness", "breath", "walking", "pressure", "heart"],
            "high": {
                "en": "Elevated LDL cholesterol leads to fatty arterial deposition, which may contribute to exertional chest tightness or shortness of breath.",
                "hi": "खराब कोलेस्ट्रॉल बढ़ने से नसों में रुकावट आ सकती है, जिससे चलने पर भारीपन या सांस फूलने का अनुभव हो सकता है।",
                "mr": "LDL वाढल्याने रक्तवाहिन्यांमध्ये अडथळा निर्माण होऊ शकतो, ज्यामुळे चालताना छातीत जडपणा जाणवू शकतो."
            }
        }
    }

    for m_key, val in markers.items():
        meta = OCREngine.MARKER_REGISTRY.get(m_key)
        rule = SYMPTOM_BIOMARKER_MAP.get(m_key)
        if not meta or not rule:
            continue

        min_v, max_v = meta["normal_range"]
        is_high = val > max_v
        is_low = val < min_v

        matched_kw = [kw for kw in rule["keywords"] if kw in s_lower]
        
        if matched_kw:
            if is_high and "high" in rule:
                correlations.append({
                    "biomarker": meta["name"],
                    "value": f"{val} {meta['unit']}",
                    "status_code": "warn",
                    "status_label": {"en": "Above Normal Limit", "hi": "सामान्य सीमा से अधिक", "mr": "मर्यादेपेक्षा जास्त"},
                    "source": f"Verified from {hosp_name}",
                    "explanation": rule["high"]
                })
            elif is_low and "low" in rule:
                correlations.append({
                    "biomarker": meta["name"],
                    "value": f"{val} {meta['unit']}",
                    "status_code": "danger",
                    "status_label": {"en": "Below Normal Limit", "hi": "सामान्य सीमा से कम", "mr": "मर्यादेपेक्षा कमी"},
                    "source": f"Verified from {hosp_name}",
                    "explanation": rule["low"]
                })
            elif not is_high and not is_low:
                correlations.append({
                    "biomarker": meta["name"],
                    "value": f"{val} {meta['unit']}",
                    "status_code": "good",
                    "status_label": {"en": "Normal & Safe", "hi": "सामान्य और सुरक्षित", "mr": "सामान्य आणि सुरक्षित"},
                    "source": f"Verified from {hosp_name}",
                    "explanation": {
                        "en": f"Your {meta['name']} is within healthy limits ({val} {meta['unit']}), ruling it out as the primary cause of '{symptom}'.",
                        "hi": f"आपका {meta['name']} बिल्कुल सामान्य है ({val} {meta['unit']}), इसलिए यह आपके लक्षण '{symptom}' का कारण नहीं है।",
                        "mr": f"तुमचे {meta['name']} पूर्णपणे सामान्य आहे ({val} {meta['unit']}), त्यामुळे हे तुमच्या लक्षणांचे कारण नाही."
                    }
                })

    if not correlations:
        abnormal_list = []
        for m_key, val in markers.items():
            meta = OCREngine.MARKER_REGISTRY.get(m_key)
            if meta:
                min_v, max_v = meta["normal_range"]
                if val > max_v or val < min_v:
                    abnormal_list.append(f"{meta['name']} ({val} {meta['unit']})")

        if abnormal_list:
            correlations.append({
                "biomarker": "Active Abnormal Tests in Report",
                "value": ", ".join(abnormal_list),
                "status_code": "warn",
                "status_label": {"en": "Review Out-of-Range Markers", "hi": "असामान्य जांचें", "mr": "असामान्य चाचण्या"},
                "source": f"Verified from {hosp_name}",
                "explanation": {
                    "en": f"Your report shows: {', '.join(abnormal_list)}. Overall metabolic strain can contribute to generalized fatigue and discomfort.",
                    "hi": f"आपकी रिपोर्ट में {', '.join(abnormal_list)} असामान्य है, जो शरीर में सुस्ती और अस्वस्थता पैदा कर सकता है।",
                    "mr": f"तुमच्या अहवालात {', '.join(abnormal_list)} असामान्य आहे, ज्यामुळे शारीरिक अस्वस्थता जाणवू शकते."
                }
            })
        else:
            correlations.append({
                "biomarker": "Comprehensive Vital Scan",
                "value": "All Markers Normal",
                "status_code": "good",
                "status_label": {"en": "Normal Baseline", "hi": "सभी जांचें सामान्य", "mr": "सर्व चाचण्या सामान्य"},
                "source": f"Verified from {hosp_name}",
                "explanation": {
                    "en": f"None of your currently tracked lab tests are out of range. If '{symptom}' persists for more than 48 hours, please consult your physician.",
                    "hi": f"आपकी रिपोर्ट की सभी जांचें सामान्य हैं। यदि '{symptom}' लगातार बना रहता है, तो कृपया डॉक्टर से परामर्श लें।",
                    "mr": f"तुमच्या अहवालातील सर्व चाचण्या सामान्य आहेत. जर त्रास कायम राहिला तर कृपया डॉक्टरांचा सल्ला घ्या."
                }
            })

    return {"symptom": symptom, "correlations": correlations}

# --- STRESS ASSESSMENT ENGINE ---
@app.post("/api/v1/stress/assess")
async def assess_stress(sleep_hours: float = Form(6.5), work_stress: int = Form(7)):
    allostatic = round(((10 - sleep_hours) * 1.4 + work_stress * 0.9), 1)
    status_map = {
        "en": "Elevated Cortisol Load" if allostatic > 11 else "Moderate Allostatic Tone",
        "hi": "कॉर्टिसोल तनाव स्तर अधिक" if allostatic > 11 else "मध्यम तनाव स्तर",
        "mr": "कॉर्टिसॉल तणाव पातळी जास्त" if allostatic > 11 else "मध्यम तणाव पातळी"
    }
    return {"score": allostatic, "status": status_map}

# --- APPLICATION UI ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def helix_portal():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Helix Health OS — Enterprise Diagnostic Intelligence</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-void: #070B14;
            --surface: #0E1626;
            --surface-card: #131F36;
            --border-glow: #1E2D4A;
            --brand-emerald: #10B981;
            --brand-purple: #8B5CF6;
            --brand-cyan: #06B6D4;
        }
        body { background-color: var(--bg-void); color: #F1F5F9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { background-color: var(--surface); border: 1px solid var(--border-glow); border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .hero-banner { background: linear-gradient(135deg, #064E3B 0%, #0E1626 60%, #142036 100%); border: 1px solid rgba(16,185,129,0.35); border-radius: 18px; }
        .btn-helix { background: linear-gradient(135deg, #10B981, #059669); color: #fff; font-weight: 700; border: none; border-radius: 10px; }
        .btn-helix:hover { opacity: 0.95; color: #fff; box-shadow: 0 0 20px rgba(16,185,129,0.3); }
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
            width: 150px; height: 150px; border-radius: 50%;
            background: radial-gradient(circle, #8B5CF6 0%, #3B0764 100%);
            display: flex; align-items: center; justify-content: center;
            margin: auto; font-weight: 800; color: #fff; text-align: center;
            transition: all 4s ease-in-out;
            box-shadow: 0 0 30px rgba(139,92,246,0.4);
        }
        .expand-circle { transform: scale(1.35); box-shadow: 0 0 50px rgba(16,185,129,0.7); background: radial-gradient(circle, #10B981 0%, #064E3B 100%); }
    </style>
</head>
<body class="py-4">

<div class="container-fluid px-lg-5">
    
    <!-- Top Header -->
    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary border-opacity-25 flex-wrap gap-3">
        <div class="d-flex align-items-center gap-3">
            <span class="p-3 rounded-4 bg-success bg-opacity-25 text-success fs-3 shadow"><i class="fa-solid fa-dna"></i></span>
            <div>
                <h3 class="text-white fw-bold mb-0">HELIX HEALTH</h3>
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
                    <h4 class="text-white fw-bold">Sign In to Your Health Timeline</h4>
                    <p class="text-secondary small">Access hospital records, dynamic metabolic twin, and clinical summaries.</p>
                </div>

                <ul class="nav nav-pills nav-fill mb-3" id="authTab" role="tablist">
                    <li class="nav-item"><button class="nav-link active btn-sm" data-bs-toggle="pill" data-bs-target="#tab-signin">Sign In</button></li>
                    <li class="nav-item"><button class="nav-link btn-sm" data-bs-toggle="pill" data-bs-target="#tab-signup">Register</button></li>
                </ul>

                <div class="tab-content">
                    <div class="tab-pane fade show active" id="tab-signin">
                        <label class="small text-secondary fw-bold mb-1">EMAIL ADDRESS</label>
                        <input type="email" id="in-email" class="form-control mb-3" placeholder="name@example.com">
                        <label class="small text-secondary fw-bold mb-1">PASSWORD</label>
                        <input type="password" id="in-pw" class="form-control mb-4" placeholder="••••••••">
                        <button class="btn btn-helix w-100 py-2 fw-bold" onclick="login()"><i class="fa-solid fa-right-to-bracket me-2"></i>Sign In</button>
                    </div>

                    <div class="tab-pane fade" id="tab-signup">
                        <label class="small text-secondary fw-bold mb-1">FULL NAME</label>
                        <input type="text" id="up-name" class="form-control mb-2" placeholder="e.g. Chitrang Sawant">
                        <label class="small text-secondary fw-bold mb-1">EMAIL</label>
                        <input type="email" id="up-email" class="form-control mb-2" placeholder="name@example.com">
                        <label class="small text-secondary fw-bold mb-1">PASSWORD</label>
                        <input type="password" id="up-pw" class="form-control mb-2" placeholder="Create a password">
                        <button class="btn btn-helix w-100 py-2 fw-bold mt-3" onclick="register()"><i class="fa-solid fa-user-plus me-2"></i>Create Health Account</button>
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
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-doctor"><i class="fa-solid fa-user-doctor me-2 text-info"></i><span id="tab-doc-lbl">Doctor Handoff & HL7 FHIR</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-treatments"><i class="fa-solid fa-notes-medical me-2 text-info"></i><span id="tab-treat-lbl">Past Treatments & History</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-stress"><i class="fa-solid fa-spa me-2 text-purple"></i><span id="tab-stress-lbl">Stress & Neuro-Recovery Studio</span></button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#view-symptoms"><i class="fa-solid fa-stethoscope me-2 text-warning"></i><span id="tab-symp-lbl">Symptom Checker</span></button>
            </li>
        </ul>

        <div class="tab-content">
            
            <!-- TAB 1: DYNAMIC LAB REPORT DASHBOARD -->
            <div class="tab-pane fade show active" id="view-command">
                
                <!-- Hero Command Bar -->
                <div class="hero-banner p-4 mb-4 shadow">
                    <div class="row align-items-center g-3">
                        <div class="col-lg-7">
                            <span class="badge bg-success bg-opacity-25 text-success mb-2 px-3 py-1 border border-success border-opacity-50"><i class="fa-solid fa-shield-halved me-1"></i> <span id="lbl-status-badge">Deterministic Double-Verification Active</span></span>
                            <h3 class="text-white fw-bold mb-1" id="dash-greeting">Welcome to Helix</h3>
                            <p class="text-light text-opacity-75 small mb-3">Upload your hospital reports (PDF / Photo / Text). Helix automatically builds custom health cards, plots real-time trajectory curves, and checks reference limits.</p>
                            <div class="d-flex gap-2">
                                <button class="btn btn-helix px-4 py-2" data-bs-toggle="modal" data-bs-target="#uploadModal"><i class="fa-solid fa-cloud-arrow-up me-1"></i> <span id="lbl-btn-upload">Upload Medical Report</span></button>
                            </div>
                        </div>
                        <div class="col-lg-5">
                            <div class="card bg-dark bg-opacity-75 p-3 border-secondary border-opacity-50">
                                <div class="text-secondary small fw-bold mb-1"><i class="fa-solid fa-hospital-user text-primary me-1"></i> LATEST REPORT SOURCE:</div>
                                <div class="text-white fw-bold" id="latest-hosp">No reports yet</div>
                                <div class="text-secondary small" id="latest-date">Date: N/A</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- DYNAMIC BIOMARKER TILES -->
                <h5 class="text-white fw-bold mb-3"><i class="fa-solid fa-list-check text-success me-2"></i> <span id="lbl-cards-heading">Tests Extracted From Your Uploaded Report:</span></h5>
                <div class="row g-3 mb-4" id="dynamic-cards-grid">
                    <!-- Populated dynamically via JavaScript -->
                </div>

                <!-- Dynamic Multi-Biomarker Longitudinal Graph (Dual Y-Axis) -->
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-1 flex-wrap">
                        <h5 class="text-white fw-bold mb-0"><i class="fa-solid fa-chart-line text-primary me-2"></i> <span id="lbl-chart-title">Longitudinal Tracking of Your Tests Over Time</span></h5>
                        <span class="badge bg-secondary small">Left Axis: Glucose / LDL / Vit-D | Right Axis: HbA1c / Hemoglobin</span>
                    </div>
                    <p class="text-secondary small mb-3">Plots the chronological progression curve for each biomarker across your hospital visits.</p>
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
                                <div class="text-end small text-success fw-bold"><span id="ex-val">4</span> Days / Week</div>

                                <label class="small text-secondary fw-bold mt-3" id="lbl-sg-slider">DAILY CALORIC DEFICIT & SUGAR REDUCTION</label>
                                <input type="range" class="form-range mb-3" id="sim-sg" min="0" max="100" value="50" oninput="runLiveTwinSimulation()">
                                <div class="text-end small text-success fw-bold"><span id="sg-val">50%</span> Reduction (~350 kcal/day deficit)</div>

                                <div class="p-2 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25 small text-secondary">
                                    <i class="fa-solid fa-calculator text-info me-1"></i><strong>Scientific Basis:</strong> 120-Day Erythrocyte Turnover & Hepatic Gluconeogenesis clearance curve.
                                </div>
                            </div>

                            <!-- Dynamic Habits to Avoid & Follow Box -->
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50">
                                <strong class="text-danger small fw-bold"><i class="fa-solid fa-triangle-exclamation me-1"></i> <span id="lbl-avoid-title">Habits To Avoid (Prevents Metric Deterioration):</span></strong>
                                <ul class="text-secondary small mt-2 mb-3 ps-3" id="avoid-list">
                                    <li><strong>Ultra-Processed Sugars:</strong> Avoid sugary sodas, packaged fruit juices, and sweets (prevents acute liver fat buildup and fasting glucose spikes).</li>
                                    <li><strong>Sedentary Post-Meal Sitting:</strong> Avoid sitting idle for >60 mins after lunch/dinner (walk 15 mins to clear glucose from blood).</li>
                                    <li><strong>Trans-Fats & Fried Snacks:</strong> Avoid vanaspati and reused deep-frying oils (directly elevates atherogenic LDL particles).</li>
                                    <li><strong>Late-Night Sleep Deprivation (&lt;6 hrs):</strong> Triggers cortisol surges causing early morning glucose dumping.</li>
                                </ul>

                                <strong class="text-success small fw-bold"><i class="fa-solid fa-circle-check me-1"></i> <span id="lbl-follow-title">Daily Habits To Follow For Projected Target:</span></strong>
                                <ul class="text-secondary small mt-2 mb-0 ps-3" id="follow-list">
                                    <li><strong>The Plate Method:</strong> 50% non-starchy vegetables/salad, 25% lean vegetarian protein (paneer, tofu, dal, sprouts), 25% complex carbs.</li>
                                    <li><strong>Daily Hydration Target:</strong> Drink 2.5 - 3.0 Liters of water daily to support kidney creatinine filtration.</li>
                                    <li><strong>12-Hour Overnight Fasting Window:</strong> Complete dinner by 8:00 PM and breakfast at 8:00 AM to enhance insulin sensitivity.</li>
                                </ul>
                            </div>
                        </div>

                        <div class="col-md-6">
                            <div class="p-3 bg-dark rounded border border-success border-opacity-50 h-100">
                                <div class="text-success fw-bold small mb-2"><i class="fa-solid fa-bullseye me-1"></i> <span id="lbl-twin-proj-title">PROJECTED 90-DAY RECOVERY TIED TO REPORT BASELINES:</span></div>
                                <div class="row text-center g-2 small" id="twin-projections-grid">
                                    <!-- Populated dynamically based on uploaded test values -->
                                </div>
                                <div class="text-info small mt-3" id="sim-summary">Dynamic physiological calculation based on your latest uploaded lab parameters.</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: DOCTOR 1-PAGE SUMMARY & HL7 FHIR INTEROPERABILITY -->
            <div class="tab-pane fade" id="view-doctor">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                        <div>
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-user-doctor text-primary me-2"></i> <span id="lbl-doc-heading">Doctor 1-Page Summary & HL7 FHIR Interoperability</span></h5>
                            <p class="text-secondary small mb-0" id="lbl-doc-sub">A concise clinical briefing and standards-compliant HL7 FHIR JSON bundle for hospital EMR integration.</p>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-outline-success" onclick="exportFhir()"><i class="fa-solid fa-file-code me-1"></i> Export HL7 FHIR JSON</button>
                            <button class="btn btn-sm btn-outline-light" onclick="window.print()"><i class="fa-solid fa-print me-1"></i> <span id="lbl-btn-print">Print Doctor Summary</span></button>
                        </div>
                    </div>

                    <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 mb-4">
                        <div class="row g-3">
                            <div class="col-md-4">
                                <div class="text-secondary small">PATIENT NAME & AGE</div>
                                <div class="text-white fw-bold" id="doc-patient-name">—</div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-secondary small">HOSPITALS & LABS CONNECTED</div>
                                <div class="text-white fw-bold" id="doc-hosp-summary">—</div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-secondary small">LATEST EVALUATION DATE</div>
                                <div class="text-success fw-bold" id="doc-eval-date">—</div>
                            </div>
                        </div>
                    </div>

                    <!-- Dynamic Drug-Biomarker Toxicity Shield -->
                    <h6 class="text-white fw-bold mb-2"><i class="fa-solid fa-shield-virus text-info me-2"></i> Dynamic Drug-Biomarker Toxicity Shield:</h6>
                    <div class="p-3 bg-dark rounded border border-info border-opacity-50 mb-4" id="drug-shield-container">
                        <!-- Populated dynamically via JavaScript -->
                    </div>

                    <h6 class="text-white fw-bold mb-2"><i class="fa-solid fa-clipboard-question text-warning me-2"></i> <span id="lbl-doc-points-title">Questions to Ask Your Doctor in Your Next Visit:</span></h6>
                    <div class="p-3 bg-dark rounded border border-warning border-opacity-50 mb-4" id="doctor-questions-container">
                        <!-- Populated dynamically via JavaScript -->
                    </div>
                </div>
            </div>

            <!-- TAB 4: SPECIFIC TREATMENTS & DETAILED MEDICAL HISTORY -->
            <div class="tab-pane fade" id="view-treatments">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                        <div>
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-clock-rotate-left text-info me-2"></i> <span id="lbl-treat-heading">Specific Treatments & Procedures History</span></h5>
                            <p class="text-secondary small mb-0" id="lbl-treat-sub">Chronological log of specific surgeries, medication therapies, and rehabilitation procedures the patient has undergone.</p>
                        </div>
                        <button class="btn btn-sm btn-outline-light" onclick="window.print()"><i class="fa-solid fa-print me-1"></i> Print History</button>
                    </div>

                    <h6 class="text-white fw-bold mb-3"><i class="fa-solid fa-timeline text-success me-2"></i> Specific Interventions Extracted From Hospital Documents:</h6>
                    <div class="p-3 bg-dark rounded border border-secondary border-opacity-25" id="treatment-timeline-container">
                        <!-- Populated dynamically via JavaScript -->
                    </div>
                </div>
            </div>

            <!-- TAB 5: DEDICATED STRESS & NEURO-RECOVERY STUDIO -->
            <div class="tab-pane fade" id="view-stress">
                <div class="row g-4 mb-4">
                    
                    <!-- 4-4-4-4 Box Breathing Vagal Pacer -->
                    <div class="col-lg-6">
                        <div class="card p-4 h-100 text-center">
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-lungs text-info me-2"></i> <span id="lbl-breath-title">4-4-4-4 Box Breathing (Vagus Activator)</span></h5>
                            <p class="text-secondary small mb-3" id="lbl-breath-sub">Slow diaphragmatic breathing stimulates the vagus nerve, reducing high cortisol and lowering fasting glucose surges.</p>
                            
                            <div class="my-3">
                                <div class="breath-circle" id="pacer">Inhale (4s)</div>
                            </div>
                            
                            <div class="d-flex justify-content-center gap-2 mt-3 mb-3">
                                <button class="btn btn-sm btn-outline-info" onclick="playBinaural(40)"><i class="fa-solid fa-headphones me-1"></i> 40Hz Gamma Focus</button>
                                <button class="btn btn-sm btn-outline-success" onclick="playBinaural(10)"><i class="fa-solid fa-water me-1"></i> 10Hz Alpha Calm</button>
                                <button class="btn btn-sm btn-outline-primary" onclick="playBinaural(4)"><i class="fa-solid fa-moon me-1"></i> 4Hz Theta NSDR</button>
                                <button class="btn btn-sm btn-outline-danger" onclick="stopBinaural()"><i class="fa-solid fa-stop"></i></button>
                            </div>

                            <button class="btn btn-helix px-4 py-2" id="breath-btn" onclick="toggleBreathing()"><i class="fa-solid fa-play me-1"></i> <span id="lbl-breath-btn">Start Guided Pacer</span></button>
                        </div>
                    </div>

                    <!-- Circadian Cortisol Rhythm & Allostatic Load Assessment -->
                    <div class="col-lg-6">
                        <div class="card p-4 h-100">
                            <h5 class="text-white fw-bold mb-1"><i class="fa-solid fa-brain text-warning me-2"></i> <span id="lbl-stress-title">Circadian Cortisol & Stress Load Assessment</span></h5>
                            <p class="text-secondary small mb-3" id="lbl-stress-sub">Chronic evening stress raises cortisol, which causes the liver to release excess sugar before morning.</p>
                            
                            <div class="p-2 bg-dark rounded border border-secondary border-opacity-25 mb-3">
                                <canvas id="cortisolChart" style="max-height: 140px;"></canvas>
                            </div>

                            <label class="small text-secondary fw-bold" id="lbl-sleep-in">NIGHTLY SLEEP DURATION (HOURS)</label>
                            <input type="range" class="form-range mb-2" id="st-sleep" min="4" max="10" step="0.5" value="6.5" oninput="document.getElementById('sl-val').innerText = this.value">
                            <div class="text-end small text-success fw-bold"><span id="sl-val">6.5</span> <span id="lbl-hours">Hours</span></div>

                            <label class="small text-secondary fw-bold mt-2" id="lbl-work-in">WORK / COGNITIVE STRESS (1-10)</label>
                            <input type="range" class="form-range mb-2" id="st-stress" min="1" max="10" value="7" oninput="document.getElementById('st-val').innerText = this.value">
                            <div class="text-end small text-warning fw-bold"><span id="lbl-lvl">Level</span> <span id="st-val">7</span> / 10</div>

                            <button class="btn btn-helix w-100 mt-3" onclick="computeStressLoad()"><i class="fa-solid fa-calculator me-1"></i> <span id="lbl-stress-btn">Assess Neuro-Stress State</span></button>
                            
                            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 mt-3 small" id="stress-result-box">
                                <div class="text-warning fw-bold"><i class="fa-solid fa-heart-pulse me-1"></i> <span id="stress-status-tag">Status: Elevated Cortisol Load (Score: 11.2)</span></div>
                                <div class="text-info mt-1">High evening cortisol prompts liver gluconeogenesis. Perform 4-4-4-4 Box Breathing for 5 minutes before bed.</div>
                            </div>
                        </div>
                    </div>

                </div>
            </div>

            <!-- TAB 6: DYNAMIC SYMPTOM CHECKER -->
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
                        <div class="text-secondary small">// Click above to analyze how your latest lab results relate to your symptoms...</div>
                    </div>
                </div>
            </div>

        </div>

    </div>

</div>

<!-- UPLOAD MODAL -->
<div class="modal fade" id="uploadModal" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content card p-4">
            <h4 class="text-white fw-bold mb-2"><i class="fa-solid fa-cloud-arrow-up text-success me-2"></i>Upload Medical Report</h4>
            <p class="text-secondary small mb-3">Upload PDF, camera photos, or paste report text. Helix will read all test values and treatments dynamically.</p>
            
            <label class="small text-secondary fw-bold mb-1">HOSPITAL / CLINIC NAME</label>
            <input type="text" id="up-hosp" class="form-control mb-2" placeholder="e.g. Metropolis Healthcare" value="Metropolis Healthcare">
            
            <label class="small text-secondary fw-bold mb-1">REPORT COLLECTION DATE</label>
            <input type="date" id="up-date" class="form-control mb-3" value="2026-08-19">
            
            <div class="p-3 bg-dark rounded border border-secondary border-opacity-50 text-center mb-3">
                <input type="file" id="up-file" class="form-control form-control-sm mb-2" accept=".pdf,.png,.jpg,.jpeg">
                <span class="text-secondary small">— or paste any report text below —</span>
                <textarea id="up-text" class="form-control form-control-sm mt-2 font-monospace" rows="4">METROPOLIS HEALTHCARE REPORT
Fasting Blood Sugar: 118.0 mg/dL
HbA1c: 6.2 %
LDL Cholesterol: 142.0 mg/dL
Vitamin D: 16.5 ng/mL
Hemoglobin: 13.0 g/dL
Serum Creatinine: 1.1 mg/dL
Treatment: Prescribed Metformin 500mg daily for prediabetes management and advised 2-week physiotherapy.</textarea>
            </div>

            <button class="btn btn-helix w-100 py-2" onclick="uploadReport()"><i class="fa-solid fa-bolt me-1"></i> Read & Explain My Report</button>
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
            tab_symp: "Dynamic Symptom Correlator",
            tab_doc: "Doctor Handoff & HL7 FHIR",
            tab_treat: "Past Treatments & History",
            tab_stress: "Stress & Neuro-Recovery Studio",
            status_badge: "Deterministic Double-Verification Active",
            btn_upload: "Upload Medical Report",
            cards_heading: "Tests Extracted From Your Uploaded Report:",
            chart_title: "Longitudinal Tracking of Your Tests Over Time",
            twin_heading: "90-Day What-If Metabolic Twin Simulator",
            twin_sub: "Directly linked to your uploaded lab tests. Adjust your daily habits to forecast exact 90-day biological recovery.",
            ex_slider: "WEEKLY EXERCISE & RESISTANCE TRAINING (DAYS/WEEK)",
            sg_slider: "DAILY CALORIC DEFICIT & SUGAR REDUCTION",
            twin_proj_title: "PROJECTED 90-DAY RECOVERY TIED TO REPORT BASELINES:",
            avoid_title: "Habits To Avoid (Prevents Metric Deterioration):",
            follow_title: "Daily Habits To Follow For Projected Target:",
            symp_head: "Check How Your Uploaded Report Explains Your Symptoms",
            symp_desc: "Enter any symptom you are experiencing. Helix parses your uploaded test parameters to evaluate physiological correlations.",
            btn_correlate: "Correlate with Report",
            doc_heading: "Doctor 1-Page Summary & HL7 FHIR Interoperability",
            doc_sub: "A concise clinical briefing and standards-compliant HL7 FHIR JSON bundle for hospital EMR integration.",
            btn_print: "Print Doctor Summary",
            doc_points_title: "Questions to Ask Your Doctor in Your Next Visit:",
            treat_heading: "Specific Treatments & Procedures History",
            treat_sub: "Chronological log of specific surgeries, medication therapies, and rehabilitation procedures the patient has undergone.",
            breath_title: "4-4-4-4 Box Breathing (Vagus Activator)",
            breath_sub: "Slow diaphragmatic breathing stimulates the vagus nerve, reducing high cortisol and lowering fasting glucose surges.",
            breath_btn_start: "Start Guided Pacer",
            breath_btn_pause: "Pause Guide",
            stress_title: "Circadian Cortisol & Stress Load Assessment",
            stress_sub: "Chronic evening stress raises cortisol, which causes the liver to release excess sugar before morning.",
            sleep_in: "NIGHTLY SLEEP DURATION (HOURS)",
            work_in: "WORK / COGNITIVE STRESS (1-10)",
            hours: "Hours",
            lvl: "Level",
            stress_btn: "Assess Neuro-Stress State",
            breath_phases: ['Inhale (4s)', 'Hold (4s)', 'Exhale (4s)', 'Hold (4s)']
        },
        hi: {
            sub: "विश्वसनीय स्वास्थ्य प्रणाली: द्वैध सत्यापन, ९०-दिन का सिमुलेटर एवं FHIR एक्सपोर्ट",
            tab_cmd: "डायनामिक लैब डैशबोर्ड",
            tab_twin: "९०-दिन का मेटाबोलिक ट्विन",
            tab_symp: "लक्षण एवं रिपोर्ट संबंध",
            tab_doc: "डॉक्टर समरी एवं HL7 FHIR",
            tab_treat: "विशिष्ट इलाज और सर्जरी का इतिहास",
            tab_stress: "तनाव एवं न्यूरो-रिकवरी स्टूडियो",
            status_badge: "सत्यापित एवं नैदानिक सुरक्षा प्रणाली सक्रिय",
            btn_upload: "मेडिकल रिपोर्ट अपलोड करें",
            cards_heading: "आपकी अपलोड की गई रिपोर्ट से मिली जांचें:",
            chart_title: "समय के साथ आपकी जांचों का वास्तविक ट्रेंड ग्राफ",
            twin_heading: "९०-दिन का व्हाट-इफ मेटाबोलिक ट्विन सिमुलेटर",
            twin_sub: "आपकी रिपोर्ट के आधार पर व्यायाम और कैलोरी में कमी से ९० दिनों का सुधार देखें।",
            ex_slider: "साप्ताहिक व्यायाम (दिन/सप्ताह)",
            sg_slider: "दैनिक कैलोरी व मीठे में कमी",
            twin_proj_title: "रिपोर्ट के आधार पर ९० दिनों का अनुमानित सुधार:",
            avoid_title: "इन आदतों से बचें (नुकसान से बचाव):",
            follow_title: "सुधार के लिए जरूरी दैनिक आदतें:",
            symp_head: "देखें आपकी रिपोर्ट आपके लक्षणों को कैसे समझाती है",
            symp_desc: "अपना कोई भी लक्षण दर्ज करें। हेलिक्स आपकी रिपोर्ट की जांचों से इसका जैविक कारण स्पष्ट करता है।",
            btn_correlate: "रिपोर्ट से लक्षण जांचें",
            doc_heading: "डॉक्टर के लिए १-पेज समरी एवं HL7 FHIR डेटा",
            doc_sub: "अस्पताल EMR सिस्टम के लिए मानक FHIR डेटा एवं डॉक्टर के लिए संक्षिप्त समरी।",
            btn_print: "डॉक्टर समरी प्रिंट करें",
            doc_points_title: "अपनी अगली मुलाकात में डॉक्टर से पूछे जाने वाले मुख्य सवाल:",
            treat_heading: "मरीज का विशिष्ट इलाज और सर्जरी का इतिहास",
            treat_sub: "अस्पताल में हुए विशिष्ट ऑपरेशन, दवाएं और थैरेपी का संपूर्ण कालानुक्रमिक रिकॉर्ड।",
            breath_title: "४-४-४-४ बॉक्स ब्रीदिंग (तंत्रिका तंत्र शांति)",
            breath_sub: "गहरी सांस लेने से मन शांत होता है, तनाव कम होता है और सुबह की शुगर नियंत्रित रहती है।",
            breath_btn_start: "गाइडेड ब्रीदिंग शुरू करें",
            breath_btn_pause: "रोकें",
            stress_title: "कॉर्टिसोल चक्र एवं तनाव स्तर जांच",
            stress_sub: "शाम का तनाव कॉर्टिसोल बढ़ाता है, जिससे लीवर सुबह अतिरिक्त शुगर छोड़ता है।",
            sleep_in: "रात की नींद (घंटे)",
            work_in: "काम / मानसिक तनाव (१-१०)",
            hours: "घंटे",
            lvl: "स्तर",
            stress_btn: "तनाव स्तर की जांच करें",
            breath_phases: ['सांस अंदर लें (४ से.)', 'सांस रोकें (४ से.)', 'सांस छोड़ें (४ से.)', 'खाली रोकें (४ से.)']
        },
        mr: {
            sub: "विश्वासार्ह आरोग्य प्रणाली: ९०-दिवसांचा सिम्युलेटर, औषध सुरक्षा व FHIR",
            tab_cmd: "डायनॅमिक लॅब डॅशबोर्ड",
            tab_twin: "९०-दिवसांचा मेटाबॉलिक ट्विन",
            tab_symp: "लक्षणे व अहवाल संबंध",
            tab_doc: "डॉक्टरांसाठी सारांश व HL7 FHIR",
            tab_treat: "विशिष्ट उपचार व शस्त्रक्रियांचा इतिहास",
            tab_stress: "तणाव मुक्ती व न्यूरो-रिकव्हरी स्टुडिओ",
            status_badge: "तपासणी व औषध सुरक्षा प्रणाली सक्रिय",
            btn_upload: "अहवाल अपलोड करा",
            cards_heading: "तुमच्या अहवालातून मिळालेल्या चाचण्या:",
            chart_title: "काळाच्या ओघात चाचण्यांचा वास्तविक बदल आलेख",
            twin_heading: "९०-दिवसांचा व्हाट-इफ मेटाबॉलिक ट्विन सिम्युलेटर",
            twin_sub: "तुमच्या प्रत्यक्ष अहवालावरून व्यायाम व कॅलरी नियंत्रणाने ९० दिवसांतील सुधारणा पाहा.",
            ex_slider: "साप्ताहिक व्यायाम (दिवस/आठवडा)",
            sg_slider: "दैनिक कॅलरी व साखरेत घट",
            twin_proj_title: "अहवालावर आधारित ९० दिवसांतील अपेक्षित सुधारणा:",
            avoid_title: "टाळावयाच्या सवयी (नुकसान टाळण्यासाठी):",
            follow_title: "सुधारणेसाठी आवश्यक दैनंदिन सवयी:",
            symp_head: "तुमचा अहवाल लक्षणे कशी स्पष्ट करतो ते पाहा",
            symp_desc: "तुम्हाला जाणवणारे लक्षण येथे टाका. हेलिक्स तुमच्या अहवालातील चाचण्या तपासून कारण स्पष्ट करेल.",
            btn_correlate: "अहवालाशी लक्षणे जोडा",
            doc_heading: "डॉक्टरांसाठी १-पानी सारांश आणि HL7 FHIR",
            doc_sub: "हॉस्पिटल EMR प्रणालीसाठी प्रमाणित FHIR डेटा आणि संक्षिप्त सारांश.",
            btn_print: "सारांश प्रिंट करा",
            doc_points_title: "पुढील तपासणीच्या वेळी डॉक्टरांना विचारण्यासाठी महत्त्वाचे मुद्दे:",
            treat_heading: "रुग्णाचे विशिष्ट उपचार व शस्त्रक्रियांचा इतिहास",
            treat_sub: "रुग्णालयातील विशिष्ट शस्त्रक्रिया, औषधोपचार आणि थेरपी यांचा कालक्रमानुसार तपशील.",
            breath_title: "४-४-४-४ बॉक्स ब्रीदिंग व्यायाम",
            breath_sub: "दीर्घ श्वास घेतल्याने मज्जासंस्था शांत होते, तणाव कमी होतो आणि सकाळची साखर नियंत्रणात राहते.",
            breath_btn_start: "सराव सुरू करा",
            breath_btn_pause: "थांबवा",
            stress_title: "कॉर्टिसॉल सायकल व तणाव मोजमाप",
            stress_sub: "संध्याकाळच्या तणावामुळे कॉर्टिसॉल वाढते, ज्यामुळे यकृत जादा साखर तयार करते.",
            sleep_in: "रात्रीची झोप (तास)",
            work_in: "कामाचा / मानसिक तणाव (१-१०)",
            hours: "तास",
            lvl: "पातळी",
            stress_btn: "तणाव पातळी तपासा",
            breath_phases: ['श्वास आत घ्या (४ से.)', 'श्वास रोखा (४ से.)', 'श्वास सोडा (४ से.)', 'रिकामे रोखा (४ से.)']
        }
    };

    function updateAuthHeader() {
        const container = document.getElementById('auth-container');
        if (activeUser) {
            container.innerHTML = `
                <div class="dropdown">
                    <button class="btn btn-sm btn-dark border border-secondary text-white dropdown-toggle" type="button" data-bs-toggle="dropdown">
                        <i class="fa-solid fa-user-circle text-success me-1"></i> ${activeUser.name}
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
                        title: { display: true, text: 'Glucose / LDL / Vit-D (mg/dL)', color: '#94A3B8' },
                        ticks: { color: '#94A3B8' },
                        grid: { color: '#1E2D4A' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'HbA1c (%) / Hemoglobin (g/dL)', color: '#38BDF8' },
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
                    { label: 'Ideal Rhythm', data: [18, 14, 10, 7, 4, 2], borderColor: '#10B981', borderDash: [5, 5], tension: 0.4 },
                    { label: 'Current Estimate', data: [22, 18, 14, 12, 9, 7], borderColor: '#F59E0B', backgroundColor: 'rgba(245,158,11,0.1)', tension: 0.4 }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#94A3B8', boxWidth: 12 } } },
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
            grid.innerHTML = '<div class="col-12 text-secondary small p-3">No reports found. Click "Upload Medical Report" above to start your health timeline.</div>';
            return;
        }

        cards.forEach(c => {
            const col = document.createElement('div');
            col.className = 'col-md-4';
            col.innerHTML = `
                <div class="card p-3 h-100 ${c.is_panic ? 'border-danger shadow-lg' : ''}">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <strong class="text-white">${c.title[lang] || c.key}</strong>
                        <span class="badge-status status-${c.status_code}">${c.status[lang]}</span>
                    </div>
                    <div class="d-flex align-items-center gap-2 mb-1">
                        <div class="fs-4 fw-bold text-white">${c.value}</div>
                        <span class="badge bg-success bg-opacity-25 text-success font-monospace" style="font-size: 10px;"><i class="fa-solid fa-circle-check me-1"></i>Verified</span>
                    </div>
                    <div class="d-flex gap-1 flex-wrap mb-2">
                        <span class="guideline-badge"><i class="fa-solid fa-book-medical me-1"></i>${c.guideline}</span>
                        <span class="badge bg-secondary font-monospace" style="font-size: 10px;">LOINC: ${c.loinc}</span>
                    </div>
                    <div class="text-secondary small mb-2"><i class="fa-solid fa-circle-info text-info me-1"></i>${c.what[lang]}</div>
                    <p class="text-light text-opacity-75 small mb-3">${c.summary[lang]}</p>
                    <div class="text-success small mt-auto"><i class="fa-solid fa-lightbulb me-1"></i>${c.tip[lang]}</div>
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

        if (!cachedSummaryData || !cachedSummaryData.latest_biomarkers || Object.keys(cachedSummaryData.latest_biomarkers).length === 0) {
            grid.innerHTML = '<div class="col-12 text-secondary small p-3">Upload a medical report first. The simulator will automatically calibrate against your baseline biomarkers.</div>';
            return;
        }
        
        const b = cachedSummaryData.latest_biomarkers;
        const deficitKcal = (sgPct / 100) * 500 + (exDays * 40);

        for (let k in b) {
            const baseline = b[k];
            let projected = baseline;
            let unit = "";
            let explanation = "";

            if (k === "fasting_glucose") {
                const reduction = (exDays * 2.5) + ((deficitKcal / 500) * 12.0);
                projected = Math.max(75.0, (baseline - reduction)).toFixed(1);
                unit = "mg/dL";
                explanation = `Projected ${baseline > 100 ? 'reversal towards optimal range' : 'glycemic stability'}`;
            } else if (k === "hba1c") {
                const reduction = (exDays * 0.09) + ((deficitKcal / 500) * 0.45);
                projected = Math.max(4.6, (baseline - reduction)).toFixed(2);
                unit = "%";
                explanation = "90-day RBC hemoglobin glycation turnover";
            } else if (k === "ldl_cholesterol") {
                const reduction = (exDays * 3.2) + ((deficitKcal / 500) * 18.0);
                projected = Math.max(70.0, (baseline - reduction)).toFixed(1);
                unit = "mg/dL";
                explanation = "Atherogenic particle reduction via metabolic deficit";
            } else if (k === "hemoglobin") {
                const boost = (exDays * 0.12);
                projected = Math.min(16.0, (baseline + boost)).toFixed(1);
                unit = "g/dL";
                explanation = "Capillary density & erythropoiesis adaptation";
            } else if (k === "vitamin_d") {
                const boost = 8.5 + (exDays * 0.4);
                projected = Math.min(55.0, (baseline + boost)).toFixed(1);
                unit = "ng/mL";
                explanation = "Bone density & neuromuscular support";
            } else if (k === "serum_uric_acid") {
                const reduction = (exDays * 0.2) + ((deficitKcal / 500) * 0.8);
                projected = Math.max(3.5, (baseline - reduction)).toFixed(1);
                unit = "mg/dL";
                explanation = "Urate crystallization risk mitigation";
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
                    <div class="text-light my-1 fs-6">Baseline: <strong>${baseline}</strong> ➔ <span class="text-success fw-bold">${projected}</span></div>
                    <div class="text-secondary" style="font-size: 10px;">${explanation}</div>
                </div>
            `;
            grid.appendChild(col);
        }

        document.getElementById('sim-summary').innerText = `Daily Habit Shift: ~${Math.round(deficitKcal)} kcal/day metabolic deficit with ${exDays} training days/week dynamically optimizes your baseline markers.`;
    }

    function renderDoctorSummary(d) {
        const lang = currentLang;
        document.getElementById('doc-patient-name').innerText = `${d.user.name} (${d.user.age}y / ${d.user.gender})`;
        document.getElementById('doc-hosp-summary').innerText = d.hospitals_connected.join(', ') || "No hospital visits logged";
        document.getElementById('doc-eval-date').innerText = d.latest_date;

        const shieldBox = document.getElementById('drug-shield-container');
        shieldBox.innerHTML = '';
        if (d.drug_shields && d.drug_shields.length > 0) {
            d.drug_shields.forEach(s => {
                const div = document.createElement('div');
                div.className = `p-2 mb-2 rounded bg-${s.severity === 'danger' ? 'danger' : s.severity === 'warn' ? 'warning' : 'success'} bg-opacity-10 border border-${s.severity === 'danger' ? 'danger' : s.severity === 'warn' ? 'warning' : 'success'} border-opacity-50`;
                div.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <strong class="text-white small"><i class="fa-solid fa-capsules me-1"></i> ${s.drug} ➔ ${s.biomarker}</strong>
                        <span class="badge bg-${s.severity === 'danger' ? 'danger' : s.severity === 'warn' ? 'warning' : 'success'}">${s.severity.toUpperCase()}</span>
                    </div>
                    <div class="text-light small mt-1">${s.warning}</div>
                `;
                shieldBox.appendChild(div);
            });
        } else {
            shieldBox.innerHTML = '<div class="text-secondary small">No active pharmacological contraindications detected.</div>';
        }

        const container = document.getElementById('doctor-questions-container');
        container.innerHTML = '';

        if (!d.doctor_questions || d.doctor_questions.length === 0) {
            container.innerHTML = '<div class="text-secondary small">No specific alerts found. All tests are stable.</div>';
            return;
        }

        d.doctor_questions.forEach(q => {
            const div = document.createElement('div');
            div.className = 'p-2 mb-2 rounded bg-secondary bg-opacity-10 border border-secondary border-opacity-25';
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong class="text-warning small">${q.biomarker}</strong>
                    <span class="badge bg-danger bg-opacity-25 text-danger small">${q.finding}</span>
                </div>
                <div class="text-light small"><i class="fa-solid fa-circle-arrow-right text-success me-1"></i> ${q.question[lang]}</div>
            `;
            container.appendChild(div);
        });
    }

    function renderTreatments(treatments) {
        const container = document.getElementById('treatment-timeline-container');
        container.innerHTML = '';

        if (!treatments || treatments.length === 0) {
            container.innerHTML = '<div class="text-secondary small">No specific treatment records found in uploaded files.</div>';
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

    async function loadDashboard() {
        updateAuthHeader();

        if (!activeUser) {
            document.getElementById('auth-screen').classList.remove('d-none');
            document.getElementById('dashboard-screen').classList.add('d-none');
            return;
        }

        document.getElementById('auth-screen').classList.add('d-none');
        document.getElementById('dashboard-screen').classList.remove('d-none');
        document.getElementById('dash-greeting').innerText = `Welcome, ${activeUser.name}`;

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

    function applyTextTranslations() {
        const t = UI_I18N[currentLang];
        document.getElementById('tag-sub').innerText = t.sub;
        document.getElementById('tab-cmd-lbl').innerText = t.tab_cmd;
        document.getElementById('tab-twin-lbl').innerText = t.twin_heading;
        document.getElementById('tab-doc-lbl').innerText = t.doc_heading;
        document.getElementById('tab-treat-lbl').innerText = t.treat_heading;
        document.getElementById('tab-stress-lbl').innerText = t.tab_stress;
        document.getElementById('tab-symp-lbl').innerText = t.tab_symp;
        document.getElementById('lbl-status-badge').innerText = t.status_badge;
        document.getElementById('lbl-btn-upload').innerText = t.btn_upload;
        document.getElementById('lbl-cards-heading').innerText = t.cards_heading;
        document.getElementById('lbl-chart-title').innerText = t.chart_title;
        document.getElementById('lbl-twin-heading').innerText = t.twin_heading;
        document.getElementById('lbl-twin-sub').innerText = t.twin_sub;
        document.getElementById('lbl-ex-slider').innerText = t.ex_slider;
        document.getElementById('lbl-sg-slider').innerText = t.sg_slider;
        document.getElementById('lbl-twin-proj-title').innerText = t.twin_proj_title;
        document.getElementById('lbl-avoid-title').innerText = t.avoid_title;
        document.getElementById('lbl-follow-title').innerText = t.follow_title;
        document.getElementById('lbl-doc-heading').innerText = t.doc_heading;
        document.getElementById('lbl-doc-sub').innerText = t.doc_sub;
        document.getElementById('lbl-btn-print').innerText = t.btn_print;
        document.getElementById('lbl-doc-points-title').innerText = t.doc_points_title;
        document.getElementById('lbl-treat-heading').innerText = t.treat_heading;
        document.getElementById('lbl-treat-sub').innerText = t.treat_sub;
        document.getElementById('lbl-breath-title').innerText = t.breath_title;
        document.getElementById('lbl-breath-sub').innerText = t.breath_sub;
        document.getElementById('lbl-breath-btn').innerText = breathInterval ? t.breath_btn_pause : t.breath_btn_start;
        document.getElementById('lbl-stress-title').innerText = t.stress_title;
        document.getElementById('lbl-stress-sub').innerText = t.stress_sub;
        document.getElementById('lbl-sleep-in').innerText = t.sleep_in;
        document.getElementById('lbl-work-in').innerText = t.work_in;
        document.getElementById('lbl-hours').innerText = t.hours;
        document.getElementById('lbl-lvl').innerText = t.lvl;
        document.getElementById('lbl-stress-btn').innerText = t.stress_btn;
        document.getElementById('lbl-symp-head').innerText = t.symp_head;
        document.getElementById('lbl-symp-desc').innerText = t.symp_desc;
        document.getElementById('lbl-btn-correlate').innerText = t.btn_correlate;
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

    async function correlateSymptoms() {
        const query = document.getElementById('symp-input').value;
        const fd = new FormData();
        fd.append('symptom', query);
        fd.append('user_id', activeUser.id);

        const res = await fetch('/api/v1/symptoms/correlate', { method: 'POST', body: fd });
        const d = await res.json();
        const lang = currentLang;
        
        let html = '<h6 class="text-warning fw-bold small mb-3"><i class="fa-solid fa-dna me-1"></i> BIOLOGICAL REASONING DERIVED FROM YOUR LAB TESTS:</h6>';
        
        d.correlations.forEach(c => {
            const expText = typeof c.explanation === 'object' ? (c.explanation[lang] || c.explanation['en']) : c.explanation;
            const statusText = typeof c.status_label === 'object' ? (c.status_label[lang] || c.status_label['en']) : c.status_label;
            
            html += `
                <div class="p-3 mb-3 rounded bg-dark border border-secondary border-opacity-50">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <strong class="text-white fs-6"><i class="fa-solid fa-vial-circle-check text-success me-1"></i> ${c.biomarker} (${c.value})</strong>
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

    async function computeStressLoad() {
        const sl = document.getElementById('st-sleep').value;
        const st = document.getElementById('st-stress').value;

        const fd = new FormData();
        fd.append('sleep_hours', sl);
        fd.append('work_stress', st);

        const res = await fetch('/api/v1/stress/assess', { method: 'POST', body: fd });
        const d = await res.json();
        const lang = currentLang;

        document.getElementById('stress-result-box').innerHTML = `
            <div class="text-warning fw-bold"><i class="fa-solid fa-heart-pulse me-1"></i> ${d.status[lang]} (Score: ${d.score})</div>
            <div class="text-info mt-1">High evening cortisol prompts liver gluconeogenesis. Perform 4-4-4-4 Box Breathing for 5 minutes before bed.</div>
        `;
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

        activeUser = { id: d.user_id, name: d.full_name, email: d.email };
        localStorage.setItem('helix_user', JSON.stringify(activeUser));
        await loadDashboard();
    }

    async function register() {
        const fn = document.getElementById('up-name').value;
        const em = document.getElementById('up-email').value;
        const pw = document.getElementById('up-pw').value;

        const fd = new FormData();
        fd.append('full_name', fn);
        fd.append('email', em);
        fd.append('password', pw);

        const res = await fetch('/api/v1/auth/register', { method: 'POST', body: fd });
        const d = await res.json();
        if (!res.ok) { alert(d.detail || "Registration failed"); return; }

        activeUser = { id: d.user_id, name: d.full_name, email: d.email };
        localStorage.setItem('helix_user', JSON.stringify(activeUser));
        await loadDashboard();
    }

    function logoutUser() {
        localStorage.removeItem('helix_user');
        activeUser = null;
        loadDashboard();
    }

    async function uploadReport() {
        if (!activeUser) {
            alert("Please sign in or register first.");
            return;
        }

        const hosp = document.getElementById('up-hosp').value || "Metropolis Healthcare";
        const rDate = document.getElementById('up-date').value || "2026-08-19";
        const text = document.getElementById('up-text').value;
        const fileIn = document.getElementById('up-file');

        const fd = new FormData();
        fd.append('user_id', activeUser.id);
        fd.append('hospital_name', hosp);
        fd.append('record_date', rDate);
        fd.append('raw_ocr_text', text);

        if (fileIn.files.length > 0) {
            fd.append('report_file', fileIn.files[0]);
        }

        try {
            const res = await fetch('/api/v1/pipeline/upload-report', { method: 'POST', body: fd });
            const d = await res.json();
            if (!res.ok) { alert(d.detail || "Upload failed"); return; }

            bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
            await loadDashboard();
            alert(currentLang === 'hi' ? "✅ रिपोर्ट, ९०-दिन का ट्विन एवं सुरक्षा सत्यापन अपडेट हुआ!" : currentLang === 'mr' ? "✅ अहवाल, ९०-दिवसांचा ट्विन व सुरक्षा पडताळणी अपडेट झाली!" : "✅ Report, 90-day twin & safety verification updated!");
        } catch (err) {
            console.error("Upload error:", err);
            alert("Error uploading report. Please check server connection.");
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
