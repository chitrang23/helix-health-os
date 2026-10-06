from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from services.rag_service import query_gemini_with_rag
# Uncomment or import your user dependency if you have JWT authentication set up:
# from core.security import get_current_user 
# from models.orm import User

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    history: list = []
    user_id: int = 1  # Fallback to user_id 1 if not extracted from auth middleware yet

@router.post("/")
async def chat_with_helix(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Accepts user clinical queries, triggers the RAG pipeline utilizing longitudinal
    lab reports and health records from the database, and returns Gemini's analysis.
    """
    if not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Query message cannot be empty."
        )
    
    try:
        # Perform RAG-backed query using database records
        ai_response = query_gemini_with_rag(db=db, user_id=req.user_id, user_query=req.message)
        
        return {
            "response": ai_response,
            "citations": ["Helix Longitudinal Database", "AI Clinical Intelligence Engine"],
            "disclaimer": "Helix is an AI health companion, not an autonomous doctor. Please consult a licensed physician for clinical validation."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your clinical chat request: {str(e)}"
        )