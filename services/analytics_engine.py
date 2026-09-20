from typing import List, Dict, Any

class AnalyticsEngine:
    @staticmethod
    def analyze_biomarker_trends(history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates baseline averages, delta percentage changes, and flags clinical anomalies.
        """
        trends = {}
        for entry in history:
            for key, val in entry.get("biomarkers", {}).items():
                if key not in trends:
                    trends[key] = []
                trends[key].append(float(val))

        analysis = {}
        for key, values in trends.items():
            if not values:
                continue
            avg_val = sum(values) / len(values)
            latest = values[-1]
            previous = values[-2] if len(values) > 1 else latest
            delta_pct = ((latest - previous) / previous * 100) if previous != 0 else 0.0

            analysis[key] = {
                "latest_value": latest,
                "historical_avg": round(avg_val, 2),
                "delta_percentage": round(delta_pct, 2),
                "trend_status": "increasing" if delta_pct > 5 else ("decreasing" if delta_pct < -5 else "stable")
            }

        return analysis
