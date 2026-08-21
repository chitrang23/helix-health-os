import re
import io
from typing import Dict, Any, List, Optional
from datetime import datetime
from pypdf import PdfReader
from PIL import Image

class OCREngine:
    @staticmethod
    def parse_pdf_bytes(file_bytes: bytes) -> str:
        extracted_text = []
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    extracted_text.append(t)
        except Exception:
            pass
        return "\n".join(extracted_text)

    @staticmethod
    def parse_image_bytes(file_bytes: bytes) -> str:
        try:
            import pytesseract
            image = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(image)
        except Exception:
            return ""

    MARKER_REGISTRY = {
        "fasting_glucose": {
            "name": {
                "en": "Fasting Blood Sugar (Morning Fuel)",
                "hi": "खाली पेट शुगर (सुबह का ग्लूकोज स्तर)",
                "mr": "उपाशीपोटी साखर (सकाळची साखरेची पातळी)"
            },
            "loinc": "1558-6",
            "specialist": {
                "en": "Diabetes Specialist (Endocrinologist)",
                "hi": "मधुमेह विशेषज्ञ (एंडोक्रिनोलॉजिस्ट)",
                "mr": "मधुमेह तज्ज्ञ (एंडोक्राइनोलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:fasting\s*glucose|fbs|fasting\s*sugar|blood\s*sugar\s*fasting|glucose\s*fasting)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (70.0, 100.0),
            "panic_limits": (55.0, 250.0),
            "guideline": {
                "en": "ADA & ICMR Diabetes Guidelines",
                "hi": "एडीए और आईसीएमआर मधुमेह दिशानिर्देश",
                "mr": "एडीए आणि आयसीएमआर मधुमेह मार्गदर्शक तत्त्वे"
            },
            "what": {
                "en": "Morning Fuel Level: Checks how much sugar is in your blood before breakfast.",
                "hi": "सुबह का ईंधन स्तर: नाश्ते से पहले खून में मौजूद शुगर की मात्रा जांचता है।",
                "mr": "सकाळची इंधन पातळी: नाश्त्यापूर्वी रक्तात किती साखर आहे हे तपासते."
            },
            "low": {
                "en": "Very Low Sugar (Hypoglycemia). Can cause dizziness and shaking.",
                "hi": "शुगर बहुत कम है। चक्कर और हाथ कांपने की समस्या हो सकती है।",
                "mr": "साखर खूप कमी आहे. चक्कर आणि थरथर जाणवू शकते."
            },
            "high": {
                "en": "High Sugar Level. Means your body is having trouble processing carbohydrates.",
                "hi": "शुगर का स्तर अधिक है। शरीर में इंसुलिन का प्रभाव कम हो रहा है।",
                "mr": "साखर जास्त आहे. शरीराला अन्नातील साखर पचवणे कठीण जात आहे."
            },
            "tip": {
                "en": "Take doctor-prescribed medicine on time and take a 15-minute walk after meals.",
                "hi": "डॉक्टर द्वारा दी गई दवा समय पर लें और भोजन के बाद १५ मिनट टहलें।",
                "mr": "डॉक्टरांचे औषध वेळेवर घ्या आणि जेवणानंतर १५ मिनिटे चाला."
            }
        },
        "hba1c": {
            "name": {
                "en": "HbA1c (3-Month Sugar Memory)",
                "hi": "एचबीए1सी (३ महीने का औसत शुगर रिपोर्ट कार्ड)",
                "mr": "HbA1c (३ महिन्यांचे साखरेचे रिपोर्ट कार्ड)"
            },
            "loinc": "4548-4",
            "specialist": {
                "en": "Diabetes Specialist (Endocrinologist)",
                "hi": "मधुमेह विशेषज्ञ (एंडोक्रिनोलॉजिस्ट)",
                "mr": "मधुमेह तज्ज्ञ (एंडोक्राइनोलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:hba1c|glycated\s*hemoglobin|glycosylated\s*hemoglobin)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "%",
            "normal_range": (4.0, 5.6),
            "panic_limits": (3.5, 10.0),
            "guideline": {
                "en": "WHO Diagnostic Standards",
                "hi": "डब्ल्यूएचओ नैदानिक मानक",
                "mr": "डब्ल्यूएचओ निदान मानके"
            },
            "what": {
                "en": "3-Month Sugar Memory: Average report card of your sugar over the last 90 days.",
                "hi": "३ महीने का रिपोर्ट कार्ड: पिछले ९० दिनों में खून में शुगर का औसत स्तर।",
                "mr": "३ महिन्यांचे रिपोर्ट कार्ड: मागील ९० दिवसांतील साखरेची खरी सरासरी."
            },
            "low": {
                "en": "Abnormally low average sugar.",
                "hi": "औसत से बहुत कम शुगर स्तर।",
                "mr": "सरासरीपेक्षा खूप कमी साखर."
            },
            "high": {
                "en": "Elevated 3-month sugar. Indicates long-term insulin resistance.",
                "hi": "पिछले ९० दिनों का शुगर बढ़ा हुआ है। नियमित दवा और परहेज जरूरी है।",
                "mr": "मागील ९० दिवसांतील साखर वाढलेली आहे. नियमित औषधोपचार आवश्यक आहे."
            },
            "tip": {
                "en": "Strictly take your diabetes medications and add sprouted legumes and green salads.",
                "hi": "दवाएं समय पर लें और अंकुरित अनाज व हरी सलाद का सेवन बढ़ाएं।",
                "mr": "औषधे वेळेवर घ्या आणि आहारात मोड आलेली कडधान्ये व सॅलड वाढवा."
            }
        },
        "ldl_cholesterol": {
            "name": {
                "en": "LDL Cholesterol (Bad Fat / Pipe Clogger)",
                "hi": "खराब कोलेस्ट्रॉल (नसों में रुकावट करने वाली चर्बी)",
                "mr": "वाईट कोलेस्टेरॉल (वाहिन्या अडवणारी चरबी)"
            },
            "loinc": "13457-7",
            "specialist": {
                "en": "Heart Specialist (Cardiologist)",
                "hi": "हृदय रोग विशेषज्ञ (कार्डियोलॉजिस्ट)",
                "mr": "हृदयरोग तज्ज्ञ (कार्डिओलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:ldl|ldl\s*cholesterol|low\s*density\s*lipoprotein)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (50.0, 100.0),
            "panic_limits": (30.0, 190.0),
            "guideline": {
                "en": "AHA Heart Health Guidelines",
                "hi": "एएचए हृदय स्वास्थ्य मानक",
                "mr": "एएचए हृदय आरोग्य मानक"
            },
            "what": {
                "en": "Clogged Pipe Builder: Bad fat particles that can stick inside your blood vessels.",
                "hi": "नसों में रुकावट: यह खराब चर्बी खून की नलियों में चिपक कर रुकावट पैदा कर सकती है।",
                "mr": "वाहिन्यांमध्ये अडथळा: ही वाईट चरबी रक्तवाहिन्यांमध्ये साचून अडथळा आणू शकते."
            },
            "low": {
                "en": "Optimal clean lipid profile.",
                "hi": "सुरक्षित एवं उत्तम स्तर।",
                "mr": "उत्तम आणि सुरक्षित पातळी."
            },
            "high": {
                "en": "High bad cholesterol. Increases the strain on your heart.",
                "hi": "खराब कोलेस्ट्रॉल अधिक है। हृदय पर दबाव बढ़ सकता है।",
                "mr": "कोलेस्टेरॉल जास्त आहे. हृदयावर ताण येऊ शकतो."
            },
            "tip": {
                "en": "Take cholesterol medication if prescribed; avoid fried foods and palm oil completely.",
                "hi": "डॉक्टर की दवाएं नियमित लें और तली-भुनी चीजें व पाम ऑयल पूरी तरह बंद करें।",
                "mr": "डॉक्टरांनी दिलेली औषधे घ्या आणि तळलेले पदार्थ पूर्णपणे टाळा."
            }
        },
        "vitamin_d": {
            "name": {
                "en": "Vitamin D (Bone Strength & Mood Vitamin)",
                "hi": "विटामिन डी (हड्डियों की मजबूती एवं धूप विटामिन)",
                "mr": "व्हिटॅमिन डी (हाडांची ताकद व उन्हाचे जीवनसत्त्व)"
            },
            "loinc": "62292-8",
            "specialist": {
                "en": "Orthopedic / Bone Specialist",
                "hi": "हड्डी रोग विशेषज्ञ (ऑर्थोपेडिक)",
                "mr": "हाडांचे तज्ज्ञ (ऑर्थोपेडिक)"
            },
            "patterns": [r"(?i)\b(?:vitamin\s*d|25-oh|vit\s*d3?|25-hydroxy\s*vitamin\s*d)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "ng/mL",
            "normal_range": (30.0, 100.0),
            "panic_limits": (10.0, 150.0),
            "guideline": {
                "en": "Endocrine Clinical Standards",
                "hi": "एंडोक्राइन क्लिनिकल मानक",
                "mr": "एंडोक्राइन क्लिनिकल मानक"
            },
            "what": {
                "en": "Sunshine Vitamin: Essential for bone mineral density, immunity, and low fatigue.",
                "hi": "धूप का विटामिन: हड्डियों की मजबूती, इम्युनिटी और फुर्ती के लिए जरूरी।",
                "mr": "उन्हाचे जीवनसत्त्व: हाडांची ताकद, प्रतिकारशक्ती आणि उत्साह टिकवण्यासाठी आवश्यक."
            },
            "low": {
                "en": "Deficiency. Can cause body fatigue, lower back aches, and low mood.",
                "hi": "विटामिन डी की कमी। कमर दर्द, बदन दर्द और थकान का कारण।",
                "mr": "कमतरता. कंबरदुखी, अंगदुखी आणि सतत थकवा जाणवू शकतो."
            },
            "high": {
                "en": "Optimal sunshine level.",
                "hi": "उत्तम एवं पर्याप्त स्तर।",
                "mr": "उत्तम व पुरेशी पातळी."
            },
            "tip": {
                "en": "Complete prescribed weekly D3 supplement course and sit in morning sunlight for 15 mins.",
                "hi": "साप्ताहिक डी3 सप्लीमेंट पूरा करें और सुबह १५ मिनट धूप में बैठें।",
                "mr": "साप्ताहिक डी3 औषध पूर्ण करा आणि सकाळी १५ मिनिटे कोवळ्या उन्हात बसा."
            }
        },
        "hemoglobin": {
            "name": {
                "en": "Hemoglobin (Oxygen Delivery Trucks)",
                "hi": "हीमोग्लोबिन (ऑक्सीजन पहुंचाने वाले रक्त कण)",
                "mr": "हिमोग्लोबिन (ऑक्सिजन वाहून नेणारे रक्तकण)"
            },
            "loinc": "718-7",
            "specialist": {
                "en": "Hematologist / Blood Specialist",
                "hi": "रक्त रोग विशेषज्ञ (हेमेटोलॉजिस्ट)",
                "mr": "रक्तविकार तज्ज्ञ (हेमॅटोलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:hemoglobin|hb|hgb)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "g/dL",
            "normal_range": (12.0, 17.5),
            "panic_limits": (7.0, 20.0),
            "guideline": {
                "en": "WHO Anaemia Diagnostic Guidelines",
                "hi": "डब्ल्यूएचओ एनीमिया मानक",
                "mr": "डब्ल्यूएचओ अ‍ॅनिमिया मार्गदर्शक तत्त्वे"
            },
            "what": {
                "en": "Oxygen Trucks: Red blood cells carrying fresh oxygen to all your muscles and brain.",
                "hi": "ऑक्सीजन वाहक: खून के लाल कण जो पूरे शरीर और मस्तिष्क तक ऑक्सीजन पहुंचाते हैं।",
                "mr": "ऑक्सिजन वाहक: रक्तातील लाल पेशी ज्या संपूर्ण शरीराला ऑक्सिजन पुरवतात."
            },
            "low": {
                "en": "Anemia (Low Blood). Causes breathlessness on walking and heavy fatigue.",
                "hi": "खून की कमी (एनीमिया)। चलने पर सांस फूलना और कमजोरी होना।",
                "mr": "रक्ताची कमतरता (अ‍ॅनिमिया). चालताना धाप लागणे आणि तीव्र थकवा."
            },
            "high": {
                "en": "High concentration. Drink plenty of water throughout the day.",
                "hi": "हीमोग्लोबिन अधिक है। दिनभर पर्याप्त पानी पिएं।",
                "mr": "प्रमाण जास्त आहे. दिवसभरात भरपूर पाणी प्या."
            },
            "tip": {
                "en": "Take iron/folate supplements with meals; eat spinach, pomegranate, beetroot, and jaggery.",
                "hi": "आयरन की दवाएं समय पर लें और पालक, अनार, चुकंदर व गुड़ खाएं।",
                "mr": "लोहाची औषधे नियमित घ्या आणि पालक, डाळिंब, बीट, गूळ आहारात ठेवा."
            }
        },
        "serum_creatinine": {
            "name": {
                "en": "Serum Creatinine (Kidney Filter Meter)",
                "hi": "सीरम क्रिएटिनिन (किडनी फिल्टर क्षमता जांच)",
                "mr": "सिरम क्रिएटिनिन (किडनीची गाळण क्षमता)"
            },
            "loinc": "2160-0",
            "specialist": {
                "en": "Kidney Specialist (Nephrologist)",
                "hi": "किडनी रोग विशेषज्ञ (नेफ्रोलॉजिस्ट)",
                "mr": "किडनी तज्ज्ञ (नेफ्रोलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:creatinine|serum\s*creatinine|s\.?\s*creatinine)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (0.6, 1.2),
            "panic_limits": (0.3, 3.0),
            "guideline": {
                "en": "KDIGO Kidney Health Standards",
                "hi": "केडीआईजीओ किडनी स्वास्थ्य मानक",
                "mr": "केडीआयजीओ किडनी आरोग्य मानक"
            },
            "what": {
                "en": "Kidney Filter Meter: Measures how cleanly and fast your kidneys filter out waste.",
                "hi": "किडनी फिल्टर जांच: यह बताता है कि आपकी किडनियां खून को कितना साफ कर रही हैं।",
                "mr": "किडनी फिल्टर तपासणी: किडन्या रक्त किती स्वच्छ गाळत आहेत हे मोजणारा घटक."
            },
            "low": {
                "en": "Normal or low muscle mass indicator.",
                "hi": "मांसपेशियों के कम भार का सामान्य संकेत।",
                "mr": "कमी स्नायू वस्तुमानाचे सामान्य लक्षण."
            },
            "high": {
                "en": "Kidney Filter Slowdown. Waste is building up; requires kidney doctor review.",
                "hi": "किडनी पर दबाव। दवाएं बदलने और डॉक्टर से समीक्षा कराने की जरूरत है।",
                "mr": "किडनीवर ताण. औषधे तपासण्याची आणि तज्ज्ञांचा सल्ला घेण्याची गरज आहे."
            },
            "tip": {
                "en": "Show your medicines to a kidney specialist; drink 2.5 to 3 liters of water daily.",
                "hi": "किडनी विशेषज्ञ से दवाओं की जांच कराएं और रोजाना २.५ से ३ लीटर पानी पिएं।",
                "mr": "किडनी तज्ज्ञांना औषधे दाखवा आणि दररोज २.५ ते ३ लिटर पाणी प्या."
            }
        },
        "sgpt_alt": {
            "name": {
                "en": "SGPT / ALT (Liver Strain Meter)",
                "hi": "एसजीपीटी / एएलटी (लिवर पर दबाव सूचक)",
                "mr": "SGPT / ALT (यकृतावरील ताण दर्शक)"
            },
            "loinc": "1742-6",
            "specialist": {
                "en": "Liver Specialist (Gastroenterologist)",
                "hi": "लिवर विशेषज्ञ (गैस्ट्रोएंटेरोलॉजिस्ट)",
                "mr": "यकृत तज्ज्ञ (गॅस्ट्रोएन्टेरोलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:sgpt|alt|alanine\s*aminotransferase|alanine\s*transaminase)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "U/L",
            "normal_range": (10.0, 45.0),
            "panic_limits": (5.0, 300.0),
            "guideline": {
                "en": "ACG Liver Clinical Guidelines",
                "hi": "एसीजी लिवर क्लिनिकल मानक",
                "mr": "एसीजी यकृत क्लिनिकल मानक"
            },
            "what": {
                "en": "Liver Strain Meter: Enzyme that leaks into the blood when liver cells are overworked.",
                "hi": "लिवर दबाव सूचक: जब लिवर पर चिकनाई या दवाओं का बोझ बढ़ता है, तब यह एंजाइम खून में बढ़ता है।",
                "mr": "यकृत ताण दर्शक: तेलकट खाणे किंवा अतिरिक्त ताणामुळे यकृताच्या पेशींवर भार आल्यास हे वाढते."
            },
            "low": {
                "en": "Optimal and healthy liver function.",
                "hi": "लिवर पूरी तरह स्वस्थ और सामान्य है।",
                "mr": "यकृत पूर्णपणे निरोगी आहे."
            },
            "high": {
                "en": "Elevated liver stress. Often caused by fatty liver, alcohol, or heavy medications.",
                "hi": "लिवर पर सूजन या फैटी लिवर का संकेत। तली-भुनी चीजें तुरंत बंद करें।",
                "mr": "यकृतावर सूज किंवा फॅटी लिव्हरचे लक्षण. तेलकट पदार्थ त्वरित टाळा."
            },
            "tip": {
                "en": "Completely stop alcohol, reduce deep-fried oily foods, and consume fresh green vegetables.",
                "hi": "शराब और तली-भुनी चीजें पूरी तरह बंद करें, हरी पत्तेदार सब्जियां खाएं।",
                "mr": "दारू आणि तेलकट अन्न पूर्णपणे बंद करा, हिरव्या पालेभाज्या खा."
            }
        },
        "serum_uric_acid": {
            "name": {
                "en": "Serum Uric Acid (Joint Crystal Maker)",
                "hi": "यूरिक एसिड (जोड़ों में दर्द व पथरी बनाने वाला तत्व)",
                "mr": "युरिक अ‍ॅसिड (सांधेदुखी व खडे तयार करणारा घटक)"
            },
            "loinc": "3084-1",
            "specialist": {
                "en": "Joint & Arthritis Specialist (Rheumatologist)",
                "hi": "जोड़ रोग विशेषज्ञ (रूमेटोलॉजिस्ट)",
                "mr": "सांधेदुखी तज्ज्ञ (रुमॅटोलॉजिस्ट)"
            },
            "patterns": [r"(?i)\b(?:uric\s*acid|serum\s*uric\s*acid)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
            "unit": "mg/dL",
            "normal_range": (3.5, 7.2),
            "panic_limits": (2.0, 12.0),
            "guideline": {
                "en": "ACR Gout Management Standards",
                "hi": "एसीआर गाउट प्रबंधन मानक",
                "mr": "एसीआर गाऊट व्यवस्थापन मानके"
            },
            "what": {
                "en": "Joint Crystal Maker: Waste chemical that forms needle-sharp crystals in toes and knees.",
                "hi": "जोड़ों के क्रिस्टल: खून में अधिक होने पर यह पैरों के अंगूठे और घुटनों में तेज दर्द पैदा करता है।",
                "mr": "सांध्यातील खडे: रक्तात वाढल्यास पायाच्या अंगठ्यात आणि गुडघ्यांत तीव्र वेदना होतात."
            },
            "low": {
                "en": "Normal and clear uric levels.",
                "hi": "सुरक्षित एवं सामान्य स्तर।",
                "mr": "सुरक्षित व सामान्य पातळी."
            },
            "high": {
                "en": "High uric acid. High risk of throbbing joint pain (gout) and kidney stones.",
                "hi": "यूरिक एसिड बढ़ा हुआ है। जोड़ों में दर्द और पथरी का खतरा बढ़ सकता है।",
                "mr": "युरिक अ‍ॅसिड जास्त आहे. सांधेदुखी आणि मुतखड्याचा धोका वाढू शकतो."
            },
            "tip": {
                "en": "Drink 3 liters of water daily; limit high-purine foods (paneer, mushrooms, spinach, pulses).",
                "hi": "रोजाना ३ लीटर पानी पिएं और पनीर, मशरूम, पालक व दालों की मात्रा नियंत्रित करें।",
                "mr": "दररोज ३ लिटर पाणी प्या आणि पनीर, मशरूम, पालक, डाळींचे प्रमाण मर्यादित ठेवा."
            }
        }
    }

    @classmethod
    def extract_structured_biomarkers(cls, text: str) -> Dict[str, Any]:
        extracted = {}
        for key, config in cls.MARKER_REGISTRY.items():
            for pat in config["patterns"]:
                match = re.search(pat, text)
                if match:
                    try:
                        val = float(match.group(1))
                        extracted[key] = {
                            "value": val,
                            "name": config["name"],
                            "unit": config["unit"],
                            "normal_range": config["normal_range"],
                            "panic_limits": config.get("panic_limits", (config["normal_range"][0]*0.5, config["normal_range"][1]*2.0)),
                            "loinc": config["loinc"],
                            "specialist": config["specialist"],
                            "guideline": config["guideline"],
                            "what": config["what"],
                            "low": config.get("low", {}),
                            "high": config.get("high", {}),
                            "tip": config["tip"]
                        }
                        break
                    except ValueError:
                        continue

        # Generic line fallback
        lines = text.split("\n")
        generic_pattern = re.compile(
            r"^\s*([A-Za-z0-9\s\(\)\-\/\+]{3,35})\s*[:\t]\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z\/\%μµ\^0-9]+)?(?:\s*(?:[\(\[]?\s*([0-9]+(?:\.[0-9]+)?)\s*[-–—to]+\s*([0-9]+(?:\.[0-9]+)?)\s*[\)\]]?))?",
            re.IGNORECASE
        )

        for line in lines:
            line_clean = line.strip()
            if not line_clean or len(line_clean) < 5:
                continue
            gm = generic_pattern.search(line_clean)
            if gm:
                raw_name = gm.group(1).strip()
                raw_val = gm.group(2)
                raw_unit = gm.group(3) or ""
                ref_min = gm.group(4)
                ref_max = gm.group(5)

                slug = re.sub(r'[^a-zA-Z0-9]', '_', raw_name.lower()).strip('_')
                if slug in extracted or len(slug) < 3 or slug in ["page", "date", "age", "sex", "patient_name"]:
                    continue

                try:
                    num_val = float(raw_val)
                    n_min = float(ref_min) if ref_min else 0.0
                    n_max = float(ref_max) if ref_max else max(num_val * 1.5, 100.0)

                    extracted[slug] = {
                        "value": num_val,
                        "name": {"en": raw_name.title(), "hi": raw_name.title(), "mr": raw_name.title()},
                        "unit": raw_unit,
                        "normal_range": (n_min, n_max),
                        "panic_limits": (n_min * 0.5, n_max * 1.8),
                        "loinc": "Clinical Test",
                        "specialist": {"en": "Consulting Doctor", "hi": "परामर्श चिकित्सक", "mr": "सल्लागार डॉक्टर"},
                        "guideline": {"en": "Standard Clinical Reference", "hi": "मानक क्लिनिकल संदर्भ", "mr": "मानक वैद्यकीय संदर्भ"},
                        "what": {
                            "en": f"Diagnostic measurement for {raw_name.title()}.",
                            "hi": f"{raw_name.title()} की जांच मान।",
                            "mr": f"{raw_name.title()} ची तपासणी पातळी."
                        },
                        "low": {
                            "en": "Below normal reference range.",
                            "hi": "सामान्य सीमा से कम है।",
                            "mr": "सामान्य मर्यादेपेक्षा कमी आहे."
                        },
                        "high": {
                            "en": "Above normal reference range.",
                            "hi": "सामान्य सीमा से अधिक है।",
                            "mr": "सामान्य मर्यादेपेक्षा जास्त आहे."
                        },
                        "tip": {
                            "en": "Discuss this specific test result with your consulting doctor.",
                            "hi": "इस जांच परिणाम के बारे में अपने डॉक्टर से चर्चा करें।",
                            "mr": "या तपासणी निकालाबाबत डॉक्टरांचा सल्ला घ्या."
                        }
                    }
                except ValueError:
                    continue

        return extracted

    @classmethod
    def extract_report_metadata(cls, text: str) -> Dict[str, Any]:
        hosp_match = re.search(r"(?i)\b([A-Za-z\s]+(?:Hospital|Healthcare|Diagnostic|Diagnostics|Lab|Labs|Clinic|Pathology|Institute|Medical Center))\b", text)
        hospital_name = hosp_match.group(1).strip() if hosp_match else "Diagnostic Center"

        date_patterns = [
            r"\b(\d{4}-\d{2}-\d{2})\b",
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b"
        ]
        extracted_date = None
        for dp in date_patterns:
            dm = re.search(dp, text, re.IGNORECASE)
            if dm:
                raw_d = dm.group(1)
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%d/%m/%y"):
                    try:
                        extracted_date = datetime.strptime(raw_d, fmt)
                        break
                    except ValueError:
                        pass
                if extracted_date:
                    break

        if not extracted_date:
            extracted_date = datetime.now()

        age_match = re.search(r"(?i)\b(?:Age|Age/Gender|Y/O|Years)\s*[:/-]?\s*([0-9]{1,2})\b", text)
        age = int(age_match.group(1)) if age_match else None

        gender_match = re.search(r"(?i)\b(?:Gender|Sex)\s*[:/-]?\s*(Male|Female|Other|M|F)\b", text)
        gender = None
        if gender_match:
            g_raw = gender_match.group(1).upper()
            gender = "Male" if g_raw in ["M", "MALE"] else "Female" if g_raw in ["F", "FEMALE"] else "Other"

        name_match = re.search(r"(?i)\b(?:Patient\s*Name|Name|Pt\.?\s*Name)\s*[:.]?\s*(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*([A-Za-z\s]{3,30})\b", text)
        patient_name = name_match.group(1).strip() if name_match else None

        return {
            "hospital_name": hospital_name.title(),
            "record_date": extracted_date,
            "age": age,
            "gender": gender,
            "patient_name": patient_name.title() if patient_name else None
        }

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
                if 3 < len(raw_match) < 60 and raw_match.lower() not in found_entities:
                    found_entities.add(raw_match.lower())
                    treatments.append({
                        "date": date_str,
                        "hospital": hospital,
                        "procedure": raw_match.title(),
                        "category": category,
                        "action_type": action_type,
                        "note": f"Clinical intervention: {raw_match} recorded at {hospital}."
                    })

        if not treatments:
            treatments.append({
                "date": date_str,
                "hospital": hospital,
                "procedure": "Clinical Evaluation & Diagnostic Profiling",
                "category": "Outpatient Care",
                "action_type": "Diagnostic Consultation",
                "note": f"Diagnostic health evaluation conducted at {hospital}."
            })

        return treatments
