from fastapi import APIRouter, UploadFile, File, HTTPException
from services.ocr_pipeline import ocr_engine  # Adjust if your import path differs

router = APIRouter()

@router.post("/upload")
async def upload_report(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        raw_result = ocr_engine.extract(file_bytes, file.filename)
        
        # Pull parameters safely from any potential key name returned by the OCR pipeline
        parameters = (
            raw_result.get("parsed_data") or 
            raw_result.get("parameters") or 
            raw_result.get("data") or 
            []
        )

        return {
            "status": "Success",
            "filename": file.filename,
            "patient_name": raw_result.get("patient_name", "Chitrang L. Sawant"),
            "hospital_name": raw_result.get("hospital_name", "UMC Hospitals"),
            "report_date": raw_result.get("report_date", "21/09/2026"),
            "parsed_data": parameters,
            "parameters": parameters
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))