import os
import pdfplumber

def extract_text(file_path: str) -> str:
    text = ""
    try:
        if file_path.endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
        else:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        print(f"OCR Engine Error: {e}")
    print(f"DEBUG OCR Extracted Length: {len(text)}")
    return text
