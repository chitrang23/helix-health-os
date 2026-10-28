# routes/chat.py
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from google import genai

from core.database import get_db
from core.security import get_current_authenticated_user
from models.orm import User, ClinicalObservation, ChatLog

# No prefix here because main.py already prefixes it with "/api/chat"
router = APIRouter(tags=["Clinical Assistant Chat"])

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's clinical question or prompt")

@router.post("")
@router.post("/")
def chat_with_helix(
    req: ChatRequest,
    current_user: User = Depends(get_current_authenticated_user),
    db: Session = Depends(get_db)
):
    clean_query = req.message.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    observations = (
        db.query(ClinicalObservation)
        .filter(ClinicalObservation.user_id == current_user.id)
        .all()
    )

    vault_summary = "\n".join([
        f"- {obs.analyte_as_written}: {obs.original_value} {obs.original_unit or ''} (Ref: {obs.printed_reference_range or 'N/A'}, Flag: {obs.laboratory_flag})"
        for obs in observations[:35]
    ]) or "No laboratory records currently ingested in vault."

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    reply_text = ""

    # Try Gemini API generation first using the active model
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            system_prompt = f"""You are Helix AI, an expert clinical intelligence assistant. Answer the patient based strictly on their verified diagnostic vault records.

PATIENT'S VERIFIED LAB OBSERVATIONS:
{vault_summary}

PATIENT QUESTION:
{clean_query}

INSTRUCTIONS:
1. Answer accurately using only the ingested lab data above.
2. Maintain a compassionate, professional tone.
3. If the data is missing from the vault, explicitly state: 'Not available — no source data provided in your uploaded reports.'"""

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=system_prompt
            )
            reply_text = response.text.strip()
        except Exception as e:
            print(f"Chat API rate-limit or error (falling back to offline vault parser): {e}")

    # Standalone Offline Fallback if API hits rate limits (429) or fails
    if not reply_text:
        query_lower = clean_query.lower()
        matching_obs = [o for o in observations if o.analyte_as_written.lower() in query_lower]
        
        if matching_obs:
            matches_str = ", ".join([f"{o.analyte_as_written} is {o.original_value} {o.original_unit or ''} ({o.laboratory_flag})" for o in matching_obs])
            reply_text = f"Based on your verified report vault: {matches_str}."
        else:
            reply_text = f"Your uploaded records contain the following parameters: {vault_summary[:300]}..."

    try:
        log_entry = ChatLog(user_id=current_user.id, query=clean_query, response=reply_text, source_citations=[])
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "success": True,
        "response": reply_text
    }