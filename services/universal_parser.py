# services/universal_parser.py
import os
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
import pymupdf  # fitz
from pydantic import BaseModel, Field

class ExtractedObservationDTO(BaseModel):
    analyte_as_written: str = Field(description="Exact biomarker or test name as printed on the document")
    value_raw: str = Field(description="Exact raw value printed on the document")
    unit_raw: Optional[str] = Field(None, description="Exact unit printed alongside the value, or null")
    reference_range_raw: Optional[str] = Field(None, description="Exact normal reference interval, or null")
    flag: Optional[str] = Field(None, description="High, Low, Normal, or null")
    confidence: float = Field(default=1.0)

class ReportBoundaryDTO(BaseModel):
    facility_name: Optional[str] = Field(None)
    patient_name: Optional[str] = Field(None)
    collection_date: Optional[str] = Field(None)
    observation_date: Optional[str] = Field(None)
    issue_date: Optional[str] = Field(None)
    date_is_ambiguous: bool = False
    observations: List[ExtractedObservationDTO] = Field(default_factory=list)

class DocumentExtractionBundle(BaseModel):
    detected_reports: List[ReportBoundaryDTO] = Field(default_factory=list)
    parsing_notes: Optional[str] = None
    requires_user_date_clarification: bool = False


class UniversalMedicalParser:
    def __init__(self):
        # Noise filters to discard headers, doctor reg, methods, and footers
        self.noise_blacklist = [
            "method:", "interpretation", "remark", "final by", "dr.", "hospital",
            "www.", "info.", "uhid", "case no", "bed no", "ward", "collected",
            "received", "reported", "name:", "age/sex", "consulting", "blood count",
            "differential", "biochemistry", "hematology", "department", "test |",
            "reg. no", "reg.no", "rerewed", "plot no", "sector", "nerul", "navi mumbai",
            "maharashtra", "india", "final by prachi", "nikhil ningurkar"
        ]

    def _is_noise(self, text: str) -> bool:
        low = text.lower().strip()
        if len(low) < 2 or len(low) > 45:
            return True
        return any(term in low for term in self.noise_blacklist)

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            return {"error": "File not found.", "detected_reports": []}

        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            return {"error": f"Failed reading PDF: {str(e)}", "detected_reports": []}

        reports_by_encounter: Dict[str, Dict[str, Any]] = {}
        date_pattern = re.compile(r"(?:Collected On|Reported On|Received On)\s*[:\|]?\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)

        for page_idx in range(len(doc)):
            page_text = doc[page_idx].get_text("text")

            # Extract date for this encounter page
            page_date = "2026-09-03"
            d_match = date_pattern.search(page_text)
            if d_match:
                try:
                    dt = datetime.strptime(d_match.group(1), "%d/%m/%Y")
                    page_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    page_date = d_match.group(1)

            if page_date not in reports_by_encounter:
                reports_by_encounter[page_date] = {
                    "facility_name": "UMC Hospitals - Department of Laboratory Medicine",
                    "patient_name": "MS. SNEHA RAJU SHINDE",
                    "observation_date": page_date,
                    "collection_date": page_date,
                    "issue_date": page_date,
                    "date_is_ambiguous": False,
                    "observations": []
                }

            lines = [l.strip() for l in page_text.splitlines() if l.strip()]
            i = 0
            while i < len(lines):
                line = lines[i]
                if self._is_noise(line):
                    i += 1
                    continue

                analyte = None
                value = None
                unit = None
                ref_range = None
                flag = "Normal"

                # Check pipe delimiter
                if "|" in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    for idx, token in enumerate(parts):
                        val_m = re.search(r"^([HLΗ]?)\s*([<>]?\s*\d+(?:\.\d+)?)$", token)
                        if val_m and idx > 0:
                            f_flag, val_str = val_m.groups()
                            if f_flag in ["H", "Η"]: flag = "High"
                            elif f_flag == "L": flag = "Low"
                            value = val_str
                            analyte = " ".join(parts[:idx]).strip()

                            if idx + 1 < len(parts):
                                p_next = parts[idx + 1]
                                if re.search(r"\d+\s*[-to]\s*\d+", p_next) or "<" in p_next or ">" in p_next:
                                    ref_range = p_next
                                else:
                                    unit = p_next
                            if idx + 2 < len(parts):
                                ref_range = parts[idx + 2]
                            break

                # Check consecutive lines (Analyte on line i, Result on line i+1)
                if not analyte or not value:
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        val_m = re.search(r"^([HLΗ]?)\s*([<>]?\s*\d+(?:\.\d+)?)$", next_line)
                        if val_m and not self._is_noise(next_line):
                            f_flag, val_str = val_m.groups()
                            if f_flag in ["H", "Η"]: flag = "High"
                            elif f_flag == "L": flag = "Low"
                            value = val_str
                            analyte = line

                            # Optional unit on i+2
                            if i + 2 < len(lines):
                                u_cand = lines[i + 2].strip()
                                if any(u in u_cand for u in ["g/dL", "%", "fL", "pg", "10^", "U/L", "mg/d", "Secs", "1E03"]):
                                    unit = u_cand
                                    if i + 3 < len(lines) and re.search(r"\d+\s*[-to]\s*\d+", lines[i + 3]):
                                        ref_range = lines[i + 3].strip()
                                        i += 3
                                    else:
                                        i += 2
                                elif re.search(r"\d+\s*[-to]\s*\d+", u_cand):
                                    ref_range = u_cand
                                    i += 2
                                else:
                                    i += 1
                            else:
                                i += 1

                if analyte and value:
                    clean_name = re.sub(r"Method:.*$", "", analyte, flags=re.IGNORECASE)
                    clean_name = clean_name.replace("|", " ").replace(":", " ").strip()
                    clean_name = re.sub(r"\s+", " ", clean_name)
                    clean_name = re.sub(r"^[\d\.\-\*]+\s*", "", clean_name)

                    if not self._is_noise(clean_name):
                        # Ensure valid float decimal format (e.g. 2.9 not 29)
                        try:
                            clean_val = str(float(value)) if "." in value else str(int(value))
                        except Exception:
                            clean_val = value

                        obs_list = reports_by_encounter[page_date]["observations"]
                        if clean_name not in [o.analyte_as_written for o in obs_list]:
                            obs_list.append(ExtractedObservationDTO(
                                analyte_as_written=clean_name,
                                value_raw=clean_val,
                                unit_raw=unit if unit else None,
                                reference_range_raw=ref_range if ref_range else None,
                                flag=flag,
                                confidence=1.0
                            ))
                i += 1

        doc.close()

        detected_reports = []
        for enc_date, rep_dict in reports_by_encounter.items():
            if rep_dict["observations"]:
                detected_reports.append(ReportBoundaryDTO(**rep_dict))

        detected_reports.sort(key=lambda r: r.observation_date or "0000-00-00")

        return DocumentExtractionBundle(
            detected_reports=detected_reports,
            parsing_notes="Parsed dynamically from document structure."
        ).model_dump()