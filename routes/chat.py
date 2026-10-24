# routes/chat.py
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from google import genai

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, ClinicalObservation, SourceDocument, ChatLog

router = APIRouter(prefix="/api/chat", tags=["Clinical Assistant Chat"])


class ChatMessageHistory(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Patient medical or document query")
    history: Optional[List[ChatMessageHistory]] = Field(default_factory=list, description="Recent conversation turns")


@router.post("/")
def chat_with_helix(
    req: ChatRequest,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Owner-scoped RAG clinical assistant:
    Answers queries grounded exclusively in the authenticated patient's verified source documents
    and health records. Never fabricates values, diagnoses, or cross-tenant observations.
    """
    clean_query = req.message.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    # 1. Retrieve all verified observations and linked source documents for this user
    observations = (
        db.query(ClinicalObservation, SourceDocument)
        .outerjoin(SourceDocument, ClinicalObservation.document_id == SourceDocument.id)
        .filter(ClinicalObservation.user_id == current_user.id)
        .order_by(ClinicalObservation.effective_date.asc())
        .all()
    )

    # 2. Honest Zero-Data Handling: Never invent hypothetical or default patient profiles
    if not observations:
        empty_response = (
            "Your health record vault currently contains no uploaded lab documents or logged vital measurements. "
            "I cannot answer questions about your specific health values or trends until a report is uploaded or an observation is logged."
        )
        try:
            log_entry = ChatLog(
                user_id=current_user.id,
                query=clean_query,
                response=empty_response,
                source_citations=[]
            )
            db.add(log_entry)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "response": empty_response,
            "citations": [],
            "grounding": "Not available — zero source documents or measurements recorded for this patient.",
            "disclaimer": "Helix is an AI educational companion, not an autonomous physician. Always consult a qualified clinician."
        }

    # 3. Assemble Grounded Clinical Context with Exact Source Traceability
    context_lines = []
    citations = []
    unique_sources = set()

    for obs, doc in observations:
        date_str = obs.effective_date.strftime("%Y-%m-%d") if obs.effective_date else "Undated on report"
        source_name = doc.filename if doc and doc.filename else "User manual entry"
        facility = doc.facility_name if doc and doc.facility_name else "Facility not specified"
        ref_range = f" [Printed Ref: {obs.printed_reference_range}]" if obs.printed_reference_range else ""
        flag_str = f" [Flag: {obs.laboratory_flag}]" if obs.laboratory_flag else ""

        line = (
            f"- Analyte: {obs.analyte_as_written} | Value: {obs.original_value} {obs.original_unit or ''}"
            f"{ref_range}{flag_str} | Date: {date_str} | Source: {source_name} ({facility})"
        )
        context_lines.append(line)

        if source_name not in unique_sources:
            unique_sources.add(source_name)
            citations.append({
                "source_document": source_name,
                "facility": facility,
                "document_id": doc.id if doc else None
            })

    # 4. Format Prior Conversation History if Provided
    conversation_context = ""
    if req.history:
        history_snippets = []
        for h in req.history[-6:]:  # Keep recent context bounded
            role_label = "User" if h.role == "user" else "Assistant"
            history_snippets.append(f"{role_label}: {h.content}")
        conversation_context = f"\nRECENT CHAT HISTORY:\n" + "\n".join(history_snippets) + "\n"

    # 5. Build Strict Clinical System Prompt
    system_prompt = f"""You are the Helix Health OS Clinical Assistant.
Analyze and answer strictly based on the authenticated patient's verified health records below.

PATIENT'S DOCUMENTED CLINICAL RECORDS:
{chr(10).join(context_lines)}
{conversation_context}
MANDATORY RULES:
1. ZERO INVENTED DATA: Never fabricate, assume, or infer unmentioned medical history, medications, allergies, diagnoses, or lab results.
2. MISSING VALUES: If the user asks about an analyte, test, or symptom not listed in their records above, explicitly state:
   'Not available — no source data provided in your uploaded reports.'
3. CLEAR SEPARATION: Clearly distinguish:
   - 'Your report states:' (exact values printed on the document)
   - 'What this generally measures:' (plain-language medical context)
   - 'General medical guidance:' (evidence-based educational information)
4. CITE SOURCES: Mention the specific report document name and date when citing a value.
5. NO DEFINITIVE DIAGNOSES: Explain what tests measure and how they compare with the reference range printed on that report, but never issue a definitive medical diagnosis.

PATIENT QUERY: {clean_query}"""

    # 6. Check for Gemini API Configuration
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        fallback_msg = (
            "Clinical AI reasoning engine is currently unconfigured (GEMINI_API_KEY missing). "
            f"Your vault contains {len(observations)} verified observation(s) across {len(unique_sources)} source document(s). "
            "Please configure the API key to enable document Q&A."
        )
        return {
            "response": fallback_msg,
            "citations": citations,
            "disclaimer": "Helix Health OS requires an active API key for AI document synthesis."
        }

    # 7. Execute AI Generation with Strict Grounding
    try:
        client = genai.Client(api_key=api_key)
        ai_result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt
        )
        reply_text = ai_result.text.strip()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Clinical AI provider failure: {str(e)}"
        )

    # 8. Record Interaction in Database ChatLog for Auditability
    try:
        log_entry = ChatLog(
            user_id=current_user.id,
            query=clean_query,
            response=reply_text,
            source_citations=[c["source_document"] for c in citations]
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "response": reply_text,
        "citations": [c["source_document"] for c in citations],
        "detailed_citations": citations,
        "records_evaluated": len(observations),
        "disclaimer": "Helix provides source-grounded educational explanations. It does not provide medical diagnosis or replace a licensed clinician."
    }