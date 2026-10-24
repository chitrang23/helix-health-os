import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.universal_parser import UniversalMedicalParser
from core.database import SessionLocal
from models import HealthReport, BiomarkerRecord

# Fixed: Removed redundant prefix="/" since main.py handles /api/ocr
router = APIRouter(tags=["OCR & Document Intelligence"])
ocr_engine = UniversalMedicalParser()

@router.post("/upload")
async def upload_report(file: UploadFile = File(...)):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)
    
    db = SessionLocal()
    try:
        file_bytes = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
            
        raw_result = ocr_engine.parse_document(file_path)
        
        if isinstance(raw_result, dict) and "error" in raw_result:
            raise HTTPException(status_code=500, detail=raw_result["error"])

        reports_list = raw_result.get("reports", [])
        if not reports_list and "extracted_biomarkers" in raw_result:
            reports_list = [raw_result]

        parsed_summary = []

        for rep in reports_list:
            metadata = rep.get("patient_metadata", {})
            biomarkers = rep.get("extracted_biomarkers", [])
            report_date = metadata.get("report_date", "2026-09-21")
            patient_name = metadata.get("name", "Chitrang L. Sawant")

            report_entry = HealthReport(
                filename=file.filename,
                report_date=report_date,
                patient_name=patient_name
            )
            db.add(report_entry)
            db.commit()
            db.refresh(report_entry)

            for b in biomarkers:
                raw_val = b.get("value")
                
                biomarker_entry = BiomarkerRecord(
                    report_id=report_entry.id,
                    test_name=b.get("test_name"),
                    value=str(raw_val) if raw_val is not None else "",
                    unit=b.get("unit", "")
                )
                db.add(biomarker_entry)
            
            db.commit()
            
            parsed_summary.append({
                "report_date": report_date,
                "patient_metadata": metadata,
                "parameters": biomarkers
            })

        return {
            "status": "Success",
            "filename": file.filename,
            "total_reports_extracted": len(reports_list),
            "reports_data": parsed_summary,
            "parsed_data": reports_list[0].get("extracted_biomarkers", []) if reports_list else [],
            "parameters": reports_list[0].get("extracted_biomarkers", []) if reports_list else []
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass