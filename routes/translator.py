import os
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# Mounts cleanly in main.py whether mounted at /api/translator or /api/translate
router = APIRouter(tags=["Medical Translation & Localization"])

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "en": "English"
}

# Standalone offline dictionary fallback for UI localization when API times out
OFFLINE_DICTIONARY = {
    "hi": {
        "Dashboard & OCR": "डैशबोर्ड और ओसीआर",
        "Patient History": "रोगी का इतिहास",
        "Stress & Mindfulness": "तनाव और सचेतनता",
        "Gemini Clinical Chat": "जेमिनी नैदानिक चैट",
        "30-Day Twin": "३०-दिवसीय डिजिटल ट्विन",
        "SOAP & Billing": "एसओएपी और बिलिंग",
        "Specialists": "विशेषज्ञ",
        "Drug Safety Shield": "दवा सुरक्षा कवच",
        "Organ Radar & Indices": "ऑर्गन रडार और सूचकांक",
        "Report Ingestion & OCR Hub": "रिपोर्ट अंतर्ग्रहण और ओसीआर केंद्र",
        "Parse & Ground Document": "रिपोर्ट विश्लेषित करें",
        "Live Report Metadata": "लाइव रिपोर्ट मेटाडाटा",
        "Extracted Clinical Parameters": "निकाले गए नैदानिक पैरामीटर",
        "Biomarker Intelligence & Range": "बायोमार्कर बुद्धिमत्ता और सीमा",
        "Verified Longitudinal Timeline": "सत्यापित अनुदैर्ध्य समयरेखा"
    },
    "mr": {
        "Dashboard & OCR": "डॅशबोर्ड आणि ओसीआर",
        "Patient History": "रुग्णाचा इतिहास",
        "Stress & Mindfulness": "तनाव आणि सजगता",
        "Gemini Clinical Chat": "जेमिनी क्लिनिकल चॅट",
        "30-Day Twin": "३०-दिवसीय डिजिटल ट्विन",
        "SOAP & Billing": "एसओएपी आणि बिलिंग",
        "Specialists": "तज्ञ",
        "Drug Safety Shield": "औषध सुरक्षा कवच",
        "Organ Radar & Indices": "ऑर्गन रडार और निर्देशक",
        "Report Ingestion & OCR Hub": "रिपोर्ट इन्जेशन आणि ओसीआर केंद्र",
        "Parse & Ground Document": "रिपोर्ट तपासा",
        "Live Report Metadata": "लाइव रिपोर्ट मेटाडाटा",
        "Extracted Clinical Parameters": "काढलेले क्लिनिकल पॅरामीटर्स",
        "Biomarker Intelligence & Range": "बायोमार्कर बुद्धिमत्ता आणि श्रेणी",
        "Verified Longitudinal Timeline": "सत्यापित कालरेषा"
    }
}


class TranslationBatchRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, description="Array of natural language strings to translate")
    target_language: str = Field(..., description="Target language code: 'hi' (Hindi), 'mr' (Marathi), 'en' (English)")


class TranslationDictRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="Structured JSON payload with natural language fields to translate")
    target_language: str = Field(..., description="Target language code: 'hi', 'mr', or 'en'")


@router.post("/batch")
@router.post("/api/translate/batch")
def translate_batch(req: TranslationBatchRequest):
    """
    Translates UI strings and clinical explanations into Hindi, Marathi, or English.
    Strictly preserves clinical terms, numbers, units, drug names, and diagnostic uncertainty.
    """
    target_code = req.target_language.strip().lower()
    target_lang_name = SUPPORTED_LANGUAGES.get(target_code)

    if not target_lang_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported target language '{target_code}'. Supported languages: 'en' (English), 'hi' (Hindi), 'mr' (Marathi)."
        )

    # English identity fast-path
    if target_code == "en" or not req.texts:
        return {
            "status": "success",
            "target_language": target_code,
            "language_name": "English",
            "translations": req.texts,
            "side_by_side": [{"original": t, "translated": t} for t in req.texts]
        }

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    translated_list = []

    if api_key:
        prompt = f"""You are an enterprise medical translator specializing in healthcare localization into {target_lang_name}.
Translate the array of strings into culturally natural, clinically accurate {target_lang_name}.

NON-NEGOTIABLE CLINICAL INTEGRITY RULES:
1. PRESERVE NUMERALS & UNITS: Do not alter, translate, or convert any number, decimal, date, or unit (e.g., '13.5 g/dL', '2026-09-21' must remain '13.5 g/dL', '2026-09-21').
2. PRESERVE DRUG & TEST NAMES: Keep medication names (e.g., Metformin, Atorvastatin, Warfarin) and clinical analyte abbreviations (e.g., HbA1c, SGPT, eGFR, WBC) in Latin script or transliterated alongside the original name.
3. PRESERVE UNCERTAINTY & NEGATIONS: Never turn 'unlikely' into 'no' or 'elevated' into 'dangerous'. Keep exact clinical nuance and uncertainty intact.

Return ONLY a valid JSON object matching this schema:
{{
  "translations": ["translated string 1", "translated string 2"]
}}

Texts to translate:
{json.dumps(req.texts)}"""

        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            data = json.loads(response.text.strip())
            translated_list = data.get("translations", [])
        except Exception as e:
            print(f"Translator API notice (falling back to offline dictionary): {e}")

    # Fallback to offline dictionary if API is missing, unconfigured, or timed out
    if not translated_list or len(translated_list) != len(req.texts):
        dict_bank = OFFLINE_DICTIONARY.get(target_code, {})
        translated_list = [dict_bank.get(t, t) for t in req.texts]

    # Pad with originals if array length mismatch occurs
    side_by_side = []
    for i, original in enumerate(req.texts):
        trans = translated_list[i] if i < len(translated_list) else original
        side_by_side.append({"original": original, "translated": trans})

    return {
        "status": "success",
        "target_language": target_code,
        "language_name": target_lang_name,
        "translations": translated_list,
        "side_by_side": side_by_side
    }


@router.post("/object")
@router.post("/api/translate/object")
def translate_object(req: TranslationDictRequest):
    """
    Translates natural-language string values in a JSON payload while preserving keys,
    numbers, booleans, dates, units, and structural hierarchy intact.
    """
    target_code = req.target_language.strip().lower()
    target_lang_name = SUPPORTED_LANGUAGES.get(target_code)

    if not target_lang_name or target_code == "en" or not req.data:
        return {
            "status": "success",
            "target_language": target_code,
            "translated_data": req.data
        }

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {
            "status": "offline",
            "target_language": target_code,
            "warning": "GEMINI_API_KEY is not configured; original data preserved without translation.",
            "translated_data": req.data
        }

    prompt = f"""You are a medical JSON translator specializing in {target_lang_name}.
Translate all natural-language string values in the JSON below into {target_lang_name}.
Keep all dictionary keys, numbers, booleans, dates, units, and structural hierarchy completely identical.
Do not modify numbers or biomarker acronyms (HbA1c, SGPT, eGFR, etc.).

JSON to translate:
{json.dumps(req.data)}"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        translated_json = json.loads(response.text.strip())
        return {
            "status": "success",
            "target_language": target_code,
            "language_name": target_lang_name,
            "translated_data": translated_json
        }
    except Exception:
        # Graceful fallback: return original data safely without corrupting payload
        return {
            "status": "fallback",
            "target_language": target_code,
            "warning": "Translation failed; original payload preserved.",
            "translated_data": req.data
        }