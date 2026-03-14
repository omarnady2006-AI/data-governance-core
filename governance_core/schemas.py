"""
Metric Schema Contract
======================

Defines the canonical MetricsSchema that is the single source of truth
for all metric names and types flowing between:

  RuleEngine → Threat Mapping → Threat Aggregation → Governance Result
                                                    → GovernanceAgent
                                                    → CLI

RULES:
- All metric keys produced by RuleEngine.evaluate_synthetic_data() must
  conform to this schema.
- All consumers (threat_mapping, governance_agent, cli) must reference
  keys defined here — never magic strings.
- Optional fields are explicitly typed as Optional so consumers know
  when a value may be absent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Canonical field name constants
# ---------------------------------------------------------------------------
# Import these wherever a metric key is referenced to eliminate magic strings.

F_PRIVACY_SCORE              = "privacy_score"
F_LEAKAGE_RISK_LEVEL         = "leakage_risk_level"
F_DUPLICATES_RATE            = "duplicates_rate"
F_DUPLICATES_COUNT           = "duplicates_count"
F_MEMBERSHIP_INFERENCE_AUC   = "membership_inference_auc"
F_DISTRIBUTION_SHIFT_SCORE   = "distribution_shift_score"
F_MODE_COLLAPSE_PROBABILITY  = "mode_collapse_probability"
F_CORRELATION_FROBENIUS_NORM = "correlation_frobenius_norm"
F_UTILITY_SCORE              = "utility_score"
F_STATISTICAL_DRIFT          = "statistical_drift"
F_SEMANTIC_VIOLATIONS        = "semantic_violations"
F_NEAREST_DISTANCES_MEAN     = "nearest_distances_mean"

# Sub-dict keys
F_PRIVACY_RISK               = "privacy_risk"
F_STATISTICAL_FIDELITY       = "statistical_fidelity"
F_GOVERNANCE_RESULT          = "governance_result"

# leakage_risk_level allowed values
RISK_CRITICAL = "critical"
RISK_WARNING  = "warning"
RISK_LOW      = "low"

# statistical_drift allowed values
DRIFT_HIGH     = "high"
DRIFT_MODERATE = "moderate"
DRIFT_LOW      = "low"
DRIFT_NONE     = "none"


# ---------------------------------------------------------------------------
# MetricsSchema
# ---------------------------------------------------------------------------

class MetricsSchema(TypedDict, total=False):
    """
    Canonical schema for the metrics dict produced by
    RuleEngine.evaluate_synthetic_data() and consumed by all downstream
    modules.

    All required fields are always present in a valid result.
    Optional fields are absent when the required data (original_df) was
    not supplied.
    """

    # --- Identity ---
    eval_id: str
    timestamp: str
    synthetic_rows: int
    synthetic_columns: int

    # --- Privacy (always present) ---
    privacy_score: float             # 0.0 (worst) → 1.0 (best)
    leakage_risk_level: str          # "critical" | "warning" | "low"
    duplicates_rate: float           # fraction of synthetic rows near-duplicate
    duplicates_count: int            # absolute count

    # --- Privacy (present when original_df supplied) ---
    membership_inference_auc: Optional[float]   # None when original absent
    nearest_distances_mean: Optional[float]

    # --- Statistical fidelity (present when original_df supplied) ---
    distribution_shift_score: Optional[float]   # 0.0 → 1.0
    mode_collapse_probability: Optional[float]  # 0.0 → 1.0
    correlation_frobenius_norm: Optional[float] # Frobenius norm of Spearman Δcorr

    # --- Derived categorical labels (always present) ---
    statistical_drift: str           # "high" | "moderate" | "low" | "none"
    semantic_violations: int         # count of structural contract violations

    # --- Utility (optional, future extension) ---
    utility_score: Optional[float]

    # --- Sub-dicts (kept for backward compatibility) ---
    privacy_risk: Dict[str, Any]
    statistical_fidelity: Dict[str, Any]

    # --- Governance pipeline result ---
    governance_result: Dict[str, Any]


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = (
    F_PRIVACY_SCORE,
    F_LEAKAGE_RISK_LEVEL,
    F_DUPLICATES_RATE,
    F_DUPLICATES_COUNT,
    F_STATISTICAL_DRIFT,
    F_SEMANTIC_VIOLATIONS,
)


def validate_metrics(metrics: Dict[str, Any]) -> List[str]:
    """
    Check that all required fields are present and have the correct type.

    Returns:
        List of validation error strings. Empty list means schema is valid.
    """
    errors: List[str] = []

    for field in REQUIRED_FIELDS:
        if field not in metrics:
            errors.append(f"Missing required field: '{field}'")

    # Type checks for fields that are present
    if F_PRIVACY_SCORE in metrics:
        v = metrics[F_PRIVACY_SCORE]
        if not isinstance(v, (int, float)):
            errors.append(f"'{F_PRIVACY_SCORE}' must be numeric, got {type(v)}")
        elif not (0.0 <= float(v) <= 1.0):
            errors.append(
                f"'{F_PRIVACY_SCORE}' must be in [0.0, 1.0], got {v}"
            )

    if F_LEAKAGE_RISK_LEVEL in metrics:
        v = metrics[F_LEAKAGE_RISK_LEVEL]
        if v not in (RISK_CRITICAL, RISK_WARNING, RISK_LOW):
            errors.append(
                f"'{F_LEAKAGE_RISK_LEVEL}' must be one of "
                f"'critical'/'warning'/'low', got '{v}'"
            )

    if F_STATISTICAL_DRIFT in metrics:
        v = metrics[F_STATISTICAL_DRIFT]
        if v not in (DRIFT_HIGH, DRIFT_MODERATE, DRIFT_LOW, DRIFT_NONE):
            errors.append(
                f"'{F_STATISTICAL_DRIFT}' must be one of "
                f"'high'/'moderate'/'low'/'none', got '{v}'"
            )

    return errors
