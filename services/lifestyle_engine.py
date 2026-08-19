class LifestyleEngine:
    @staticmethod
    def generate_recommendations(markers: dict, dietary_pref: str = "Vegetarian") -> dict:
        diet = []
        exercise = [
            "Calisthenics: 3 sets of 12-15 bodyweight squats and pushups 4 days a week.",
            "Zone-2 Aerobic: 20-minute brisk walk post-lunch or post-dinner."
        ]

        if markers.get("fasting_glucose", 0) > 100 or markers.get("hba1c", 0) > 5.7:
            diet.append("Prioritize high-fiber low-GI meals: Sprouted moong, paneer/tofu salads, chia seeds.")
            diet.append("Eliminate ultra-processed sugars, maida, and late-night refined carb intake.")

        if markers.get("ldl_cholesterol", 0) > 130:
            diet.append("Incorporate 20g ground flaxseeds daily and minimize deep-fried items.")

        return {
            "dietary_preference": dietary_pref,
            "targeted_nutrition": diet,
            "exercise_protocol": exercise
        }
