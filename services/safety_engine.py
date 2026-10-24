from typing import List, Dict, Any, Optional
from models.orm import DrugRuleModel

class SafetyEngine:
    @staticmethod
    def evaluate_interactions(
        prescriptions: List[str],
        supplements: Optional[List[str]] = None,
        rules: Optional[List[Any]] = None,
        latest_biomarkers: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates potential drug-drug, drug-supplement, and drug-biomarker interactions.
        Returns a list of alerts containing both legacy keys ('level', 'pair', 'mechanism')
        and extended clinical keys ('severity', 'combination', 'recommendation', 'evidence_source').
        """
        alerts = []
        supplements = supplements or []
        rules = rules or []
        latest_biomarkers = latest_biomarkers or {}

        # Normalize text lists for clean substring matching
        all_rx = [rx.strip().lower() for rx in prescriptions if rx.strip()]
        all_supplements = [s.strip().lower() for s in supplements if s.strip()]
        all_substances = all_rx + all_supplements

        if not all_substances:
            return []

        # Normalize biomarker keys for case-insensitive lookup
        normalized_biomarkers = {k.strip().lower(): float(v) for k, v in latest_biomarkers.items() if v is not None}

        for rule in rules:
            if hasattr(rule, "is_active") and not rule.is_active:
                continue

            rule_type = getattr(rule, "rule_type", "")
            trigger_a = getattr(rule, "trigger_a", "").strip().lower()
            trigger_b = getattr(rule, "trigger_b", "").strip().lower() if getattr(rule, "trigger_b", None) else ""
            severity = getattr(rule, "severity", "high")
            pair_label = getattr(rule, "pair_label", f"{trigger_a} + {trigger_b}")
            evidence_source = getattr(rule, "evidence_source", "Versioned Clinical Pharmacovigilance Rules")

            # 1. Drug-Drug and Drug-Supplement Rules
            if rule_type in ("drug_drug", "drug_supplement"):
                has_a = any(trigger_a in item for item in all_substances)
                has_b = any(trigger_b in item for item in all_substances) if trigger_b else False

                if has_a and has_b:
                    mechanism = getattr(rule, "mechanism", "Potential pharmacological interaction detected.")
                    alerts.append({
                        # Legacy keys required by test suites
                        "level": severity,
                        "pair": pair_label,
                        "mechanism": mechanism,
                        # Extended fields for clinical UI/audit
                        "category": "Drug-Drug Interaction" if rule_type == "drug_drug" else "Drug-Supplement Interaction",
                        "severity": severity.upper(),
                        "combination": pair_label,
                        "clinical_effect": mechanism,
                        "recommendation": "Consult attending physician or pharmacist regarding timing separation or dosage review.",
                        "evidence_source": evidence_source
                    })

            # 2. Drug-Biomarker / Organ Clearance Contraindication Rules
            elif rule_type == "drug_biomarker":
                has_a = any(trigger_a in item for item in all_substances)
                biomarker_key = getattr(rule, "biomarker_key", None)
                clean_b_key = biomarker_key.strip().lower() if biomarker_key else None

                if has_a and clean_b_key and clean_b_key in normalized_biomarkers:
                    val = normalized_biomarkers[clean_b_key]
                    op = getattr(rule, "operator", ">")
                    threshold = float(getattr(rule, "threshold", 0.0))

                    triggered = False
                    if op == "<" and val < threshold:
                        triggered = True
                    elif op == "<=" and val <= threshold:
                        triggered = True
                    elif op == ">" and val > threshold:
                        triggered = True
                    elif op == ">=" and val >= threshold:
                        triggered = True

                    if triggered:
                        raw_mechanism = getattr(rule, "mechanism", "Contraindication detected: biomarker threshold exceeded.")
                        try:
                            formatted_mechanism = raw_mechanism.format(threshold=threshold, value=val)
                        except Exception:
                            formatted_mechanism = raw_mechanism

                        alerts.append({
                            # Legacy keys
                            "level": severity,
                            "pair": pair_label,
                            "mechanism": formatted_mechanism,
                            # Extended fields
                            "category": "Drug-Biomarker Contraindication",
                            "severity": severity.upper(),
                            "combination": f"{trigger_a.capitalize()} + {biomarker_key} ({val})",
                            "clinical_effect": formatted_mechanism,
                            "recommendation": "Requires prompt clinician oversight prior to continued administration.",
                            "evidence_source": evidence_source
                        })

        return alerts