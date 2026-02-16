"""
Governance metrics: 5 core capabilities only.

- statistical_fidelity: Structural contracts, distribution shift, mode collapse
- privacy_risk: Duplicate detection, membership inference (DOMIAS)
"""

from .statistical_fidelity import StatisticalFidelityMetrics
from .privacy_risk import PrivacyRiskMetrics

__all__ = [
    "StatisticalFidelityMetrics",
    "PrivacyRiskMetrics",
]
