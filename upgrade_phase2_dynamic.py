# -*- coding: utf-8 -*-
import os

seed_data_code = '''# -*- coding: utf-8 -*-
"""
Dynamic initial seed knowledge for Helix Enterprise Health OS.
Stored in SQLite/Postgres DB on first run; manageable via Admin API.
"""

SEED_BIOMARKERS = [
    {
        "key": "fasting_glucose",
        "name": "Fasting Blood Glucose",
        "loinc": "1558-6",
        "unit": "mg/dL",
        "patterns": [r"(?i)\b(?:fasting\s*glucose|fbs|fasting\s*sugar|blood\s*sugar\s*fasting|glucose\s*fasting)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 70.0, "normal_high": 100.0,
        "panic_low": 55.0, "panic_high": 250.0,
        "guideline": "ADA Standards of Care 2026 / ICMR Guidelines for Glycemic Management",
        "scale_bucket": "normal",
        "translations": {
            "en": {"what": "Morning blood sugar before eating breakfast.",
                   "low": "Hypoglycemia. Can cause tremors, cold sweats, and dizziness.",
                   "high": "Hyperglycemia / Prediabetes zone. Indicates impaired insulin response.",
                   "tip": "Engage in a 15-minute post-meal brisk walk and reduce high-glycemic carbohydrates."},
            "hi": {"what": "सुबह खाली पेट खून में ग्लूकोज (शर्करा) का स्तर।",
                   "low": "हाइपोग्लाइसीमिया। चक्कर, पसीना और कंपकंपी हो सकती है।",
                   "high": "प्रीडायबिटीज / बढ़ा हुआ शुगर स्तर। इंसुलिन प्रतिरोध का संकेत।",
                   "tip": "भोजन के बाद १५ मिनट टहलें और मीठा व मैदा कम करें।"},
            "mr": {"what": "सकाळी उपाशीपोटी रक्तातील साखरेचे प्रमाण.",
                   "low": "रक्तातील साखर खूप कमी झाली आहे. चक्कर येऊ शकते.",
                   "high": "रक्तातील साखर वाढलेली आहे. मधुमेहाचा पूर्वसंकेत.",
                   "tip": "जेवणानंतर १५ मिनिटे चाला आणि गोड पदार्थ टाळा."},
        },
        "symptom_rules": {
            "keywords": ["sugar", "dizzy", "dizziness", "tired", "fatigue", "thirst", "hungry", "sweating", "headache", "urination", "weakness"],
            "high": {"en": "Your high blood sugar prevents glucose from entering cells efficiently, causing post-meal fatigue, frequent thirst, and energy crashes.",
                     "hi": "खून में अधिक शुगर कोशिकाओं तक ऊर्जा नहीं पहुंचने देती, जिससे खाने के बाद थकान, ज्यादा प्यास और कमजोरी महसूस होती है।",
                     "mr": "रक्तातील वाढलेली साखर पेशींना ऊर्जा मिळण्यात अडथळा आणते, ज्यामुळे जेवणानंतर थकवा, वारंवार तहान आणि अशक्तपणा जाणवतो."},
            "low": {"en": "Low blood sugar causes your brain to lack immediate fuel, leading directly to dizziness, shakiness, and sudden weakness.",
                    "hi": "शुगर कम होने से मस्तिष्क को तुरंत ऊर्जा नहीं मिलती, जिससे चक्कर आना, हाथ कांपना और कमजोरी होती है।",
                    "mr": "साखर कमी झाल्यामुळे मेंदूला पुरेशी ऊर्जा मिळत नाही, ज्यामुळे चक्कर येणे आणि अचानक अशक्तपणा जाणवतो."},
        },
    },
    {
        "key": "hba1c",
        "name": "Glycated Hemoglobin (HbA1c)",
        "loinc": "4548-4",
        "unit": "%",
        "patterns": [r"(?i)\b(?:hba1c|glycated\s*hemoglobin|glycosylated\s*hemoglobin)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 4.0, "normal_high": 5.6,
        "panic_low": 3.5, "panic_high": 10.0,
        "guideline": "WHO Diagnostic Thresholds for Glycated Hemoglobin / ADA 2026",
        "scale_bucket": "small",
        "translations": {
            "en": {"what": "90-day biological average of circulating blood sugar.",
                   "low": "Abnormally low average glycemic state.",
                   "high": "Elevated 3-month sugar. Consistent with insulin resistance.",
                   "tip": "Incorporate sprouted legumes, whole grains, and leafy vegetables."},
            "hi": {"what": "पिछले ३ महीनों के ब्लड शुगर का औसत स्तर।",
                   "low": "सामान्य से अत्यधिक कम औसत शुगर।",
                   "high": "पिछले ९० दिनों का शुगर बढ़ा हुआ है।",
                   "tip": "अंकुरित मूंग, सलाद और रेशेदार अनाज खाएं।"},
            "mr": {"what": "मागील ३ महिन्यांतील साखरेची सरासरी पातळी.",
                   "low": "सरासरी साखर अत्यंत कमी आहे.",
                   "high": "मागील ९० दिवसांतील साखर वाढलेली आहे.",
                   "tip": "मोड आलेली कडधान्ये आणि पालेभाज्या आहारात वाढवा."},
        },
        "symptom_rules": {
            "keywords": ["tired", "fatigue", "weakness", "blurry", "vision", "healing", "tingling", "feet", "numbness"],
            "high": {"en": "Elevated 3-month sugar indicates long-term insulin resistance, which directly explains chronic lethargy and slow muscle recovery.",
                     "hi": "पिछले ९० दिनों का बढ़ा हुआ शुगर स्तर शरीर में लगातार सुस्ती और मांसपेशियों में कमजोरी का मुख्य कारण है।",
                     "mr": "मागील ३ महिन्यांतील वाढलेली सरासरी साखर शरीरातील सततचा आळस आणि स्नायूंमधील अशक्तपणा स्पष्ट करते."},
        },
    },
    {
        "key": "ldl_cholesterol",
        "name": "LDL Cholesterol",
        "loinc": "13457-7",
        "unit": "mg/dL",
        "patterns": [r"(?i)\b(?:ldl|ldl\s*cholesterol|low\s*density\s*lipoprotein)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 50.0, "normal_high": 100.0,
        "panic_low": 30.0, "panic_high": 190.0,
        "guideline": "AHA/ACC Clinical Practice Guidelines on Management of Blood Cholesterol",
        "scale_bucket": "normal",
        "translations": {
            "en": {"what": "Atherogenic lipid particles that can deposit in arterial walls.",
                   "low": "Optimal low atherogenic lipid profile.",
                   "high": "Elevated bad cholesterol. Increases vascular plaque risk.",
                   "tip": "Add 20g ground flaxseed daily and avoid trans-fats and palm oil."},
            "hi": {"what": "खराब कोलेस्ट्रॉल जो रक्त नलिकाओं में वसा जमा कर सकता है।",
                   "low": "उत्तम एवं सुरक्षित स्तर।",
                   "high": "कोलेस्ट्रॉल अधिक होने से हृदय पर दबाव बढ़ता है।",
                   "tip": "रोजाना अलसी (Flaxseeds) लें और तली-भुनी चीजों से बचें।"},
            "mr": {"what": "वाईट कोलेस्टेरॉल जे रक्तवाहिन्यांमध्ये अडथळा आणू शकते.",
                   "low": "सुरक्षित पातळी.",
                   "high": "कोलेस्टेरॉल वाढल्यामुळे हृदयावर ताण येऊ शकतो.",
                   "tip": "आहारात जवस वापरा आणि तेलकट पदार्थ टाळा."},
        },
        "symptom_rules": {
            "keywords": ["chest", "heaviness", "breath", "walking", "pressure", "heart"],
            "high": {"en": "Elevated LDL cholesterol leads to fatty arterial deposition, which may contribute to exertional chest tightness or shortness of breath.",
                     "hi": "खराब कोलेस्ट्रॉल बढ़ने से नसों में रुकावट आ सकती है, जिससे चलने पर भारीपन या सांस फूलने का अनुभव हो सकता है।",
                     "mr": "LDL वाढल्याने रक्तवाहिन्यांमध्ये अडथळा निर्माण होऊ शकतो, ज्यामुळे चालताना छातीत जडपणा जाणवू शकतो."},
        },
    },
    {
        "key": "vitamin_d",
        "name": "25-OH Vitamin D Total",
        "loinc": "62292-8",
        "unit": "ng/mL",
        "patterns": [r"(?i)\b(?:vitamin\s*d|25-oh|vit\s*d3?)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 30.0, "normal_high": 100.0,
        "panic_low": 10.0, "panic_high": 150.0,
        "guideline": "Endocrine Society Clinical Practice Guideline on Vitamin D",
        "scale_bucket": "normal",
        "translations": {
            "en": {"what": "Hormonal vitamin essential for bone mineral density and immune response.",
                   "low": "Deficiency. Associated with non-specific muscle fatigue and joint aches.",
                   "high": "Optimal sunshine level.",
                   "tip": "Get 15 minutes of early morning sun exposure and consult physician regarding D3 repletion."},
            "hi": {"what": "हड्डियों की मजबूती और रोग प्रतिरोधक क्षमता के लिए आवश्यक विटामिन।",
                   "low": "विटामिन डी की कमी। थकान और जोड़ों में दर्द का कारण।",
                   "high": "उत्तम व पर्याप्त स्तर।",
                   "tip": "सुबह की धूप लें और डॉक्टर की सलाह से सप्लीमेंट शुरू करें।"},
            "mr": {"what": "हाडांच्या बळकटीसाठी आणि प्रतिकारशक्तीसाठी आवश्यक घटक.",
                   "low": "व्हिटॅमिनची कमतरता. अंगदुखी आणि थकवा जाणवू शकतो.",
                   "high": "उत्तम पातळी.",
                   "tip": "दररोज सकाळी कोवळ्या उन्हात बसा आणि डॉक्टरांचा सल्ला घ्या."},
        },
        "symptom_rules": {
            "keywords": ["bone", "joint", "back", "muscle", "aches", "pain", "cramps", "tired", "mood", "depression"],
            "low": {"en": "Vitamin D deficiency impairs calcium absorption in bones and neuromuscular signaling, causing chronic back aches and body fatigue.",
                    "hi": "विटामिन डी की कमी से हड्डियां कमजोर होती हैं और मांसपेशियों में दर्द व लगातार बदन दर्द बना रहता है।",
                    "mr": "व्हिटॅमिन डी च्या कमतरतेमुळे हाडे आणि स्नायूंमध्ये सतत वेदना, कंबरदुखी व अंगदुखी जाणवते."},
        },
    },
    {
        "key": "hemoglobin",
        "name": "Hemoglobin (Hb)",
        "loinc": "718-7",
        "unit": "g/dL",
        "patterns": [r"(?i)\b(?:hemoglobin|hb|hgb)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 12.0, "normal_high": 17.5,
        "panic_low": 7.0, "panic_high": 20.0,
        "guideline": "WHO Haemoglobin Concentrations for the Diagnosis of Anaemia",
        "scale_bucket": "small",
        "translations": {
            "en": {"what": "Iron-rich protein in red blood cells that transports oxygen.",
                   "low": "Anemia. Results in reduced oxygenation, dyspnea, and exhaustion.",
                   "high": "High hemoglobin. Maintain optimal hydration.",
                   "tip": "Increase consumption of iron-dense foods like spinach, beetroot, and jaggery."},
            "hi": {"what": "खून में ऑक्सीजन ले जाने वाला मुख्य प्रोटीन।",
                   "low": "एनीमिया (खून की कमी)। सांस फूलना और सुस्ती महसूस होना।",
                   "high": "हीमोग्लोबिन अधिक है। पर्याप्त पानी पिएं।",
                   "tip": "पालक, अनार, चुकंदर और गुड़ का सेवन करें।"},
            "mr": {"what": "रक्तात ऑक्सिजन वाहून नेणारे मुख्य घटक.",
                   "low": "अ‍ॅनिमिया (रक्ताची कमतरता). यामुळे थकवा जाणवतो.",
                   "high": "प्रमाण जास्त आहे. भरपूर पाणी प्या.",
                   "tip": "पालक, बीट, डाळिंब आणि गूळ आहारात ठेवा."},
        },
        "symptom_rules": {
            "keywords": ["pale", "breath", "breathing", "tired", "fatigue", "weakness", "stamina", "cold", "dizzy"],
            "low": {"en": "Low hemoglobin means fewer red blood cells carrying oxygen to your muscles and brain, causing shortness of breath and extreme fatigue.",
                    "hi": "हीमोग्लोबिन कम होने से शरीर और मांसपेशियों में ऑक्सीजन की कमी हो जाती है, जिससे सांस फूलना और भारी थकान होती है।",
                    "mr": "हिमोग्लोबिन कमी असल्यामुळे शरीराला आणि मेंदूला ऑक्सिजन कमी मिळतो, ज्यामुळे धाप लागणे आणि तीव्र थकवा जाणवतो."},
            "high": {"en": "High hemoglobin increases blood thickness, which can lead to headaches, facial flushing, and mild dizziness.",
                     "hi": "हीमोग्लोबिन अधिक होने से खून गाढ़ा हो सकता है, जिससे सिरदर्द और चक्कर आ सकते हैं।",
                     "mr": "हिमोग्लोबिन जास्त असल्यामुळे डोकेदुखी आणि चक्कर येण्याचा त्रास होऊ शकतो."},
        },
    },
    {
        "key": "serum_creatinine",
        "name": "Serum Creatinine",
        "loinc": "2160-0",
        "unit": "mg/dL",
        "patterns": [r"(?i)\b(?:creatinine|serum\s*creatinine|s\.?\s*creatinine)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 0.6, "normal_high": 1.2,
        "panic_low": 0.3, "panic_high": 3.0,
        "guideline": "KDIGO Clinical Practice Guideline for Acute Kidney Injury & CKD",
        "scale_bucket": "small",
        "translations": {
            "en": {"what": "Metabolic breakdown marker reflecting renal glomerular filtration rate.",
                   "low": "Low baseline muscle mass indicator.",
                   "high": "Renal strain. Kidneys are filtering metabolic waste at reduced clearance.",
                   "tip": "Maintain hydration (2.5 to 3 L/day) and review nephrotoxic medications."},
            "hi": {"what": "यह दिखाता है कि आपकी किडनी खून को कितना साफ कर रही है।",
                   "low": "मांसपेशियों के कम भार का संकेत।",
                   "high": "किडनी पर दबाव। पानी की मात्रा बढ़ाएं और नमक नियंत्रित करें।",
                   "tip": "२.५ से ३ लीटर पानी पिएं और डॉक्टर से दवाओं की समीक्षा कराएं।"},
            "mr": {"what": "किडनी रक्त किती स्वच्छ गाळत आहे हे दर्शवणारा घटक.",
                   "low": "कमी स्नायू वस्तुमानाचे लक्षण.",
                   "high": "किडनीवर ताण दर्शवते. पाण्याचे प्रमाण वाढवा.",
                   "tip": "भरपूर पाणी प्या आणि डॉक्टरांच्या सल्ल्याने औषधे तपासा."},
        },
        "symptom_rules": {
            "keywords": ["swelling", "feet", "legs", "nausea", "urine", "puffy", "eyes", "itch"],
            "high": {"en": "Elevated creatinine indicates slower kidney filtration, which can cause fluid buildup leading to swollen ankles and puffiness.",
                     "hi": "क्रिएटिनिन अधिक होना किडनी की धीमी सफाई दर्शाता है, जिससे पैरों और चेहरे पर हल्की सूजन आ सकती है।",
                     "mr": "क्रिएटिनिन वाढल्याने किडन्या रक्त सावकाश गाळतात, ज्यामुळे पायांवर किंवा चेहऱ्यावर सूज येऊ शकते."},
        },
    },
    {
        "key": "wbc_count",
        "name": "Total WBC (Leukocyte) Count",
        "loinc": "6690-2",
        "unit": "/uL",
        "patterns": [r"(?i)\b(?:wbc|white\s*blood\s*cell(?:s)?|total\s*leukocyte\s*count|tlc)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 4000.0, "normal_high": 11000.0,
        "panic_low": 2000.0, "panic_high": 30000.0,
        "guideline": "CBC Reference Intervals - CLSI Guidelines",
        "scale_bucket": "normal",
        "translations": {
            "en": {"what": "White blood cells that form the core of your immune defense against infection.",
                   "low": "Low WBC weakens immune defense, raising infection risk.",
                   "high": "Elevated WBC - the immune system is actively responding to infection or inflammation.",
                   "tip": "Prioritize sleep and hygiene; a rising WBC alongside fever warrants prompt medical review."},
            "hi": {"what": "श्वेत रक्त कोशिकाएं जो संक्रमण से लड़ने में मुख्य भूमिका निभाती हैं।",
                   "low": "WBC कम होने से रोग प्रतिरोधक क्षमता घटती है।",
                   "high": "WBC बढ़ा हुआ है - शरीर संक्रमण या सूजन से लड़ रहा है।",
                   "tip": "पर्याप्त नींद लें और बुखार के साथ WBC बढ़ने पर तुरंत डॉक्टर से मिलें।"},
            "mr": {"what": "पांढऱ्या रक्तपेशी ज्या संसर्गाशी लढण्यास मदत करतात.",
                   "low": "WBC कमी असल्याने प्रतिकारशक्ती कमी होते.",
                   "high": "WBC वाढलेले आहे - शरीर संसर्गाशी लढत आहे.",
                   "tip": "पुरेशी झोप घ्या आणि तापासोबत WBC वाढल्यास डॉक्टरांना भेटा."},
        },
        "symptom_rules": {
            "keywords": ["fever", "infection", "chills", "throat", "cough", "pain", "swelling", "burn"],
            "high": {"en": "Elevated WBC confirms your immune system is actively fighting an acute infection or inflammatory response causing your fever/pain.",
                     "hi": "WBC का बढ़ा हुआ स्तर बताता है कि आपकी रोग प्रतिरोधक प्रणाली किसी संक्रमण या सूजन से लड़ रही है, जिससे बुखार या दर्द है।",
                     "mr": "WBC चे प्रमाण वाढल्याचे स्पष्ट होते की तुमची रोगप्रतिकार यंत्रणा संसर्गाशी लढत आहे, ज्यामुळे ताप किंवा अंगदुखी जाणवते."},
            "low": {"en": "Low WBC count weakens defense immunity, making you prone to recurring viral infections and slower recovery.",
                    "hi": "WBC कम होने से इम्यूनिटी घटती है, जिससे बार-बार संक्रमण और कमजोरी हो सकती है।",
                    "mr": "WBC कमी असल्यामुळे प्रतिकारशक्ती मंदावते आणि आजारपण लवकर बरे होत नाही."},
        },
    },
    {
        "key": "platelet_count",
        "name": "Platelet Count",
        "loinc": "777-3",
        "unit": "x10^3/uL",
        "patterns": [r"(?i)\b(?:platelet(?:s)?(?:\s*count)?|plt)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 150.0, "normal_high": 450.0,
        "panic_low": 50.0, "panic_high": 1000.0,
        "guideline": "CBC Reference Intervals - CLSI Guidelines",
        "scale_bucket": "small",
        "translations": {
            "en": {"what": "Blood cell fragments responsible for clotting.",
                   "low": "Low platelets slow clotting, raising bleeding/bruising risk.",
                   "high": "Elevated platelets - usually reactive to inflammation or infection.",
                   "tip": "Avoid unnecessary NSAIDs and watch for unusual bruising or bleeding."},
            "hi": {"what": "खून का थक्का जमाने वाली रक्त कोशिकाएं।",
                   "low": "प्लेटलेट कम होने से रक्तस्राव का खतरा बढ़ता है।",
                   "high": "प्लेटलेट बढ़ा हुआ है - आमतौर पर सूजन या संक्रमण की प्रतिक्रिया।",
                   "tip": "अनावश्यक दर्द निवारक दवाओं से बचें और असामान्य चोट के निशान पर ध्यान दें।"},
            "mr": {"what": "रक्त गोठण्यासाठी जबाबदार पेशी.",
                   "low": "प्लेटलेट्स कमी असल्याने रक्तस्रावाचा धोका वाढतो.",
                   "high": "प्लेटलेट्स वाढलेले आहेत - सहसा सूज किंवा संसर्गाला प्रतिसाद.",
                   "tip": "अनावश्यक वेदनाशामक औषधे टाळा आणि असामान्य जखमांकडे लक्ष द्या."},
        },
        "symptom_rules": {
            "keywords": ["bleeding", "bruise", "bruising", "spots", "rash", "nosebleed", "gum"],
            "low": {"en": "Low platelet count reduces blood clotting speed, causing unexplained purple bruises, bleeding gums, or small red skin spots.",
                    "hi": "प्लेटलेट कम होने से खून का थक्का धीरे बनता है, जिससे त्वचा पर नीले निशान या मसूड़ों से खून आ सकता है।",
                    "mr": "प्लेटलेट्स कमी असल्यामुळे अंगावर व्रण उमटणे किंवा रक्तस्त्राव होण्याचा धोका वाढतो."},
        },
    },
    {
        "key": "tsh_thyroid",
        "name": "Thyroid Stimulating Hormone (TSH)",
        "loinc": "3016-3",
        "unit": "mIU/L",
        "patterns": [r"(?i)\b(?:tsh|thyroid\s*stimulating\s*hormone)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 0.4, "normal_high": 4.0,
        "panic_low": 0.05, "panic_high": 20.0,
        "guideline": "American Thyroid Association Guidelines for Hypothyroidism/Hyperthyroidism",
        "scale_bucket": "small",
        "translations": {
            "en": {"what": "Pituitary hormone that regulates thyroid gland output and overall metabolic rate.",
                   "low": "Low TSH signals an overactive thyroid (hyperthyroidism).",
                   "high": "Elevated TSH signals an underactive thyroid (hypothyroidism), slowing metabolism.",
                   "tip": "Discuss thyroid panel timing and medication adherence with your physician."},
            "hi": {"what": "थायरॉयड ग्रंथि और चयापचय दर को नियंत्रित करने वाला हार्मोन।",
                   "low": "कम TSH थायरॉयड के अतिसक्रिय होने का संकेत है।",
                   "high": "बढ़ा हुआ TSH सुस्त थायरॉयड (हाइपोथायरायडिज्म) दर्शाता है।",
                   "tip": "डॉक्टर से थायरॉयड जांच और दवा के समय पर चर्चा करें।"},
            "mr": {"what": "थायरॉईड ग्रंथी आणि चयापचय दर नियंत्रित करणारे संप्रेरक.",
                   "low": "TSH कमी असणे थायरॉईड अतिसक्रिय असल्याचे दर्शवते.",
                   "high": "TSH वाढल्यामुळे थायरॉईड मंदावतो.",
                   "tip": "थायरॉईड तपासणी व औषधांबाबत डॉक्टरांशी चर्चा करा."},
        },
        "symptom_rules": {
            "keywords": ["weight", "gain", "loss", "cold", "heat", "hair", "constipation", "heart", "pulse", "palpitation"],
            "high": {"en": "Elevated TSH indicates an underactive thyroid (Hypothyroidism), slowing metabolic rate and causing sudden weight gain, hair fall, and fatigue.",
                     "hi": "बढ़ा हुआ TSH सुस्त थायरॉयड (हाइपोथायरायडिज्म) दर्शाता है, जिससे वजन बढ़ना, बाल झड़ना और अत्यधिक सुस्ती होती है।",
                     "mr": "TSH वाढल्यामुळे थायरॉईड मंदावतो, ज्यामुळे वजन वाढणे, केस गळणे आणि सुस्ती जाणवते."},
            "low": {"en": "Low TSH signals an overactive thyroid (Hyperthyroidism), speeding up metabolism and causing rapid heart rate and heat intolerance.",
                    "hi": "कम TSH थायरॉयड के अतिसक्रिय होने का संकेत है, जिससे दिल की धड़कन तेज होना और बेचैनी हो सकती है।",
                    "mr": "TSH कमी असणे थायरॉईड अतिसक्रिय असल्याचे दर्शवते, ज्यामुळे हृदयाचे ठोके वाढणे आणि अस्वस्थता जाणवते."},
        },
    },
    {
        "key": "serum_uric_acid",
        "name": "Serum Uric Acid",
        "loinc": "3084-1",
        "unit": "mg/dL",
        "patterns": [r"(?i)\b(?:uric\s*acid|serum\s*uric\s*acid)\b[\s:]*([0-9]+(?:\.[0-9]+)?)"],
        "normal_low": 3.5, "normal_high": 7.2,
        "panic_low": 2.0, "panic_high": 12.0,
        "guideline": "ACR Guideline for Management of Gout",
        "scale_bucket": "small",
        "translations": {
            "en": {"what": "Waste product from purine breakdown; buildup can crystallize in joints.",
                   "low": "Low baseline - not typically clinically significant on its own.",
                   "high": "Elevated uric acid - raises risk of gout and urate crystal deposition.",
                   "tip": "Reduce red meat/organ meat and sweetened beverages; increase water intake."},
            "hi": {"what": "प्यूरीन के टूटने से बनने वाला अपशिष्ट पदार्थ, जो जोड़ों में क्रिस्टल बना सकता है।",
                   "low": "सामान्यतः चिंताजनक नहीं।",
                   "high": "यूरिक एसिड बढ़ा हुआ है - गाउट का खतरा बढ़ता है।",
                   "tip": "लाल मांस व मीठे पेय कम करें, पानी अधिक पिएं।"},
            "mr": {"what": "प्युरीनच्या विघटनातून तयार होणारा टाकाऊ पदार्थ, जो सांध्यांत जमा होऊ शकतो.",
                   "low": "सहसा चिंताजनक नाही.",
                   "high": "युरिक अ‍ॅसिड वाढलेले आहे - गाउटचा धोका वाढतो.",
                   "tip": "लाल मांस व गोड पेये कमी करा, पाणी जास्त प्या."},
        },
        "symptom_rules": {
            "keywords": ["toe", "heel", "joint", "foot", "knee", "swelling", "pain", "gout"],
            "high": {"en": "High uric acid forms sharp urate micro-crystals inside joints (especially big toe and knees), causing intense throbbing pain and swelling.",
                     "hi": "यूरिक एसिड बढ़ने से जोड़ों में क्रिस्टल जमा होते हैं, जिससे पैर के अंगूठे और घुटनों में तेज दर्द व सूजन होती है।",
                     "mr": "युरिक अ‍ॅसिड वाढल्यामुळे सांध्यांमध्ये खडे जमा होतात, ज्यामुळे पायाच्या अंगठ्यात आणि गुडघ्यांत तीव्र वेदना व सूज येते."},
        },
    },
]

SEED_DRUG_RULES = [
    {
        "rule_type": "drug_supplement",
        "trigger_a": "metformin",
        "trigger_b": "calcium",
        "severity": "warn",
        "pair_label": "Metformin + Calcium Carbonate",
        "mechanism": "Calcium can alter GI transit time and diminish Metformin absorption efficacy. Space intake by 2+ hours.",
    },
    {
        "rule_type": "drug_supplement",
        "trigger_a": "metformin",
        "trigger_b": "green tea",
        "severity": "warn",
        "pair_label": "Metformin + Green Tea Extract (EGCG)",
        "mechanism": "Potential additive hypoglycemic effect. Ensure routine fasting blood glucose checks.",
    },
    {
        "rule_type": "drug_biomarker",
        "trigger_a": "metformin",
        "biomarker_key": "serum_creatinine",
        "operator": ">",
        "threshold": 1.4,
        "severity": "danger",
        "pair_label": "Metformin renal clearance risk",
        "mechanism": "Metformin renal clearance is reduced with elevated creatinine (>{threshold} mg/dL, current {value} mg/dL). Clinical review required to prevent lactic acidosis risk.",
    },
    {
        "rule_type": "drug_drug",
        "trigger_a": "warfarin",
        "trigger_b": "aspirin",
        "severity": "danger",
        "pair_label": "Warfarin + Aspirin",
        "mechanism": "Combined anticoagulant/antiplatelet effect substantially raises bleeding risk. Requires close INR monitoring and physician oversight.",
    },
    {
        "rule_type": "drug_supplement",
        "trigger_a": "warfarin",
        "trigger_b": "vitamin k",
        "severity": "warn",
        "pair_label": "Warfarin + Vitamin K",
        "mechanism": "Vitamin K directly antagonizes Warfarin's anticoagulant mechanism. Keep dietary vitamin K intake consistent day-to-day.",
    },
    {
        "rule_type": "drug_supplement",
        "trigger_a": "levothyroxine",
        "trigger_b": "calcium",
        "severity": "warn",
        "pair_label": "Levothyroxine + Calcium Carbonate",
        "mechanism": "Calcium chelates levothyroxine in the gut, reducing absorption. Space intake by at least 4 hours.",
    },
    {
        "rule_type": "drug_drug",
        "trigger_a": "ibuprofen",
        "trigger_b": "lisinopril",
        "severity": "warn",
        "pair_label": "Ibuprofen (NSAID) + Lisinopril (ACE inhibitor)",
        "mechanism": "NSAIDs can blunt the blood-pressure-lowering effect of ACE inhibitors and stress renal filtration when combined long-term.",
    },
]
'''

