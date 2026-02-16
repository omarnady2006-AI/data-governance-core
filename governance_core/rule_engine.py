"""
Rule Engine - Deterministic execution engine for governance

Orchestrates:
- Statistical fidelity metrics (structural contracts, distribution shift, mode collapse)
- Privacy risk assessment (duplicate detection, membership leakage)

CRITICAL: This engine is DETERMINISTIC ONLY.
- NO LLM calls
- NO AI-based decisions
- Pure metric computation and rule execution
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from pathlib import Path
import logging
import time

from .metrics import (
    StatisticalFidelityMetrics,
    PrivacyRiskMetrics,
)
from .data_profiles import DataProfiler, DatasetProfile
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Deterministic rule engine for synthetic data governance.

    Computes all metrics without any AI/LLM involvement.
    Produces structured, score-based outputs for GovernanceAgent interpretation.
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

    def compute_statistical_fidelity(
        self,
        synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[DatasetProfile] = None
    ) -> Dict[str, Any]:
        """Compute all statistical fidelity metrics."""
        start_time = time.time()

        metrics = self.stat_fidelity.compute_all(
            synthetic_df, original_df, original_profile
        )

        computation_time = (time.time() - start_time) * 1000

        if self.audit_logger:
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float, str)):
                    self.audit_logger.log_metric_computation(
                        eval_id="",
                        metric_name=f"stat_fidelity.{metric_name}",
                        value=value,
                        computation_time_ms=computation_time
                    )

        return metrics

    def compute_privacy_risk(
        self,
        synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[DatasetProfile] = None
    ) -> Dict[str, Any]:
        """Compute privacy risk metrics."""
        start_time = time.time()

        metrics = self.privacy_risk.compute_all(
            synthetic_df, original_df, original_profile
        )

        computation_time = (time.time() - start_time) * 1000

        if self.audit_logger:
            self.audit_logger.log_metric_computation(
                eval_id="",
                metric_name="privacy.duplicates_rate",
                value=metrics.get("duplicates_rate", 0.0),
                computation_time_ms=computation_time
            )

        return metrics

    def evaluate_synthetic_data(
        self,
        synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[DatasetProfile] = None,
        eval_id: Optional[str] = None,
        target_column: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive evaluation of synthetic data.

        Computes ALL metrics and returns structured result.
        """
        import uuid
        from datetime import datetime

        eval_id = eval_id or f"eval_{uuid.uuid4().hex[:8]}"

        logger.info(f"Starting evaluation {eval_id}")

        # Update audit logger with eval_id
        original_log_metric = self.audit_logger.log_metric_computation
        def log_with_id(*args, **kwargs):
            kwargs['eval_id'] = eval_id
            return original_log_metric(*args, **kwargs)
        self.audit_logger.log_metric_computation = log_with_id

        result = {
            "eval_id": eval_id,
            "timestamp": datetime.now().isoformat(),
            "synthetic_rows": len(synthetic_df),
            "synthetic_columns": len(synthetic_df.columns)
        }

        # 1. Statistical Fidelity
        logger.info("Computing statistical fidelity...")
        result["statistical_fidelity"] = self.compute_statistical_fidelity(
            synthetic_df, original_df, original_profile
        )

        # 2. Privacy Risk
        logger.info("Computing privacy risk...")
        result["privacy_risk"] = self.compute_privacy_risk(
            synthetic_df, original_df, original_profile
        )

        # Extract top-level scores
        result["distribution_shift_score"] = result["statistical_fidelity"].get("distribution_shift", {}).get("shift_score")
        result["mode_collapse_probability"] = result["statistical_fidelity"].get("mode_collapse", {}).get("collapse_probability")
        result["duplicates_rate"] = result["privacy_risk"].get("duplicates_rate", 0.0)

        # Restore original logging function
        self.audit_logger.log_metric_computation = original_log_metric

        logger.info(f"Evaluation {eval_id} complete")

        return result
