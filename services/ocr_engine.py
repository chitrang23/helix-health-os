import re
import io
from typing import Dict, Any, List
from pypdf import PdfReader
from PIL import Image

class OCREngine:
    @staticmethod
    def parse_pdf_bytes(file_bytes: bytes) -> str:
        extracted_text = ""
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted_text += (page.extract_text() or "") + "\n"
        except Exception:
            pass
        return extracted_text

    @staticmethod
    def parse_image_bytes(file_bytes: bytes) -> str:
        extracted_text = ""
        try:
            import pytesseract
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text = pytesseract.image_to_string(image)
        except Exception:
            pass
        return extracted_text

    # Complete Universal Biomarker Registry with LOINC, Panic Limits & Clinical Guidelines
    MARKER_REGISTRY = {
        "fasting_glucose": {
            "name": "Fasting Blood Glucose",
            "loinc": "1558-6",
            "patterns": [r"(?i)\b(?:fasting\s*glucose|fbs|fasting\s*sugar|blood\s*sugar\s*fasting|glucose\s*fasting)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (70.0, 100.0),
            "panic_limits": (55.0, 250.0),
            "guideline": "ADA Standards of Care 2026 / ICMR Guidelines for Glycemic Management",
            "en": {
                "what": "Morning blood sugar before eating breakfast.",
                "low": "Hypoglycemia. Can cause tremors, cold sweats, and dizziness.",
                "high": "Hyperglycemia / Prediabetes zone. Indicates impaired insulin response.",
                "tip": "Engage in a 15-minute post-meal brisk walk and reduce high-glycemic carbohydrates."
            },
            "hi": {
                "what": "सुबह खाली पेट खून में ग्लूकोज (शर्करा) का स्तर।",
                "low": "हाइपोग्लाइसीमिया। चक्कर, पसीना और कंपकंपी हो सकती है।",
                "high": "प्रीडायबिटीज / बढ़ा हुआ शुगर स्तर। इंसुलिन प्रतिरोध का संकेत।",
                "tip": "भोजन के बाद १५ मिनट टहलें और मीठा व मैदा कम करें।"
            },
            "mr": {
                "what": "सकाळी उपाशीपोटी रक्तातील साखरेचे प्रमाण.",
                "low": "रक्तातील साखर खूप कमी झाली आहे. चक्कर येऊ शकते.",
                "high": "रक्तातील साखर वाढलेली आहे. मधुमेहाचा पूर्वसंकेत.",
                "tip": "जेवणानंतर १५ मिनिटे चाला आणि गोड पदार्थ टाळा."
            }
        },
        "hba1c": {
            "name": "Glycated Hemoglobin (HbA1c)",
            "loinc": "4548-4",
            "patterns": [r"(?i)\b(?:hba1c|glycated\s*hemoglobin|glycosylated\s*hemoglobin)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "%",
            "normal_range": (4.0, 5.6),
            "panic_limits": (3.5, 10.0),
            "guideline": "WHO Diagnostic Thresholds for Glycated Hemoglobin / ADA 2026",
            "en": {
                "what": "90-day biological average of circulating blood sugar.",
                "low": "Abnormally low average glycemic state.",
                "high": "Elevated 3-month sugar. Consistent with insulin resistance.",
                "tip": "Incorporate sprouted legumes, whole grains, and leafy vegetables."
            },
            "hi": {
                "what": "पिछले ३ महीनों के ब्लड शुगर का औसत स्तर।",
                "low": "सामान्य से अत्यधिक कम औसत शुगर।",
                "high": "पिछले ९० दिनों का शुगर बढ़ा हुआ है।",
                "tip": "अंकुरित मूंग, सलाद और रेशेदार अनाज खाएं।"
            },
            "mr": {
                "what": "मागील ३ महिन्यांतील साखरेची सरासरी पातळी.",
                "low": "सरासरी साखर अत्यंत कमी आहे.",
                "high": "मागील ९० दिवसांतील साखर वाढलेली आहे.",
                "tip": "मोड आलेली कडधान्ये आणि पालेभाज्या आहारात वाढवा."
            }
        },
        "ldl_cholesterol": {
            "name": "LDL Cholesterol",
            "loinc": "13457-7",
            "patterns": [r"(?i)\b(?:ldl|ldl\s*cholesterol|low\s*density\s*lipoprotein)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (50.0, 100.0),
            "panic_limits": (30.0, 190.0),
            "guideline": "AHA/ACC Clinical Practice Guidelines on Management of Blood Cholesterol",
            "en": {
                "what": "Atherogenic lipid particles that can deposit in arterial walls.",
                "low": "Optimal low atherogenic lipid profile.",
                "high": "Elevated bad cholesterol. Increases vascular plaque risk.",
                "tip": "Add 20g ground flaxseed daily and avoid trans-fats and palm oil."
            },
            "hi": {
                "what": "खराब कोलेस्ट्रॉल जो रक्त नलिकाओं में वसा जमा कर सकता है।",
                "low": "उत्तम एवं सुरक्षित स्तर।",
                "high": "कोलेस्ट्रॉल अधिक होने से हृदय पर दबाव बढ़ता है।",
                "tip": "रोजाना अलसी (Flaxseeds) लें और तली-भुनी चीजों से बचें।"
            },
            "mr": {
                "what": "वाईट कोलेस्टेरॉल जे रक्तवाहिन्यांमध्ये अडथळा आणू शकते.",
                "low": "सुरक्षित पातळी.",
                "high": "कोलेस्टेरॉल वाढल्यामुळे हृदयावर ताण येऊ शकतो.",
                "tip": "आहारात जवस वापरा आणि तेलकट पदार्थ टाळा."
            }
        },
        "vitamin_d": {
            "name": "25-OH Vitamin D Total",
            "loinc": "62292-8",
            "patterns": [r"(?i)\b(?:vitamin\s*d|25-oh|vit\s*d3?)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "ng/mL",
            "normal_range": (30.0, 100.0),
            "panic_limits": (10.0, 150.0),
            "guideline": "Endocrine Society Clinical Practice Guideline on Vitamin D",
            "en": {
                "what": "Hormonal vitamin essential for bone mineral density and immune response.",
                "low": "Deficiency. Associated with non-specific muscle fatigue and joint aches.",
                "high": "Optimal sunshine level.",
                "tip": "Get 15 minutes of early morning sun exposure and consult physician regarding D3 repletion."
            },
            "hi": {
                "what": "हड्डियों की मजबूती और रोग प्रतिरोधक क्षमता के लिए आवश्यक विटामिन।",
                "low": "विटामिन डी की कमी। थकान और जोड़ों में दर्द का कारण।",
                "high": "उत्तम व पर्याप्त स्तर।",
                "tip": "सुबह की धूप लें और डॉक्टर की सलाह से सप्लीमेंट शुरू करें।"
            },
            "mr": {
                "what": "हाडांच्या बळकटीसाठी आणि प्रतिकारशक्तीसाठी आवश्यक घटक.",
                "low": "व्हिटॅमिनची कमतरता. अंगदुखी आणि थकवा जाणवू शकतो.",
                "high": "उत्तम पातळी.",
                "tip": "दररोज सकाळी कोवळ्या उन्हात बसा आणि डॉक्टरांचा सल्ला घ्या."
            }
        },
        "hemoglobin": {
            "name": "Hemoglobin (Hb)",
            "loinc": "718-7",
            "patterns": [r"(?i)\b(?:hemoglobin|hb|hgb)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "g/dL",
            "normal_range": (12.0, 17.5),
            "panic_limits": (7.0, 20.0),
            "guideline": "WHO Haemoglobin Concentrations for the Diagnosis of Anaemia",
            "en": {
                "what": "Iron-rich protein in red blood cells that transports oxygen.",
                "low": "Anemia. Results in reduced oxygenation, dyspnea, and exhaustion.",
                "high": "High hemoglobin. Maintain optimal hydration.",
                "tip": "Increase consumption of iron-dense foods like spinach, beetroot, and jaggery."
            },
            "hi": {
                "what": "खून में ऑक्सीजन ले जाने वाला मुख्य प्रोटीन।",
                "low": "एनीमिया (खून की कमी)। सांस फूलना और सुस्ती महसूस होना।",
                "high": "हीमोग्लोबिन अधिक है। पर्याप्त पानी पिएं।",
                "tip": "पालक, अनार, चुकंदर और गुड़ का सेवन करें।"
            },
            "mr": {
                "what": "रक्तात ऑक्सिजन वाहून नेणारे मुख्य घटक.",
                "low": "अ‍ॅनिमिया (रक्ताची कमतरता). यामुळे थकवा जाणवतो.",
                "high": "प्रमाण जास्त आहे. भरपूर पाणी प्या.",
                "tip": "पालक, बीट, डाळिंब आणि गूळ आहारात ठेवा."
            }
        },
        "serum_creatinine": {
            "name": "Serum Creatinine",
            "loinc": "2160-0",
            "patterns": [r"(?i)\b(?:creatinine|serum\s*creatinine|s\.?\s*creatinine)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (0.6, 1.2),
            "panic_limits": (0.3, 3.0),
            "guideline": "KDIGO Clinical Practice Guideline for Acute Kidney Injury & CKD",
            "en": {
                "what": "Metabolic breakdown marker reflecting renal glomerular filtration rate.",
                "low": "Low baseline muscle mass indicator.",
                "high": "Renal strain. Kidneys are filtering metabolic waste at reduced clearance.",
                "tip": "Maintain hydration (2.5 to 3 L/day) and review nephrotoxic medications."
            },
            "hi": {
                "what": "यह दिखाता है कि आपकी किडनी खून को कितना साफ कर रही है।",
                "low": "मांसपेशियों के कम भार का संकेत।",
                "high": "किडनी पर दबाव। पानी की मात्रा बढ़ाएं और नमक नियंत्रित करें।",
                "tip": "२.५ से ३ लीटर पानी पिएं और डॉक्टर से दवाओं की समीक्षा कराएं।"
            },
            "mr": {
                "what": "किडनी रक्त किती स्वच्छ गाळत आहे हे दर्शवणारा घटक.",
                "low": "कमी स्नायू वस्तुमानाचे लक्षण.",
                "high": "किडनीवर ताण दर्शवते. पाण्याचे प्रमाण वाढवा.",
                "tip": "भरपूर पाणी प्या आणि डॉक्टरांच्या सल्ल्याने औषधे तपासा."
            }
        }
    }

    @classmethod
    def extract_structured_biomarkers(cls, text: str) -> Dict[str, float]:
        extracted = {}
        for key, config in cls.MARKER_REGISTRY.items():
            for pat in config["patterns"]:
                match = re.search(pat, text)
                if match:
                    try:
                        extracted[key] = float(match.group(1))
                        break
                    except ValueError:
                        continue
        return extracted

    @classmethod
    def extract_clinical_treatments(cls, text: str, hospital: str, date_str: str) -> List[Dict[str, Any]]:
        treatments = []
        cleaned = text.replace("\n", " ")

        patterns = [
            (r"(?i)(?:prescribed|started on|placed on|rx|medication|given|tablet|tab|cap|capsule|injection|inj|dose)\s*:?\s*([A-Za-z0-9\s\-]+(?:\d+\s*(?:mg|mcg|iu|ml|g|gm))?)", "Medication Protocol", "Prescription Therapy"),
            (r"(?i)(?:surgery|procedure|underwent|performed|operated|repair|resection|arthroscopy|biopsy|endoscopy|angioplasty|appendectomy|cesarean|stent)\s*:?\s*([A-Za-z0-9\s\-]+)", "Surgical Procedure", "Surgery / Intervention"),
            (r"(?i)(?:physiotherapy|rehabilitation|physical therapy|exercise therapy|mobilization|traction|splinting)\s*:?\s*([A-Za-z0-9\s\-]+)", "Physical Therapy", "Rehabilitation"),
            (r"(?i)(?:dietary regimen|diet plan|advised to|lifestyle modification|weight management|cardiac diet|diabetic diet)\s*:?\s*([A-Za-z0-9\s\-]+)", "Lifestyle Modification", "Dietary Protocol")
        ]

        found_entities = set()
        for pat, category, action_type in patterns:
            for match in re.finditer(pat, cleaned):
                raw_match = match.group(1).strip()
                raw_match = re.split(r'[,.;:\n]', raw_match)[0].strip()
                if len(raw_match) > 3 and len(raw_match) < 60 and raw_match.lower() not in found_entities:
                    found_entities.add(raw_match.lower())
                    treatments.append({
                        "date": date_str,
                        "hospital": hospital,
                        "procedure": raw_match.title(),
                        "category": category,
                        "action_type": action_type,
                        "note": f"Documented clinical intervention: {raw_match} recorded at {hospital}."
                    })

        if not treatments:
            treatments.append({
                "date": date_str,
                "hospital": hospital,
                "procedure": "Clinical Evaluation & Vital Profiling",
                "category": "Outpatient Care",
                "action_type": "Diagnostic Consultation",
                "note": f"Comprehensive diagnostic assessment conducted at {hospital}."
            })

        return treatments
