import pytest
from unittest.mock import MagicMock
from services.safety_engine import SafetyEngine

@pytest.fixture
def sample_rules():
    # Active Drug-Drug Rule
    rule_dd = MagicMock()
    rule_dd.rule_type = "drug_drug"
    rule_dd.trigger_a = "metformin"
    rule_dd.trigger_b = "contrast"
    rule_dd.severity = "high"
    rule_dd.pair_label = "Metformin + Iodinated Contrast"
    rule_dd.mechanism = "Risk of lactic acidosis."
    rule_dd.is_active = True

    # Active Drug-Biomarker Rule (< operator)
    rule_db_lt = MagicMock()
    rule_db_lt.rule_type = "drug_biomarker"
    rule_db_lt.trigger_a = "metformin"
    rule_db_lt.biomarker_key = "eGFR"
    rule_db_lt.operator = "<"
    rule_db_lt.threshold = 30.0
    rule_db_lt.severity = "critical"
    rule_db_lt.pair_label = "Metformin Renal Cutoff"
    rule_db_lt.mechanism = "Contraindicated when eGFR < {threshold} mL/min (current: {value})."
    rule_db_lt.is_active = True

    # Inactive Rule (Should be skipped)
    rule_inactive = MagicMock()
    rule_inactive.rule_type = "drug_drug"
    rule_inactive.trigger_a = "aspirin"
    rule_inactive.trigger_b = "warfarin"
    rule_inactive.severity = "high"
    rule_inactive.is_active = False

    # Operators Tests Rules: <=, >, >=
    rule_lte = MagicMock()
    rule_lte.rule_type = "drug_biomarker"
    rule_lte.trigger_a = "statin"
    rule_lte.biomarker_key = "ALT"
    rule_lte.operator = "<="
    rule_lte.threshold = 50.0
    rule_lte.severity = "moderate"
    rule_lte.pair_label = "Statin ALT Check"
    rule_lte.mechanism = "ALT within range"
    rule_lte.is_active = True

    rule_gt = MagicMock()
    rule_gt.rule_type = "drug_biomarker"
    rule_gt.trigger_a = "statin"
    rule_gt.biomarker_key = "ALT"
    rule_gt.operator = ">"
    rule_gt.threshold = 100.0
    rule_gt.severity = "high"
    rule_gt.pair_label = "Statin ALT High"
    rule_gt.mechanism = "ALT elevated"
    rule_gt.is_active = True

    rule_gte = MagicMock()
    rule_gte.rule_type = "drug_biomarker"
    rule_gte.trigger_a = "statin"
    rule_gte.biomarker_key = "ALT"
    rule_gte.operator = ">="
    rule_gte.threshold = 120.0
    rule_gte.severity = "critical"
    rule_gte.pair_label = "Statin ALT Critical"
    rule_gte.mechanism = "ALT critical"
    rule_gte.is_active = True

    return [rule_dd, rule_db_lt, rule_inactive, rule_lte, rule_gt, rule_gte]


def test_drug_drug_interaction_detected(sample_rules):
    rx = ["Metformin 500mg", "Iodinated Contrast"]
    alerts = SafetyEngine.evaluate_interactions(rx, [], sample_rules)
    assert len(alerts) == 1
    assert alerts[0]["level"] == "high"
    assert alerts[0]["pair"] == "Metformin + Iodinated Contrast"


def test_drug_biomarker_threshold_exceeded(sample_rules):
    rx = ["Metformin 500mg"]
    biomarkers = {"eGFR": 24.5}
    alerts = SafetyEngine.evaluate_interactions(rx, [], sample_rules, latest_biomarkers=biomarkers)
    assert any(a["pair"] == "Metformin Renal Cutoff" for a in alerts)


def test_inactive_rule_is_skipped(sample_rules):
    rx = ["Aspirin", "Warfarin"]
    alerts = SafetyEngine.evaluate_interactions(rx, [], sample_rules)
    assert not any(a["pair"] == "Interaction Alert" for a in alerts)


def test_all_biomarker_operators(sample_rules):
    rx = ["Atorvastatin 20mg"]
    
    # Trigger <= (50.0)
    alerts_lte = SafetyEngine.evaluate_interactions(rx, [], sample_rules, latest_biomarkers={"ALT": 50.0})
    assert any(a["pair"] == "Statin ALT Check" for a in alerts_lte)

    # Trigger > (100.0)
    alerts_gt = SafetyEngine.evaluate_interactions(rx, [], sample_rules, latest_biomarkers={"ALT": 105.0})
    assert any(a["pair"] == "Statin ALT High" for a in alerts_gt)

    # Trigger >= (120.0)
    alerts_gte = SafetyEngine.evaluate_interactions(rx, [], sample_rules, latest_biomarkers={"ALT": 120.0})
    assert any(a["pair"] == "Statin ALT Critical" for a in alerts_gte)
