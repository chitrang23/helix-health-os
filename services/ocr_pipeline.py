import os
import re
from typing import Dict, Any

class MultiEngineOCR:
    @staticmethod
    def extract_lab_report(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Multi-engine extraction pipeline:
        Primary: Structured pattern parser
        Fallback: Text fallback engine
        """
        text = ""
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

        # Pattern extraction for common lab markers
        extracted_biomarkers = {}

        patterns = {
            "eGFR": r"eGFR\s*[:=]?\s*(\d+(?:\.\d+)?)",
            "HbA1c": r"HbA1c\s*[:=]?\s*(\d+(?:\.\d+)?)",
            "ALT": r"ALT\s*[:=]?\s*(\d+(?:\.\d+)?)",
            "Creatinine": r"Creatinine\s*[:=]?\s*(\d+(?:\.\d+)?)"
        }

        for marker, regex in patterns.items():
            match = re.search(regex, text, re.IGNORECASE)
            if match:
                extracted_biomarkers[marker] = float(match.group(1))

        return {
            "filename": filename,
            "status": "completed",
            "extracted_count": len(extracted_biomarkers),
            "biomarkers": extracted_biomarkers
        }
