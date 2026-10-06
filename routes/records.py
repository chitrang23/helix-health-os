from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, Header
from fastapi.responses import JSONResponse, FileResponse
import pdfplumber
import pytesseract
import pymupdf
from PIL import Image
import io
import re
import platform
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import jwt

router = APIRouter(prefix="/api/records", tags=["Medical Records"])
executor = ThreadPoolExecutor(max_workers=8)

SECRET_KEY = "helix_super_secret_enterprise_key"
ALGORITHM = "HS256"

# In-memory user history store mapping user email -> list of uploaded reports
# In production, this maps to your SQLAlchemy database tables
user_records_db = {}

def get_current_user_email(authorization: str = Header(None)) -> str:
    """Extracts user email from JWT token in Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token.")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

if platform.system() == "Windows":
    possible_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe')
    ]
    for p in possible_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break

def fast_ocr_extraction(file_bytes: bytes, filename: str) -> str:
    raw_text = ""
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages[:5]:
                    text = page.extract_text()
                    if text:
                        raw_text += text + "\n"
        except Exception:
            pass
        
        if not raw_text.strip():
            try:
                doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                for page in doc[:3]:
                    pix = page.get_pixmap(dpi=100)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    raw_text += pytesseract.image_to_string(img, config='--psm 6 -c preserve_interword_spaces=1') + "\n"
            except Exception as e:
                print(f"[Fast OCR Error]: {e}")

    elif filename_lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")):
        try:
            image = Image.open(io.BytesIO(file_bytes))
            raw_text = pytesseract.image_to_string(image, config='--psm 6')
        except Exception as e:
            print(f"[Image Error]: {e}")

    return raw_text

def extract_metadata_from_header(raw_text: str) -> dict:
    meta = {"report_date": datetime.now().strftime("%Y-%m-%d"), "hospital_name": "General Diagnostic Facility"}
    
    date_match = re.search(r'(?:date|collected|reported|specimen\s+date)[\s\:\-\=]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})', raw_text, re.IGNORECASE)
    if date_match:
        meta["report_date"] = date_match.group(1)

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()][:10]
    for line in lines:
        if re.search(r'(hospital|diagnostics|pathology|laboratory|labs|clinic|health\s+care)', line, re.IGNORECASE):
            clean_name = re.sub(r'^(welcome\s+to|department\s+of|name\s*:)', '', line, flags=re.IGNORECASE).strip()
            if len(clean_name) > 3:
                meta["hospital_name"] = clean_name
                break

    return meta

def parse_report_parameters(raw_text: str) -> dict:
    biomarkers = {}
    ignore_keywords = ["page", "date", "sample", "patient", "dr.", "lab", "hospital", "ref", "signature", "report", "phone", "address"]

    lines = raw_text.split('\n')
    for line in lines:
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 3 or any(kw in line_clean.lower() for kw in ignore_keywords):
            continue

        match = re.search(r'^([a-zA-Z\s\(\)\-\/\.\,\+\%]{3,35})[\s\:\-\=\|]+(\d+\.?\d*)\s*(mg/dL|g/dL|mmol/L|%|u/L|IU/L|mEq/L|ng/mL|pg/mL|fL|pg|g/L|fl)?', line_clean, re.IGNORECASE)
        if match:
            param_name = match.group(1).strip()
            param_name = re.sub(r'\s+[A-Za-z]$', '', param_name).strip()
            param_val = float(match.group(2))
            param_unit = match.group(3) if match.group(3) else ""

            if len(param_name) >= 3 and param_name.lower() not in ignore_keywords:
                if param_name not in biomarkers:
                    biomarkers[param_name] = {"value": param_val, "unit": param_unit}

    return biomarkers

@router.get("/history-page")
async def serve_history_page():
    return FileResponse("public/history.html")

@router.get("/history/me")
async def get_my_patient_history(authorization: str = Header(None)):
    """Fetches real longitudinal history for the currently authenticated user."""
    user_email = get_current_user_email(authorization)
    history = user_records_db.get(user_email, [])
    return {"success": True, "total_records": len(history), "history": history}

@router.post("/upload-report")
async def process_lab_report(file: UploadFile = File(...), authorization: str = Header(None)):
    # 1. Authenticate user from JWT token
    user_email = get_current_user_email(authorization)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    loop = asyncio.get_event_loop()
    raw_text = await loop.run_in_executor(executor, fast_ocr_extraction, contents, file.filename)
    
    metadata = extract_metadata_from_header(raw_text)
    extracted_biomarkers = parse_report_parameters(raw_text)

    if not extracted_biomarkers:
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "message": "Report extracted, but no structured parameters were identified.",
                "filename": file.filename,
                "metadata": metadata,
                "extracted_biomarkers": {}
            }
        )

    # 2. Package record for longitudinal tracking
    new_record = {
        "diagnosis_title": f"Lab Report: {file.filename}",
        "description": f"Extracted {len(extracted_biomarkers)} clinical parameters.",
        "hospital_name": metadata.get("hospital_name", "General Diagnostic Facility"),
        "diagnosis_date": metadata.get("report_date"),
        "biomarkers": extracted_biomarkers
    }

    # 3. Store record under the authenticated user's profile
    if user_email not in user_records_db:
        user_records_db[user_email] = []
    user_records_db[user_email].append(new_record)

    return {
        "success": True,
        "message": f"Successfully ingested {len(extracted_biomarkers)} parameters for longitudinal tracking.",
        "filename": file.filename,
        "metadata": metadata,
        "extracted_biomarkers": extracted_biomarkers
    }