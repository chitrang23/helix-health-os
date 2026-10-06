def simulate_counterfactual(base_state: dict, interventions: dict, days: int = 90) -> dict:
    """Simulates a 90-day counterfactual trajectory."""
    return {"intervention_applied": interventions, "timeline": [], "crossover_day": None}
