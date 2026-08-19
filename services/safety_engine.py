from typing import List

class SafetyEngine:
    @staticmethod
    def evaluate_interactions(rx: List[str], supplements: List[str]) -> List[dict]:
        alerts = []
        rx_lower = [x.lower() for x in rx]
        supp_lower = [x.lower() for x in supplements]

        if any("metformin" in d for d in rx_lower) and any("calcium" in s for s in supp_lower):
            alerts.append({
                "level": "MODERATE",
                "pair": "Metformin + Calcium Carbonate",
                "mechanism": "Calcium can alter GI transit time and diminish Metformin absorption efficacy. Space intake by 2+ hours."
            })

        if any("metformin" in d for d in rx_lower) and any("green tea" in s for s in supp_lower):
            alerts.append({
                "level": "LOW",
                "pair": "Metformin + Green Tea Extract (EGCG)",
                "mechanism": "Potential additive hypoglycemic effect. Ensure routine fasting blood glucose checks."
            })

        return alerts
