"""
Rule Engine - Deterministic execution engine for governance

Orchestrates:
- Statistical fidelity metrics (structural contracts, distribution shift, mode collapse)
- Privacy risk assessment (duplicate detection, membership leakage)
- Derived metric computation (privacy_score, leakage_risk_level, statistical_drift, ...)
- Full governance pipeline (threat mapping -> aggregation -> GovernanceResult)

CRITICAL: This engine is DETERMINISTIC ONLY.
- NO LLM calls
- NO AI-based decisions
- Pure metric computation and rule execution
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
import logging
import time

from .metrics import (
    StatisticalFidelityMetrics,
    PrivacyRiskMetrics,
)
from .data_profiles import DataProfiler, DatasetProfile
from .audit_logger import AuditLogger
from .schemas import (
    MetricsSchema,
    F_PRIVACY_SCORE,
    F_LEAKAGE_RISK_LEVEL,
    F_DUPLICATES_RATE,
    F_DUPLICATES_COUNT,
    F_MEMBERSHIP_INFERENCE_AUC,
    F_DISTRIBUTION_SHIFT_SCORE,
    F_MODE_COLLAPSE_PROBABILITY,
    F_CORRELATION_FROBENIUS_NORM,
    F_STATISTICAL_DRIFT,
    F_SEMANTIC_VIOLATIONS,
    F_NEAREST_DISTANCES_MEAN,
    F_PRIVACY_RISK,
    F_STATISTICAL_FIDELITY,
    F_GOVERNANCE_RESULT,
    RISK_CRITICAL,
    RISK_WARNING,
    RISK_LOW,
    DRIFT_HIGH,
    DRIFT_MODERATE,
    DRIFT_LOW,
    DRIFT_NONE,
    validate_metrics,
)

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Deterministic rule engine for synthetic data governance.

    Computes all metrics without any AI/LLM involvement.
    Produces structured, schema-conformant outputs for downstream consumers.

    Pipeline:
        DataFrame
        -> StatisticalFidelityMetrics + PrivacyRiskMetrics
        -> _compute_derived_metrics()          # fills schema gaps
        -> evaluate_governance()               # threat mapping + aggregation
        -> final dict conforming to MetricsSchema
    """

    def __init__(
        self,
        config: Optional[object] = None,
        audit_logger: Optional[AuditLogger] = None
    ):
        self.config = config
        self.audit_logger = audit_logger or AuditLogger()

        # Initialize metric calculators
        self.stat_fidelity = StatisticalFidelityMetrics()
        self.privacy_risk = PrivacyRiskMetrics()
        self.profiler = DataProfiler()

    # ------------------------------------------------------------------
    # INTERNAL: audit helper -- no monkey-patching
    # ------------------------------------------------------------------

    def _log_metric(
        self,
        eval_id: str,
        name: str,
        value: Any,
        time_ms: float = 0.0
    ) -> None:
        """
        Write a single metric to the audit log.

        Uses eval_id explicitly rather than mutating the shared AuditLogger.
        """
        if self.audit_logger:
            self.audit_logger.log_metric_computation(
                eval_id=eval_id,
                metric_name=name,
                value=value,
                computation_time_ms=time_ms,
            )

    # ------------------------------------------------------------------
    # Public: individual metric groups
    # ------------------------------------------------------------------

    def compute_statistical_fidelity(
        self,
        synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[DatasetProfile] = None,
        eval_id: str = ""
    ) -> Dict[str, Any]:
        """Compute all statistical fidelity metrics."""
        start_time = time.time()

        metrics = self.stat_fidelity.compute_all(
            synthetic_df, original_df, original_profile
        )

        computation_time = (time.time() - start_time) * 1000

        for metric_name, value in metrics.items():
            if isinstance(value, (int, float, str)):
                self._log_metric(
                    eval_id, f"stat_fidelity.{metric_name}", value, computation_time
                )

        return metrics

    def compute_privacy_risk(
        self,
        synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[DatasetProfile] = None,
        eval_id: str = ""
    ) -> Dict[str, Any]:
        """Compute privacy risk metrics."""
        start_time = time.time()

        metrics = self.privacy_risk.compute_all(
            synthetic_df, original_df, original_profile
        )

        computation_time = (time.time() - start_time) * 1000

        self._log_metric(
            eval_id,
            "privacy.duplicates_rate",
            metrics.get(F_DUPLICATES_RATE, 0.0),
            computation_time,
        )

        return metrics

    # ------------------------------------------------------------------
    # Internal: derived metric computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_membership_inference_auc(
        privacy_metrics: Dict[str, Any]
    ) -> Optional[float]:
        """
        Derive membership_inference_auc from DOMIAS log-likelihood ratio scores.

        The DOMIAS implementation returns raw LR statistics but never calls
        _auc_from_scores(). We approximate AUC from the mean LR using a
        logistic transform:

            auc = sigmoid(0.5 * lr_mean)

        where sigmoid(0) = 0.5 (random guessing baseline).
        A positive mean LR indicates the synthetic model assigns higher
        likelihood to training records than the population model does,
        which is the core signal of membership inference risk.

        Returns:
            Float in [0.0, 1.0], or None if DOMIAS scores are unavailable.
        """
        lr_mean = privacy_metrics.get("lr_distribution_mean")
        lr_std = privacy_metrics.get("lr_distribution_std")

        if lr_mean is None:
            return None

        import math
        try:
            auc = 1.0 / (1.0 + math.exp(-0.5 * float(lr_mean)))
            return round(float(np.clip(auc, 0.0, 1.0)), 4)
        except (OverflowError, ValueError):
            return 0.5

    @staticmethod
    def _compute_privacy_score(
        duplicates_rate: float,
        membership_inference_auc: Optional[float],
        nearest_distances_mean: Optional[float],
    ) -> float:
        """
        Deterministic composite privacy score in [0.0, 1.0].

        Higher = better privacy (less leakage).

        Components and weights:
          duplicates_rate            50%  -- direct record re-identification risk
          membership_inference_auc   30%  -- inference attack risk above baseline
          nearest_distances_mean     20%  -- proximity risk in feature space

        All components are normalised to [0,1] risk before combining.
        """
        # Component 1: duplicate risk (direct proportion)
        dup_risk = float(np.clip(duplicates_rate, 0.0, 1.0))

        # Component 2: MIA risk (AUC=0.5 is baseline/no-risk)
        if membership_inference_auc is not None:
            mia_risk = float(
                np.clip((membership_inference_auc - 0.5) / 0.5, 0.0, 1.0)
            )
        else:
            mia_risk = 0.0  # no additional penalty when not computable

        # Component 3: proximity risk
        # Smaller mean NN distance in standardised space -> higher risk.
        # Safe distance threshold = 2.0 (empirical for standardised data).
        if nearest_distances_mean is not None and nearest_distances_mean >= 0:
            prox_risk = float(
                np.clip(1.0 - nearest_distances_mean / 2.0, 0.0, 1.0)
            )
        else:
            prox_risk = 0.0

        composite_risk = (
            dup_risk  * 0.5 +
            mia_risk  * 0.3 +
            prox_risk * 0.2
        )

        return round(float(np.clip(1.0 - composite_risk, 0.0, 1.0)), 4)

    @staticmethod
    def _compute_leakage_risk_level(privacy_score: float) -> str:
        """
        Map privacy_score to a categorical risk level.

        Thresholds (deterministic, auditable, aligned with thresholds.yaml):
          privacy_score >= 0.80 -> "low"
          privacy_score >= 0.60 -> "warning"
          privacy_score <  0.60 -> "critical"
        """
        if privacy_score >= 0.80:
            return RISK_LOW
        elif privacy_score >= 0.60:
            return RISK_WARNING
        else:
            return RISK_CRITICAL

    @staticmethod
    def _compute_statistical_drift(distribution_shift_score: Optional[float]) -> str:
        """
        Convert float distribution_shift_score to categorical drift label.

        Thresholds:
          >= 0.7 -> "high"
          >= 0.4 -> "moderate"
          >= 0.2 -> "low"
          <  0.2 -> "none"

        Returns "none" when score is unavailable.
        """
        if distribution_shift_score is None:
            return DRIFT_NONE
        s = float(distribution_shift_score)
        if s >= 0.7:
            return DRIFT_HIGH
        elif s >= 0.4:
            return DRIFT_MODERATE
        elif s >= 0.2:
            return DRIFT_LOW
        else:
            return DRIFT_NONE

    @staticmethod
    def _compute_semantic_violations(
        stat_fidelity_metrics: Dict[str, Any]
    ) -> int:
        """
        Count structural contract violations from column_violations.

        A violation is a column whose JS divergence flag is True in the
        structural_contract_validation output of StatisticalFidelityMetrics.
        """
        structural = stat_fidelity_metrics.get(
            "structural_contract_validation", {}
        )
        col_violations = structural.get("column_violations", {})

        count = 0
        for _col, detail in col_violations.items():
            if isinstance(detail, dict) and detail.get("violated", False):
                count += 1

        return count

    def _compute_derived_metrics(
        self,
        result: Dict[str, Any],
        privacy_metrics: Dict[str, Any],
        stat_fidelity_metrics: Dict[str, Any],
        eval_id: str,
        original_df_present: bool = False,
    ) -> Dict[str, Any]:
        """
        Compute all derived schema fields that the raw metric engines do not
        produce, and inject them into result in-place.

        This is the bridge between raw engine output and MetricsSchema.

        Args:
            result:                   Accumulation dict to mutate and return.
            privacy_metrics:          Output of PrivacyRiskMetrics.compute_all().
            stat_fidelity_metrics:    Output of StatisticalFidelityMetrics.compute_all().
            eval_id:                  Evaluation ID for audit logging.
            original_df_present:      True when original_df was supplied to the
                                      outer evaluate_synthetic_data() call.
                                      Used to set the privacy_score_reliable flag.
        """

        # --- membership_inference_auc ---
        mia_auc = self._compute_membership_inference_auc(privacy_metrics)
        result[F_MEMBERSHIP_INFERENCE_AUC] = mia_auc
        self._log_metric(eval_id, F_MEMBERSHIP_INFERENCE_AUC, mia_auc)

        # --- duplicates_count / duplicates_rate (promote to top-level) ---
        result[F_DUPLICATES_RATE] = float(
            privacy_metrics.get(F_DUPLICATES_RATE, 0.0)
        )
        result[F_DUPLICATES_COUNT] = int(
            privacy_metrics.get("duplicates_count", 0)
        )
        result[F_NEAREST_DISTANCES_MEAN] = privacy_metrics.get(
            "nearest_distances_mean"
        )

        # --- privacy_score ---
        privacy_score = self._compute_privacy_score(
            duplicates_rate=result[F_DUPLICATES_RATE],
            membership_inference_auc=mia_auc,
            nearest_distances_mean=result[F_NEAREST_DISTANCES_MEAN],
        )
        result[F_PRIVACY_SCORE] = privacy_score
        self._log_metric(eval_id, F_PRIVACY_SCORE, privacy_score)

        # --- privacy_score reliability flag ---
        # When original_df is absent every privacy component (duplicates_rate,
        # membership_inference_auc, nearest_distances_mean) defaults to 0 / None,
        # which drives privacy_score to 1.0.  That value is mathematically
        # correct given the inputs but does NOT mean the data is safe — it
        # means there was nothing to compare against.  Flag this explicitly so
        # downstream callers (and the VS Code extension UI) can surface a
        # warning rather than a false green status.
        if original_df_present:
            result["privacy_score_reliable"] = True
            result["privacy_score_note"] = (
                "privacy_score is based on comparison with the supplied "
                "original dataset."
            )
        else:
            result["privacy_score_reliable"] = False
            result["privacy_score_note"] = (
                "privacy_score=1.0 reflects absence of reference data, "
                "not confirmed safety. "
                "Provide original_df for a meaningful privacy evaluation."
            )
        self._log_metric(eval_id, "privacy_score_reliable", result["privacy_score_reliable"])

        # --- leakage_risk_level ---
        risk_level = self._compute_leakage_risk_level(privacy_score)
        result[F_LEAKAGE_RISK_LEVEL] = risk_level
        self._log_metric(eval_id, F_LEAKAGE_RISK_LEVEL, risk_level)

        # --- distribution_shift_score ---
        raw_shift = (
            stat_fidelity_metrics
            .get("distribution_shift", {})
            .get("shift_score")
        )
        result[F_DISTRIBUTION_SHIFT_SCORE] = raw_shift
        self._log_metric(eval_id, F_DISTRIBUTION_SHIFT_SCORE, raw_shift)

        # --- statistical_drift (categorical label) ---
        stat_drift = self._compute_statistical_drift(raw_shift)
        result[F_STATISTICAL_DRIFT] = stat_drift
        self._log_metric(eval_id, F_STATISTICAL_DRIFT, stat_drift)

        # --- mode_collapse_probability ---
        mc_prob = (
            stat_fidelity_metrics
            .get("mode_collapse", {})
            .get("collapse_probability")
        )
        result[F_MODE_COLLAPSE_PROBABILITY] = mc_prob
        self._log_metric(eval_id, F_MODE_COLLAPSE_PROBABILITY, mc_prob)

        # --- correlation_frobenius_norm ---
        # StatisticalFidelityMetrics stores this as "copula_distance" inside
        # the distribution_shift sub-dict. We surface it under the canonical
        # schema name so threat_mapping can find it.
        copula_dist = (
            stat_fidelity_metrics
            .get("distribution_shift", {})
            .get("copula_distance")
        )
        result[F_CORRELATION_FROBENIUS_NORM] = copula_dist
        self._log_metric(eval_id, F_CORRELATION_FROBENIUS_NORM, copula_dist)

        # --- semantic_violations ---
        sem_violations = self._compute_semantic_violations(stat_fidelity_metrics)
        result[F_SEMANTIC_VIOLATIONS] = sem_violations
        self._log_metric(eval_id, F_SEMANTIC_VIOLATIONS, sem_violations)

        # --- utility_score (placeholder; not yet computable) ---
        result.setdefault("utility_score", None)

        return result

    # ------------------------------------------------------------------
    # Public: full evaluation
    # ------------------------------------------------------------------

    def evaluate_synthetic_data(
        self,
        synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[DatasetProfile] = None,
        eval_id: Optional[str] = None,
        target_column: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive, end-to-end evaluation of synthetic data.

        Pipeline:
            synthetic_df (+ optional original_df)
            -> StatisticalFidelityMetrics.compute_all()
            -> PrivacyRiskMetrics.compute_all()
            -> _compute_derived_metrics()    (fills MetricsSchema gaps)
            -> evaluate_governance()         (threat mapping + aggregation)
            -> schema-conformant result dict

        Args:
            synthetic_df:     Synthetic dataset to evaluate.
            original_df:      Optional original reference dataset.
            original_profile: Optional pre-computed DatasetProfile.
            eval_id:          Optional evaluation ID; auto-generated if absent.
            target_column:    Reserved for future utility metric computation.

        Returns:
            Dict conforming to MetricsSchema with a 'governance_result' key.
        """
        import uuid
        from datetime import datetime

        eval_id = eval_id or f"eval_{uuid.uuid4().hex[:8]}"

        logger.info(f"Starting evaluation {eval_id}")

        result: Dict[str, Any] = {
            "eval_id": eval_id,
            "timestamp": datetime.now().isoformat(),
            "synthetic_rows": len(synthetic_df),
            "synthetic_columns": len(synthetic_df.columns),
        }

        # ----------------------------------------------------------------
        # 1. Statistical Fidelity
        # ----------------------------------------------------------------
        logger.info("Computing statistical fidelity...")
        stat_fidelity_metrics = self.compute_statistical_fidelity(
            synthetic_df, original_df, original_profile, eval_id=eval_id
        )
        result[F_STATISTICAL_FIDELITY] = stat_fidelity_metrics

        # ----------------------------------------------------------------
        # 2. Privacy Risk
        # ----------------------------------------------------------------
        logger.info("Computing privacy risk...")
        privacy_metrics = self.compute_privacy_risk(
            synthetic_df, original_df, original_profile, eval_id=eval_id
        )
        result[F_PRIVACY_RISK] = privacy_metrics

        # ----------------------------------------------------------------
        # 3. Derived Metrics (fills MetricsSchema gaps)
        # ----------------------------------------------------------------
        logger.info("Computing derived metrics...")
        result = self._compute_derived_metrics(
            result, privacy_metrics, stat_fidelity_metrics, eval_id,
            original_df_present=(original_df is not None),
        )

        # ----------------------------------------------------------------
        # 4. Governance Pipeline (threat mapping -> aggregation)
        # ----------------------------------------------------------------
        logger.info("Running governance pipeline...")
        try:
            from .api import evaluate_governance
            governance_result = evaluate_governance(result, output_mode="full")
            result[F_GOVERNANCE_RESULT] = governance_result.to_dict()
            risk_level_out = (
                governance_result.dataset_risk_summary.overall_risk_level
                if governance_result.dataset_risk_summary else "unknown"
            )
            self._log_metric(
                eval_id, "governance.overall_risk_level", risk_level_out
            )
        except Exception as exc:
            logger.error(
                f"Governance pipeline failed for {eval_id}: {exc}", exc_info=True
            )
            result[F_GOVERNANCE_RESULT] = {
                "error": str(exc),
                "overall_risk_level": "unknown",
            }

        # ----------------------------------------------------------------
        # 5. Schema validation (log warnings only, never raise)
        # ----------------------------------------------------------------
        schema_errors = validate_metrics(result)
        if schema_errors:
            for err in schema_errors:
                logger.warning(f"Schema validation [{eval_id}]: {err}")

        logger.info(
            f"Evaluation {eval_id} complete -- "
            f"privacy_score={result.get(F_PRIVACY_SCORE):.4f}, "
            f"risk={result.get(F_LEAKAGE_RISK_LEVEL)}, "
            f"drift={result.get(F_STATISTICAL_DRIFT)}"
        )

        return result
