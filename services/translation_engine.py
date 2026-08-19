class TranslationEngine:
    DICTIONARY = {
        "hba1c": {
            "en": "HbA1c reflects your 3-month average blood glucose. Higher levels show progression towards diabetes.",
            "hi": "HbA1c पिछले ३ महीनों के औसत ब्लड शुगर को दर्शाता है। इसका बढ़ना प्रीडायबिटीज का संकेत है।",
            "mr": "HbA1c मागील ३ महिन्यांतील साखरेची सरासरी पातळी दर्शवतो. ही वाढ मधुमेहाचा धोका दर्शवते."
        },
        "ldl_cholesterol": {
            "en": "LDL is 'bad' cholesterol that accumulates in blood vessels, increasing cardiovascular risk.",
            "hi": "LDL खराब कोलेस्ट्रॉल है जो रक्त वाहिकाओं में जमा होकर हृदय रोग का खतरा बढ़ाता है।",
            "mr": "LDL हे वाईट कोलेस्टेरॉल असून ते रक्तवाहिन्यांमध्ये जमा होऊन हृदयविकाराचा धोका वाढवते."
        },
        "vitamin_d": {
            "en": "Vitamin D supports bone health, immunity, and hormonal regulation.",
            "hi": "विटामिन D हड्डियों के स्वास्थ्य, रोग प्रतिरोधक क्षमता और हार्मोन संतुलन में मदद करता है।",
            "mr": "व्हिटॅमिन D हाडांचे आरोग्य, प्रतिकारशक्ती आणि संप्रेरक नियंत्रणास मदत करते."
        }
    }

    @classmethod
    def get_explanation(cls, term: str, lang: str = "en") -> str:
        term_data = cls.DICTIONARY.get(term.lower())
        if not term_data:
            return "Term not in standard layperson registry."
        return term_data.get(lang, term_data["en"])
