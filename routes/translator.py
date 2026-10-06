from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from deep_translator import GoogleTranslator

router = APIRouter(prefix="/api/translate", tags=["Translation Service"])

class TranslateRequest(BaseModel):
    texts: List[str]
    target_language: str  # 'hi' for Hindi, 'mr' for Marathi, 'en' for English

class TranslateDictRequest(BaseModel):
    data: Dict[str, Any]
    target_language: str

# Helper function to map language codes
def get_dest_lang(code: str) -> str:
    mapping = {
        "hi": "hi",
        "mr": "mr",
        "en": "en"
    }
    return mapping.get(code, "en")

@router.post("/batch")
async def translate_batch(req: TranslateRequest):
    dest = get_dest_lang(req.target_language)
    if dest == "en" or not req.texts:
        return {"translations": req.texts}
    
    try:
        translator = GoogleTranslator(source='auto', target=dest)
        # Translate each text item dynamically without hardcoding
        translated_texts = [translator.translate(text) if text else text for text in req.texts]
        return {"translations": translated_texts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/object")
async def translate_object(req: TranslateDictRequest):
    dest = get_dest_lang(req.target_language)
    if dest == "en" or not req.data:
        return {"translated_data": req.data}

    try:
        translator = GoogleTranslator(source='auto', target=dest)
        translated_data = {}
        
        for key, value in req.data.items():
            if isinstance(value, str) and value.strip():
                translated_data[key] = translator.translate(value)
            elif isinstance(value, list):
                # Translate lists of strings dynamically
                translated_data[key] = [
                    translator.translate(item) if isinstance(item, str) else item 
                    for item in value
                ]
            else:
                translated_data[key] = value
                
        return {"translated_data": translated_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))