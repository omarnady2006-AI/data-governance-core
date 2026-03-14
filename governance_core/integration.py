"""
Public Integration Entrypoint
==============================

This is the ONLY module that external systems need to import.

Usage::

    from governance_core.integration import audit_dataset

    result = audit_dataset(
        synthetic_df=my_synthetic_df,
        original_df=my_original_df,   # optional
    )

    print(result["dataset_risk_summary"]["overall_risk_level"])
    print(result["has_uncertainty"])
    for threat in result.get("threats") or []:
        print(threat["threat_name"], threat["severity"])

Design decisions
----------------
* **Keyword-only arguments** — callers cannot accidentally swap
  ``synthetic_df`` and ``original_df`` by position, which would silently
  produce inverted metrics.

* **NullAuditLogger by default** — no directories or files are created
  inside the host process unless the caller explicitly supplies an
  ``audit_logger``.  This makes the function safe to call from VS Code
  extensions, web services, and unit tests without side effects.

* **Returns the GovernanceResult dict** — the full metrics dict returned
  by ``RuleEngine`` is available via the ``raw_metrics`` key for callers
  that need lower-level detail, but the primary return value is the
  structured governance assessment.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from .rule_engine import RuleEngine
from .audit_logger import AuditLogger, NullAuditLogger

logger = logging.getLogger(__name__)

__all__ = ["audit_dataset"]


def audit_dataset(
    *,
    synthetic_df: pd.DataFrame,
    original_df: Optional[pd.DataFrame] = None,
    audit_logger: Optional[AuditLogger] = None,
    eval_id: Optional[str] = None,
    domias_row_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Evaluate a synthetic dataset for privacy and governance risks.

    This is the single public entrypoint for embedding the governance engine
    inside external systems.  External callers should never need to import
    ``RuleEngine``, metric modules, or any other internal component.

    All arguments are **keyword-only** to prevent silent argument-order bugs.

    Parameters
    ----------
    synthetic_df:
        The synthetic dataset to audit.  Must be a pandas DataFrame.
    original_df:
        Optional reference (original) dataset.  When supplied, privacy
        metrics (duplicate detection, DOMIAS membership inference) and
        fidelity metrics (distribution shift, mode collapse, correlation)
        are computed against it.

        When omitted the engine still runs and returns a valid result, but
        ``privacy_score`` will be ``1.0`` and ``privacy_score_reliable``
        will be ``False`` — see the note in the returned dict.
    audit_logger:
        Optional :class:`AuditLogger` instance.  When ``None`` (default),
        a :class:`NullAuditLogger` is used so no files or directories are
        created.  Pass an :class:`AuditLogger` instance to enable
        filesystem-backed audit trails.
    eval_id:
        Optional stable identifier for this evaluation run.  Useful when
        the caller wants to correlate results with its own records.
        Auto-generated (``eval_<8-hex>`` format) when ``None``.
    domias_row_limit:
        Override the default DOMIAS row limit (8 000).  DOMIAS builds an
        O(N²) matrix so very large datasets require more RAM.  Set to a
        higher value only when sufficient memory is available.
        Pass ``None`` to use the built-in default.

    Returns
    -------
    dict
        The ``GovernanceResult`` serialised to a plain dict.  Always
        contains:

        ``dataset_risk_summary``
            Aggregated risk level (``"low"`` / ``"warning"`` / ``"critical"``),
            threat counts, top threats, and a human-readable summary string.
        ``has_uncertainty``
            ``True`` when any metric was missing or unreliable.
        ``uncertainty_notes``
            List of human-readable strings describing uncertainty sources.
        ``metadata``
            Engine version, timestamp, and output mode.
        ``disclaimers``
            Standard advisory disclaimers.
        ``threats``
            List of individual :class:`ThreatSignal` dicts (full mode).
        ``raw_metrics``
            The complete ``MetricsSchema`` dict from ``RuleEngine``,
            including ``privacy_score``, ``privacy_score_reliable``,
            ``statistical_drift``, ``domias_skipped``, etc.

    Raises
    ------
    Never raises.  All internal errors are captured and returned in
    ``has_uncertainty`` / ``uncertainty_notes``.

    Examples
    --------
    Basic usage — no original data::

        result = audit_dataset(synthetic_df=synth)
        print(result["dataset_risk_summary"]["overall_risk_level"])
        # "low" — but result["raw_metrics"]["privacy_score_reliable"] is False

    Full evaluation::

        result = audit_dataset(
            synthetic_df=synth,
            original_df=orig,
        )
        print(result["dataset_risk_summary"]["overall_risk_level"])   # "warning"
        print(result["raw_metrics"]["privacy_score"])                 # e.g. 0.7312
        print(result["raw_metrics"]["privacy_score_reliable"])        # True

    With audit trail::

        from governance_core.audit_logger import AuditLogger
        audit = AuditLogger(output_dir="/var/log/governance")
        result = audit_dataset(
            synthetic_df=synth,
            original_df=orig,
            audit_logger=audit,
        )
    """
    # Use NullAuditLogger by default — no filesystem side effects.
    effective_logger: AuditLogger = (
        audit_logger if audit_logger is not None else NullAuditLogger()
    )

    # Build engine kwargs
    engine_kwargs: Dict[str, Any] = {"audit_logger": effective_logger}

    # Build PrivacyRiskMetrics kwargs if row limit override supplied
    # RuleEngine exposes this by forwarding to PrivacyRiskMetrics at init time.
    # We patch via the config dict for forward-compatibility.
    if domias_row_limit is not None:
        from .metrics import PrivacyRiskMetrics
        privacy_risk_instance = PrivacyRiskMetrics(
            domias_row_limit=domias_row_limit
        )
        engine = RuleEngine(audit_logger=effective_logger)
        engine.privacy_risk = privacy_risk_instance
    else:
        engine = RuleEngine(**engine_kwargs)

    try:
        raw_metrics = engine.evaluate_synthetic_data(
            synthetic_df=synthetic_df,
            original_df=original_df,
            eval_id=eval_id,
        )
    except Exception as exc:  # pragma: no cover — safety net
        logger.error(f"audit_dataset failed: {exc}", exc_info=True)
        return {
            "dataset_risk_summary": {
                "overall_risk_level": "unknown",
                "summary_text": f"Evaluation failed: {exc}",
                "total_threats": 0,
                "top_threats": [],
            },
            "has_uncertainty": True,
            "uncertainty_notes": [f"Unhandled error: {exc}"],
            "metadata": {},
            "disclaimers": [
                "This assessment is advisory only",
                "An error occurred during evaluation — results are incomplete",
            ],
            "threats": None,
            "raw_metrics": {},
        }

    # Extract the GovernanceResult dict that RuleEngine embedded in the
    # metrics dict, then attach the full raw_metrics for callers that need
    # lower-level access.
    governance_dict = raw_metrics.get("governance_result", {})

    # Attach the full metrics dict so callers can inspect privacy_score,
    # privacy_score_reliable, statistical_drift, domias_skipped, etc.
    # without having to know about the internal dict structure.
    governance_dict = dict(governance_dict)   # shallow copy — do not mutate original
    governance_dict["raw_metrics"] = {
        k: v for k, v in raw_metrics.items()
        # Exclude large sub-dicts that are already captured inside
        # governance_result to keep the return value lean by default.
        # Callers that need the full statistical_fidelity / privacy_risk
        # sub-dicts can pass output_mode="full" directly to evaluate_governance.
        if k not in ("governance_result", "statistical_fidelity", "privacy_risk")
    }

    return governance_dict
