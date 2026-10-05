from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    history: list = []

@router.post("/")
async def chat_with_helix(req: ChatRequest):
    msg = req.message.lower()
    reply = f"Based on your longitudinal records regarding '{req.message}': Your trends remain stable under your current regimen."
    if "sugar" in msg or "glucose" in msg or "hba1c" in msg:
        reply = "Your HbA1c has dropped from 6.1% to 5.7% over the last two quarters. Consistent physical activity is producing measurable metabolic improvements."
    
    return {
        "response": reply,
        "citations": ["Clinical Longitudinal Study Vol. 14", "WHO Metabolic Guidelines"],
        "disclaimer": "Helix is an AI health companion, not an autonomous doctor."
    }
