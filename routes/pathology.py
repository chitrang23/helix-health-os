from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from google import genai
from google.genai import types

router = APIRouter(prefix="/api/pathology", tags=["Pathology Synthesizer"])

@router.post("/synthesize")
async def synthesize_pathology(
    file: UploadFile = File(...),
    clinical_focus: str = Form(...)
):
    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded scan file is empty.")

        # Initialize the Gemini client (picks up GEMINI_API_KEY from environment variables)
        client = genai.Client()

        # Call Gemini using the multi-modal capable model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=file.content_type or 'image/jpeg',
                ),
                f"Perform a detailed medical multi-modal synthesis scan correlation for clinical focus: {clinical_focus}. Analyze visual tissue structures, anomalies, and clinical indications based on this uploaded scan/image."
            ]
        )

        return {
            "success": True,
            "synthesis_report": response.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))