with open("seed_data.py", "w", encoding="utf-8") as f:
    f.write(seed_data_code)
print("Updated: seed_data.py")

models_orm_code = '''# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    age = Column(Integer, default=30)
    gender = Column(String, default="Male")
    dietary_preference = Column(String, default="Vegetarian")
    active_prescriptions = Column(JSON, default=list)
    active_supplements = Column(JSON, default=list)
    treatment_history = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    lab_reports = relationship("LabReport", back_populates="user", cascade="all, delete-orphan")

class LabReport(Base):
    __tablename__ = "lab_reports"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    hospital_name = Column(String, default="Metropolis Healthcare")
    record_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    raw_ocr_text = Column(Text, nullable=True)
    biomarkers = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="lab_reports")

class BiomarkerRegistryModel(Base):
    __tablename__ = "biomarker_registry"
    key = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    loinc = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    patterns = Column(JSON, default=list)
    normal_low = Column(Float, nullable=False)
    normal_high = Column(Float, nullable=False)
    panic_low = Column(Float, nullable=True)
    panic_high = Column(Float, nullable=True)
    guideline = Column(String, nullable=False)
    scale_bucket = Column(String, default="normal")
    translations = Column(JSON, default=dict)
    symptom_rules = Column(JSON, default=dict)

class DrugRuleModel(Base):
    __tablename__ = "drug_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String, nullable=False)
    trigger_a = Column(String, index=True, nullable=False)
    trigger_b = Column(String, nullable=True)
    biomarker_key = Column(String, nullable=True)
    operator = Column(String, nullable=True)
    threshold = Column(Float, nullable=True)
    severity = Column(String, nullable=False)
    pair_label = Column(String, nullable=False)
    mechanism = Column(Text, nullable=False)
'''

