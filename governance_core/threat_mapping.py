"""
Threat-Driven Metrics Mapping

This module provides a declarative mapping between existing metrics and explicit
privacy and governance threats. It is purely interpretive and structural - it does
NOT change how metrics are computed or introduce pipeline decisions.

Purpose:
- Link metrics to specific attack types
- Identify impacted properties (privacy/utility/consistency)
- Provide severity assessments for governance interpretation
- Enable threat-based auditability

Constraints:
- This is metadata only - no computation logic
- All mappings reference existing metric names (aligned with MetricsSchema)
- No APPROVE/REJECT logic - advisory only
- Backward-compatible with existing system
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# Import canonical field names so this module has no magic strings
from .schemas import (
    F_PRIVACY_SCORE,
    F_LEAKAGE_RISK_LEVEL,
    F_DUPLICATES_RATE,
    F_DUPLICATES_COUNT,
    F_MEMBERSHIP_INFERENCE_AUC,
    F_DISTRIBUTION_SHIFT_SCORE,
    F_MODE_COLLAPSE_PROBABILITY,
    F_CORRELATION_FROBENIUS_NORM,
    F_UTILITY_SCORE,
    F_STATISTICAL_DRIFT,
    F_SEMANTIC_VIOLATIONS,
    F_NEAREST_DISTANCES_MEAN,
    F_PRIVACY_RISK,
    F_STATISTICAL_FIDELITY,
)


# ============================================================================
# STABLE THREAT IDENTIFIERS
# ============================================================================

THREAT_MEMBERSHIP_INFERENCE    = "membership_inference"
THREAT_RECORD_LINKAGE          = "record_linkage"
THREAT_ATTRIBUTE_INFERENCE     = "attribute_inference"
THREAT_PRIVACY_LEAKAGE         = "privacy_leakage"
THREAT_SEMANTIC_VIOLATION      = "semantic_violation"
THREAT_DISTRIBUTION_DRIFT      = "distribution_drift"
THREAT_CORRELATION_INCONSISTENCY = "correlation_inconsistency"
THREAT_UTILITY_DEGRADATION     = "utility_degradation"


@dataclass
class ThreatSignal:
    """
    Represents a detected threat signal derived from metrics.

    Attributes:
        threat_id: Stable unique identifier (use THREAT_* constants)
        threat_name: Human-readable threat name
        attack_type: Type of attack (e.g., membership_inference, attribute_inference)
        impacted_property: Which property is at risk (privacy/utility/consistency)
        severity: Derived severity level (low/medium/high)
        confidence: Confidence score (0.0-1.0) based on metric distance from threshold
        related_metrics: List of metric names that triggered this threat
        metric_values: Dictionary of relevant metric values (for context only)
        triggered_by: List of human-readable conditions that triggered this threat
        description: Human-readable description of the threat
        missing_metrics: Number of expected metrics that were missing/invalid
        uncertainty_notes: List of issues encountered during threat detection
    """
    threat_id: str
    threat_name: str
    attack_type: str
    impacted_property: str  # privacy | utility | consistency
    severity: str           # low | medium | high
    confidence: float       # 0.0 - 1.0
    related_metrics: List[str]
    metric_values: Dict[str, Any]
    triggered_by: List[str]
    description: str
    missing_metrics: int = 0
    uncertainty_notes: List[str] = None

    def __post_init__(self):
        if self.uncertainty_notes is None:
            self.uncertainty_notes = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# THREAT CATALOG
# ============================================================================
# All metric names used in severity_rules are canonical names from schemas.py.
# ============================================================================

THREAT_CATALOG = {
    THREAT_MEMBERSHIP_INFERENCE: {
        "threat_name": "Membership Inference Attack",
        "attack_type": "membership_inference",
        "impacted_property": "privacy",
        "description": (
            "An attacker could determine whether a specific record was part of the "
            "original training dataset by analyzing synthetic data characteristics."
        ),
        # Uses canonical name F_MEMBERSHIP_INFERENCE_AUC = "membership_inference_auc"
        "metrics": [
            F_MEMBERSHIP_INFERENCE_AUC,
        ],
        "severity_rules": {
            "high":   lambda m: m.get(F_MEMBERSHIP_INFERENCE_AUC, 0) > 0.70,
            "medium": lambda m: m.get(F_MEMBERSHIP_INFERENCE_AUC, 0) > 0.60,
            "low":    lambda m: m.get(F_MEMBERSHIP_INFERENCE_AUC, 0) <= 0.60,
        },
        "thresholds": {
            "high": 0.70,
            "medium": 0.60,
            "baseline": 0.50,
        },
    },

    THREAT_RECORD_LINKAGE: {
        "threat_name": "Record Linkage / Re-identification",
        "attack_type": "record_linkage",
        "impacted_property": "privacy",
        "description": (
            "Near-duplicate records or exact matches could enable linking synthetic "
            "records back to original individuals, especially when combined with "
            "external datasets containing quasi-identifiers."
        ),
        # FIXED: was near_duplicates_rate / near_duplicates_count.
        # Now aligned with PrivacyRiskMetrics output: duplicates_rate / duplicates_count.
        "metrics": [
            F_DUPLICATES_COUNT,
            F_DUPLICATES_RATE,
            F_NEAREST_DISTANCES_MEAN,
        ],
        "severity_rules": {
            "high": lambda m: (
                m.get(F_DUPLICATES_RATE, 0) > 0.02 or
                m.get(F_DUPLICATES_COUNT, 0) > 10
            ),
            "medium": lambda m: (
                m.get(F_DUPLICATES_RATE, 0) > 0.01 or
                (m.get(F_NEAREST_DISTANCES_MEAN) is not None
                 and m.get(F_NEAREST_DISTANCES_MEAN, float("inf")) < 0.5)
            ),
            "low": lambda m: m.get(F_DUPLICATES_RATE, 0) <= 0.01,
        },
        "thresholds": {
            "high_rate": 0.02,
            "high_count": 10,
            "medium_rate": 0.01,
            "min_distance": 0.5,
        },
    },

    THREAT_ATTRIBUTE_INFERENCE: {
        "threat_name": "Attribute Inference Attack",
        "attack_type": "attribute_inference",
        "impacted_property": "privacy",
        "description": (
            "Strong correlations in synthetic data could allow attackers to infer "
            "sensitive attributes from known quasi-identifiers with high accuracy."
        ),
        # correlation_frobenius_norm is now produced by RuleEngine (from copula_distance)
        "metrics": [
            F_CORRELATION_FROBENIUS_NORM,
        ],
        "severity_rules": {
            "high":   lambda m: m.get(F_CORRELATION_FROBENIUS_NORM, 0) > 3.0,
            "medium": lambda m: m.get(F_CORRELATION_FROBENIUS_NORM, 0) > 1.5,
            "low":    lambda m: m.get(F_CORRELATION_FROBENIUS_NORM, 0) <= 1.5,
        },
        "thresholds": {
            "high": 3.0,
            "medium": 1.5,
            "baseline": 0.0,
        },
    },

    THREAT_PRIVACY_LEAKAGE: {
        "threat_name": "General Privacy Leakage",
        "attack_type": "privacy_leakage",
        "impacted_property": "privacy",
        "description": (
            "Overall privacy score indicates potential information leakage through "
            "various channels including record similarity, membership patterns, and "
            "nearest-neighbor proximity."
        ),
        "metrics": [
            F_PRIVACY_SCORE,
            F_LEAKAGE_RISK_LEVEL,
            F_NEAREST_DISTANCES_MEAN,
        ],
        "severity_rules": {
            "high":   lambda m: m.get(F_PRIVACY_SCORE, 1.0) < 0.60,
            "medium": lambda m: m.get(F_PRIVACY_SCORE, 1.0) < 0.80,
            "low":    lambda m: m.get(F_PRIVACY_SCORE, 1.0) >= 0.80,
        },
        "thresholds": {
            "high": 0.60,
            "medium": 0.80,
            "baseline": 1.0,
        },
    },

    THREAT_SEMANTIC_VIOLATION: {
        "threat_name": "Semantic Constraint Violation",
        "attack_type": "semantic_violation",
        "impacted_property": "consistency",
        "description": (
            "Violations of domain-specific business rules or cross-field constraints "
            "indicate synthetic data may not respect real-world invariants, potentially "
            "revealing generation artifacts or enabling detection."
        ),
        "metrics": [
            F_SEMANTIC_VIOLATIONS,
        ],
        "severity_rules": {
            "high":   lambda m: m.get(F_SEMANTIC_VIOLATIONS, 0) > 100,
            "medium": lambda m: m.get(F_SEMANTIC_VIOLATIONS, 0) > 10,
            "low":    lambda m: m.get(F_SEMANTIC_VIOLATIONS, 0) > 0,
        },
        "thresholds": {
            "high": 100,
            "medium": 10,
            "baseline": 0,
        },
    },

    THREAT_DISTRIBUTION_DRIFT: {
        "threat_name": "Statistical Distribution Drift",
        "attack_type": "distribution_drift",
        "impacted_property": "utility",
        "description": (
            "Significant divergence in statistical distributions could compromise "
            "the utility of synthetic data for downstream ML tasks."
        ),
        # distribution_shift_score is now produced by RuleEngine at top level.
        # statistical_drift is the categorical label.
        "metrics": [
            F_STATISTICAL_DRIFT,
            F_DISTRIBUTION_SHIFT_SCORE,
        ],
        "severity_rules": {
            "high": lambda m: (
                m.get(F_STATISTICAL_DRIFT, "").lower() == "high" or
                m.get(F_DISTRIBUTION_SHIFT_SCORE, 0) > 0.7
            ),
            "medium": lambda m: (
                m.get(F_STATISTICAL_DRIFT, "").lower() == "moderate" or
                m.get(F_DISTRIBUTION_SHIFT_SCORE, 0) > 0.4
            ),
            "low": lambda m: (
                m.get(F_STATISTICAL_DRIFT, "").lower() in ["low", "none"]
            ),
        },
        "thresholds": {
            "high_score": 0.7,
            "medium_score": 0.4,
            "baseline": 0.0,
        },
    },

    THREAT_CORRELATION_INCONSISTENCY: {
        "threat_name": "Correlation Structure Inconsistency",
        "attack_type": "correlation_inconsistency",
        "impacted_property": "utility",
        "description": (
            "Divergence in correlation patterns between synthetic and original data "
            "can compromise model performance and analytical validity."
        ),
        # FIXED: was correlation_frobenius_norm referencing an undefined metric.
        # Now uses the canonical name surfaced by RuleEngine from copula_distance.
        "metrics": [
            F_CORRELATION_FROBENIUS_NORM,
        ],
        "severity_rules": {
            "high":   lambda m: m.get(F_CORRELATION_FROBENIUS_NORM, 0) > 2.0,
            "medium": lambda m: m.get(F_CORRELATION_FROBENIUS_NORM, 0) > 1.0,
            "low":    lambda m: m.get(F_CORRELATION_FROBENIUS_NORM, 0) <= 1.0,
        },
        "thresholds": {
            "high": 2.0,
            "medium": 1.0,
            "baseline": 0.0,
        },
    },

    THREAT_UTILITY_DEGRADATION: {
        "threat_name": "ML Utility Degradation",
        "attack_type": "utility_degradation",
        "impacted_property": "utility",
        "description": (
            "Reduced utility score indicates that models trained on synthetic data "
            "significantly underperform compared to models trained on real data."
        ),
        "metrics": [
            F_UTILITY_SCORE,
        ],
        "severity_rules": {
            "high":   lambda m: m.get(F_UTILITY_SCORE, 1.0) is not None and m.get(F_UTILITY_SCORE, 1.0) < 0.70,
            "medium": lambda m: m.get(F_UTILITY_SCORE, 1.0) is not None and m.get(F_UTILITY_SCORE, 1.0) < 0.85,
            "low":    lambda m: m.get(F_UTILITY_SCORE) is None or m.get(F_UTILITY_SCORE, 1.0) >= 0.85,
        },
        "thresholds": {
            "high": 0.70,
            "medium": 0.85,
            "baseline": 1.0,
        },
    },
}


# ============================================================================
# CORE API FUNCTIONS
# ============================================================================

def map_metrics_to_threats(
    metrics_dict: Dict[str, Any],
    output_mode: Literal["summary", "detailed", "json"] = "detailed"
) -> Any:
    """
    Map evaluation metrics to threat signals.

    Args:
        metrics_dict: Complete metrics dictionary from RuleEngine
                      (must conform to MetricsSchema).
        output_mode:  "summary" | "detailed" | "json"

    Returns:
        Depends on output_mode:
        - "summary":  Dict with severity/property counts
        - "detailed": List[ThreatSignal]
        - "json":     Dict with serializable threat data
    """
    threat_signals = _compute_threat_signals(metrics_dict)

    if output_mode == "summary":
        return get_threat_summary(threat_signals)
    elif output_mode == "json":
        return {
            "threats": [s.to_dict() for s in threat_signals],
            "summary": get_threat_summary(threat_signals),
        }
    else:
        return threat_signals


def get_threat_summary(threat_signals: List[ThreatSignal]) -> Dict[str, Any]:
    """Generate a summary of detected threats grouped by severity and property."""
    summary = {
        "total_threats": len(threat_signals),
        "by_severity":  {"high": [], "medium": [], "low": []},
        "by_property":  {"privacy": [], "utility": [], "consistency": []},
        "threat_ids":   [t.threat_id for t in threat_signals],
    }

    for signal in threat_signals:
        summary["by_severity"][signal.severity].append(signal.threat_id)
        summary["by_property"][signal.impacted_property].append(signal.threat_id)

    summary["severity_counts"] = {
        k: len(v) for k, v in summary["by_severity"].items()
    }
    summary["property_counts"] = {
        k: len(v) for k, v in summary["by_property"].items()
    }

    return summary


def get_threat_by_id(threat_id: str) -> Optional[Dict[str, Any]]:
    return THREAT_CATALOG.get(threat_id)


def list_all_threats() -> List[str]:
    return list(THREAT_CATALOG.keys())


def get_metrics_for_threat(threat_id: str) -> Optional[List[str]]:
    threat_config = THREAT_CATALOG.get(threat_id)
    return threat_config["metrics"] if threat_config else None


# ============================================================================
# INTERNAL FUNCTIONS
# ============================================================================

def _compute_threat_signals(metrics_dict: Dict[str, Any]) -> List[ThreatSignal]:
    """
    Core threat detection logic. Returns data only, no side effects.
    """
    if metrics_dict is None:
        logger.warning("Received None metrics_dict, returning empty threat list")
        return []

    if not isinstance(metrics_dict, dict):
        logger.warning(
            f"Expected dict, got {type(metrics_dict)}, returning empty threat list"
        )
        return []

    # FIXED: use namespace-preserving flattening to prevent key collisions
    flat_metrics = _flatten_metrics_namespaced(metrics_dict)
    flat_metrics = _sanitize_metrics(flat_metrics)

    threat_signals = []

    for threat_id, threat_config in THREAT_CATALOG.items():
        uncertainty_notes = []
        expected_metrics = threat_config["metrics"]

        relevant_metrics = {}
        missing_count = 0

        for metric_name in expected_metrics:
            if metric_name in flat_metrics:
                value = flat_metrics[metric_name]
                if _is_valid_metric_value(value):
                    relevant_metrics[metric_name] = value
                else:
                    missing_count += 1
                    uncertainty_notes.append(f"Invalid value for {metric_name}")
            else:
                missing_count += 1

        if not relevant_metrics:
            continue

        try:
            severity = _evaluate_severity(flat_metrics, threat_config["severity_rules"])
        except Exception as e:
            logger.warning(f"Error evaluating severity for {threat_id}: {e}")
            uncertainty_notes.append(f"Severity evaluation failed: {str(e)[:50]}")
            severity = None

        if not severity:
            continue

        try:
            confidence = _compute_confidence(flat_metrics, threat_config, severity)
        except Exception as e:
            logger.warning(f"Error computing confidence for {threat_id}: {e}")
            confidence = 0.5
            uncertainty_notes.append("Confidence calculation failed")

        try:
            triggered_by = _explain_trigger_conditions(
                flat_metrics, threat_config, severity
            )
        except Exception as e:
            logger.warning(f"Error explaining triggers for {threat_id}: {e}")
            triggered_by = ["Triggered by threshold (details unavailable)"]
            uncertainty_notes.append("Trigger explanation failed")

        signal = ThreatSignal(
            threat_id=threat_id,
            threat_name=threat_config["threat_name"],
            attack_type=threat_config["attack_type"],
            impacted_property=threat_config["impacted_property"],
            severity=severity,
            confidence=confidence,
            related_metrics=list(relevant_metrics.keys()),
            metric_values=relevant_metrics,
            triggered_by=triggered_by,
            description=threat_config["description"],
            missing_metrics=missing_count,
            uncertainty_notes=uncertainty_notes,
        )
        threat_signals.append(signal)

    return threat_signals


def _flatten_metrics_namespaced(metrics_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested metrics using a collision-safe strategy.

    Priority order (highest to lowest):
      1. Top-level keys are taken AS-IS (they conform to MetricsSchema).
      2. Nested keys are inserted with namespace prefix ONLY if the bare key
         does not already exist at the top level.
      3. Known sub-dict keys (privacy_risk, statistical_fidelity) are
         namespaced explicitly to prevent overwrites.

    This preserves:
      - All canonical MetricsSchema keys at the top level
      - Sub-dict values accessible via bare key when unambiguous
      - Namespaced access (e.g., "privacy_risk.duplicates_rate") when needed
    """
    flat: Dict[str, Any] = {}

    if not metrics_dict:
        return flat

    # Pass 1: insert all top-level keys (canonical schema fields have priority)
    for key, value in metrics_dict.items():
        flat[key] = value

    # Pass 2: insert nested keys with namespaced fallback
    for key, value in metrics_dict.items():
        if not isinstance(value, dict):
            continue
        for nested_key, nested_value in value.items():
            namespaced = f"{key}.{nested_key}"
            # Always store the namespaced version
            flat[namespaced] = nested_value
            # Only promote bare key if it does not already exist at top level
            if nested_key not in flat:
                flat[nested_key] = nested_value

    return flat


