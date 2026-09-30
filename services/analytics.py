from datetime import datetime

def calculate_longitudinal_velocity(historical_records: list, target_marker: str) -> dict:
    """
    Scans a chronological list of LabRecords for a user and calculates:
    - Absolute change
    - Velocity (% change per month)
    - Overall trajectory direction
    """
    timeline = []
    
    for rec in historical_records:
        biomarkers = rec.extracted_biomarkers or {}
        for key, details in biomarkers.items():
            if target_marker.lower() in key.lower():
                timeline.append({
                    "date": rec.created_at,
                    "value": float(details["value"]),
                    "unit": details.get("unit", "")
                })
                break

    if len(timeline) < 2:
        return {
            "marker": target_marker,
            "status": "INSUFFICIENT_HISTORICAL_DATA",
            "message": "Upload at least 2 historical reports to compute longitudinal velocity."
        }

    # Sort chronologically
    timeline.sort(key=lambda x: x["date"])
    first_entry = timeline[0]
    latest_entry = timeline[-1]

    days_elapsed = max((latest_entry["date"] - first_entry["date"]).days, 1)
    val_delta = latest_entry["value"] - first_entry["value"]
    pct_change = (val_delta / first_entry["value"]) * 100
    monthly_velocity = (pct_change / (days_elapsed / 30.0))

    trajectory = "STABLE"
    if monthly_velocity > 2.0:
        trajectory = "RISING_VELOCITY"
    elif monthly_velocity < -2.0:
        trajectory = "IMPROVING_DROPPING"

    return {
        "marker": target_marker,
        "first_recorded": {"value": first_entry["value"], "date": first_entry["date"].strftime("%Y-%m-%d")},
        "latest_recorded": {"value": latest_entry["value"], "date": latest_entry["date"].strftime("%Y-%m-%d")},
        "days_elapsed": days_elapsed,
        "absolute_change": round(val_delta, 2),
        "monthly_velocity_pct": round(monthly_velocity, 2),
        "trajectory": trajectory,
        "history_points": len(timeline)
    }
