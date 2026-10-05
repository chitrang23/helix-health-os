from fastapi import APIRouter, UploadFile, File
from services.ocr_pipeline import MultiEngineOCR

router = APIRouter()
ocr_engine = MultiEngineOCR()

@router.post("/upload")
async def upload_report(file: UploadFile = File(...)):
    content = await file.read()
    result = ocr_engine.extract(content, file.filename)
    return result

