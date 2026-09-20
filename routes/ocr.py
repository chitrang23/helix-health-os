from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from services.ocr_pipeline import MultiEngineOCR

ocr_router = APIRouter(prefix="/api/v1/ocr", tags=["OCR Lab Processing"])

@ocr_router.post("/process-async")
async def process_lab_report_async(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    if not file.filename.lower().endswith(('.pdf', '.txt', '.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Unsupported file format.")

    content = await file.read()
    results = MultiEngineOCR.extract_lab_report(content, file.filename)
    return {
        "message": "File processed successfully",
        "results": results
    }
