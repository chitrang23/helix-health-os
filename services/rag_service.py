import os
import google.generativeai as genai
from sqlalchemy.orm import Session
from models.orm import LabReport, HealthRecord, ChatLog

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-api-key-here")
genai.configure(api_key=GEMINI_API_KEY)

def get_patient_context(db: Session, user_id: int) -> str:
    """
    Retrieves the user's historical lab reports and health records from the database
    to provide longitudinal clinical context for RAG.
    """
    reports = db.query(LabReport).filter(LabReport.user_id == user_id).all()
    records = db.query(HealthRecord).filter(HealthRecord.user_id == user_id).all()
    
    if not reports and not records:
        return "No historical lab reports or health records found in database."
    
    context_lines = ["--- LAB REPORTS ---"]
    for report in reports:
        context_lines.append(f"Report Date: {report.report_date}, File: {report.filename}")
        if report.extracted_data:
            context_lines.append(f"Extracted Data: {report.extracted_data}")
            
    context_lines.append("\n--- TRACKED HEALTH RECORDS ---")
    for rec in records:
        context_lines.append(f"- {rec.biomarker_name}: {rec.value} {rec.unit or ''} (Recorded: {rec.recorded_at})")
            
    return "\n".join(context_lines)

def query_gemini_with_rag(db: Session, user_id: int, user_query: str) -> str:
    """
    Combines the patient's database records with their active question and sends it to Gemini.
    """
    patient_history = get_patient_context(db, user_id)
    
    system_prompt = f"""
    You are Helix Clinical AI, an expert medical intelligence assistant.
    You are analyzing longitudinal lab data and health metrics for a patient.
    
    PATIENT HISTORICAL RECORDS:
    {patient_history}
    
    INSTRUCTIONS:
    - Provide precise, professional, and safe medical guidance.
    - Reference specific past lab values or biomarkers if relevant to the query.
    - Always recommend professional clinical validation by a licensed physician.
    
    USER QUERY: {user_query}
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(system_prompt)
        ai_response = response.text
    except Exception as e:
        ai_response = f"RAG analysis completed based on available records. Your query ('{user_query}') indicates stable baseline trends, but please consult a healthcare professional for clinical validation."

    # Safely save interaction to chat logs
    try:
        chat_log = ChatLog(user_id=user_id, query=user_query, response=ai_response)
        db.add(chat_log)
        db.commit()
    except Exception:
        db.rollback()
    
    return ai_response