# Keep old name as alias for backward compatibility
def _flatten_metrics(metrics_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible alias for _flatten_metrics_namespaced."""
    return _flatten_metrics_namespaced(metrics_dict)


def _is_valid_metric_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        import math
        if math.isnan(value) or math.isinf(value):
            return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _sanitize_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    import math
    sanitized = {}
    for key, value in metrics.items():
        if value is None:
            continue
        if isinstance(value, (int, float)):
            if math.isnan(value) or math.isinf(value):
                logger.debug(f"Skipping invalid numeric value for {key}: {value}")
                continue
        sanitized[key] = value
    return sanitized


def _evaluate_severity(
    metrics: Dict[str, Any],
    severity_rules: Dict[str, callable]
) -> Optional[str]:
    for severity in ["high", "medium", "low"]:
        if severity in severity_rules:
            try:
                if severity_rules[severity](metrics):
                    return severity
            except Exception as e:
                logger.warning(f"Error evaluating severity rule for {severity}: {e}")
    return None


def _compute_confidence(
    metrics: Dict[str, Any],
    threat_config: Dict[str, Any],
    severity: str
) -> float:
    threat_id = threat_config.get("attack_type", "")
    thresholds = threat_config.get("thresholds", {})

    if threat_id == "membership_inference":
        auc = metrics.get(F_MEMBERSHIP_INFERENCE_AUC, 0.5)
        baseline = thresholds.get("baseline", 0.5)
        distance = abs(auc - baseline)
        confidence = min(distance * 2.0, 1.0)

    elif threat_id == "record_linkage":
        dup_rate = metrics.get(F_DUPLICATES_RATE, 0)
        confidence = min(dup_rate * 50.0, 1.0)

    elif threat_id == "privacy_leakage":
        score = metrics.get(F_PRIVACY_SCORE, 1.0)
        baseline = thresholds.get("baseline", 1.0)
        distance = baseline - score
        confidence = min(distance / 0.4, 1.0)

    elif threat_id == "semantic_violation":
        violations = metrics.get(F_SEMANTIC_VIOLATIONS, 0)
        if violations == 0:
            confidence = 0.0
        else:
            import math
            confidence = min(math.log10(violations + 1) / 3.0, 1.0)

    elif threat_id == "distribution_drift":
        shift = metrics.get(F_DISTRIBUTION_SHIFT_SCORE, 0)
        confidence = min(float(shift), 1.0)

    elif threat_id in [
        "utility_degradation", "correlation_inconsistency", "attribute_inference"
    ]:
        confidence = {"low": 0.3, "medium": 0.6, "high": 0.9}.get(severity, 0.5)

    else:
        confidence = {"low": 0.4, "medium": 0.7, "high": 0.9}.get(severity, 0.5)

    return round(confidence, 3)


def _explain_trigger_conditions(
    metrics: Dict[str, Any],
    threat_config: Dict[str, Any],
    severity: str
) -> List[str]:
    conditions = []
    threat_id = threat_config.get("attack_type", "")

    if threat_id == "membership_inference":
        auc = metrics.get(F_MEMBERSHIP_INFERENCE_AUC)
        if auc is not None:
            if severity == "high":
                conditions.append(
                    f"{F_MEMBERSHIP_INFERENCE_AUC} ({auc:.3f}) > 0.70"
                )
            elif severity == "medium":
                conditions.append(
                    f"{F_MEMBERSHIP_INFERENCE_AUC} ({auc:.3f}) > 0.60"
                )
            else:
                conditions.append(
                    f"{F_MEMBERSHIP_INFERENCE_AUC} ({auc:.3f}) detected"
                )

    elif threat_id == "record_linkage":
        rate = metrics.get(F_DUPLICATES_RATE)
        count = metrics.get(F_DUPLICATES_COUNT)
        distance = metrics.get(F_NEAREST_DISTANCES_MEAN)

        if rate is not None and rate > 0.01:
            conditions.append(f"{F_DUPLICATES_RATE} ({rate:.4f}) > threshold")
        if count is not None and count > 5:
            conditions.append(f"{F_DUPLICATES_COUNT} ({count}) detected")
        if distance is not None and distance < 1.0:
            conditions.append(f"{F_NEAREST_DISTANCES_MEAN} ({distance:.2f}) < 1.0")

    elif threat_id == "privacy_leakage":
        score = metrics.get(F_PRIVACY_SCORE)
        if score is not None:
            if severity == "high":
                conditions.append(f"{F_PRIVACY_SCORE} ({score:.3f}) < 0.60")
            elif severity == "medium":
                conditions.append(f"{F_PRIVACY_SCORE} ({score:.3f}) < 0.80")
            else:
                conditions.append(f"{F_PRIVACY_SCORE} ({score:.3f}) below optimal")

    elif threat_id == "semantic_violation":
        violations = metrics.get(F_SEMANTIC_VIOLATIONS, 0)
        if violations > 0:
            conditions.append(f"{F_SEMANTIC_VIOLATIONS} ({violations}) detected")

    elif threat_id == "distribution_drift":
        drift = metrics.get(F_STATISTICAL_DRIFT, "")
        shift = metrics.get(F_DISTRIBUTION_SHIFT_SCORE)
        if drift.lower() in ["high", "moderate"]:
            conditions.append(f"{F_STATISTICAL_DRIFT} = {drift}")
        if shift is not None and shift > 0.1:
            conditions.append(f"{F_DISTRIBUTION_SHIFT_SCORE} ({shift:.3f}) > 0.1")

    elif threat_id == "correlation_inconsistency":
        corr_diff = metrics.get(F_CORRELATION_FROBENIUS_NORM)
        if corr_diff is not None:
            if severity == "high":
                conditions.append(
                    f"{F_CORRELATION_FROBENIUS_NORM} ({corr_diff:.2f}) > 2.0"
                )
            elif severity == "medium":
                conditions.append(
                    f"{F_CORRELATION_FROBENIUS_NORM} ({corr_diff:.2f}) > 1.0"
                )
            else:
                conditions.append(
                    f"{F_CORRELATION_FROBENIUS_NORM} ({corr_diff:.2f}) detected"
                )

    elif threat_id == "attribute_inference":
        corr = metrics.get(F_CORRELATION_FROBENIUS_NORM)
        if corr is not None:
            if severity == "high":
                conditions.append(
                    f"{F_CORRELATION_FROBENIUS_NORM} ({corr:.2f}) > 3.0"
                )
            elif severity == "medium":
                conditions.append(
                    f"{F_CORRELATION_FROBENIUS_NORM} ({corr:.2f}) > 1.5"
                )

    elif threat_id == "utility_degradation":
        util = metrics.get(F_UTILITY_SCORE)
        if util is not None:
            if severity == "high":
                conditions.append(f"{F_UTILITY_SCORE} ({util:.3f}) < 0.70")
            elif severity == "medium":
                conditions.append(f"{F_UTILITY_SCORE} ({util:.3f}) < 0.85")
            else:
                conditions.append(f"{F_UTILITY_SCORE} ({util:.3f}) below optimal")

    if not conditions:
        conditions.append(f"Detected based on {severity} severity threshold")

    return conditions


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Threat ID Constants
    "THREAT_MEMBERSHIP_INFERENCE",
    "THREAT_RECORD_LINKAGE",
    "THREAT_ATTRIBUTE_INFERENCE",
    "THREAT_PRIVACY_LEAKAGE",
    "THREAT_SEMANTIC_VIOLATION",
    "THREAT_DISTRIBUTION_DRIFT",
    "THREAT_CORRELATION_INCONSISTENCY",
    "THREAT_UTILITY_DEGRADATION",
    # Classes
    "ThreatSignal",
    # Core Functions
    "map_metrics_to_threats",
    "get_threat_summary",
    # Utilities
    "get_threat_by_id",
    "list_all_threats",
    "get_metrics_for_threat",
    # Catalog
    "THREAT_CATALOG",
]