with open("models/orm.py", "w", encoding="utf-8") as f:
    f.write(models_orm_code)
print("Updated: models/orm.py")

db_seeder_code = '''# -*- coding: utf-8 -*-
from sqlalchemy.orm import Session
from models.orm import BiomarkerRegistryModel, DrugRuleModel
from seed_data import SEED_BIOMARKERS, SEED_DRUG_RULES

def seed_db_if_empty(db: Session):
    if db.query(BiomarkerRegistryModel).first() is None:
        for b in SEED_BIOMARKERS:
            model = BiomarkerRegistryModel(
                key=b["key"],
                name=b["name"],
                loinc=b["loinc"],
                unit=b["unit"],
                patterns=b.get("patterns", []),
                normal_low=b["normal_low"],
                normal_high=b["normal_high"],
                panic_low=b.get("panic_low"),
                panic_high=b.get("panic_high"),
                guideline=b["guideline"],
                scale_bucket=b.get("scale_bucket", "normal"),
                translations=b.get("translations", {}),
                symptom_rules=b.get("symptom_rules", {})
            )
            db.add(model)
        db.commit()

    if db.query(DrugRuleModel).first() is None:
        for r in SEED_DRUG_RULES:
            model = DrugRuleModel(
                rule_type=r["rule_type"],
                trigger_a=r["trigger_a"].strip().lower(),
                trigger_b=r.get("trigger_b", "").strip().lower() if r.get("trigger_b") else None,
                biomarker_key=r.get("biomarker_key"),
                operator=r.get("operator"),
                threshold=r.get("threshold"),
                severity=r["severity"],
                pair_label=r["pair_label"],
                mechanism=r["mechanism"]
            )
            db.add(model)
        db.commit()
'''

with open("services/knowledge_seeder.py", "w", encoding="utf-8") as f:
    f.write(db_seeder_code)
print("Updated: services/knowledge_seeder.py")
