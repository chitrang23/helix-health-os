# Regional Disease-Specific Doctor Recommendation Engine
class DoctorMatcher:
    REGIONAL_SPECIALISTS = {
        "mumbai": {
            "cardiology": [{"name": "Dr. Ajit Menon", "hospital": "Lilavati Hospital, Bandra", "contact": "+91-22-26751000"}, {"name": "Dr. P. Rafiyath", "hospital": "Asian Heart Institute, BKC", "contact": "+91-22-66986666"}],
            "diabetology": [{"name": "Dr. Shashank Joshi", "hospital": "Lilavati & Joshi Clinic, Khar", "contact": "+91-22-26469999"}],
            "neurology": [{"name": "Dr. Uday Andar", "hospital": "Breach Candy Hospital", "contact": "+91-22-23672889"}],
            "general": [{"name": "Dr. Rahul Khurana", "hospital": "Global Hospitals, Parel", "contact": "+91-22-67670101"}]
        },
        "default": {
            "cardiology": [{"name": "Senior Consultant Cardiologist", "hospital": "Apex Metro Heart Institute", "contact": "1800-HEART-CLINIC"}],
            "diabetology": [{"name": "Endocrinology & Metabolic Specialist", "hospital": "Metabolic Care Center", "contact": "1800-SUGAR-CARE"}],
            "general": [{"name": "Internal Medicine Lead", "hospital": "City General Hospital", "contact": "1800-GENERAL"}]
        }
    }

    @classmethod
    def recommend_doctor(cls, specialty: str, region: str = "mumbai"):
        reg = region.lower() if region.lower() in cls.REGIONAL_SPECIALISTS else "default"
        spec = specialty.lower()
        specialist_pool = cls.REGIONAL_SPECIALISTS[reg]
        for key in specialist_pool:
            if key in spec:
                return specialist_pool[key]
        return specialist_pool.get("general", [{"name": "Dr. General Practitioner", "hospital": "Primary Health Clinic"}])
