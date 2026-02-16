"""
Hybrid Data Governance Agent for Synthetic Data

Capabilities:
1. Structural Contract Validation
2. Distribution Shift Detection
3. Mode Collapse Detection
4. Duplicate Identifier Detection
5. Membership Leakage Detection (DOMIAS)
"""

from .rule_engine import RuleEngine
from .governance_agent import GovernanceAgent
from .audit_logger import AuditLogger, AuditEntry
from .data_profiles import DataProfiler, DatasetProfile, FieldProfile
from .llm_provider import (
    LLMProvider,
    OllamaProvider,
    AnthropicProvider,
    OpenAIProvider,
    create_provider
)
from .metrics import (
    StatisticalFidelityMetrics,
    PrivacyRiskMetrics,
)

# Public API facade
from .api import (
    evaluate_governance,
    GovernanceResult,
    __version__ as api_version
)

__version__ = "3.0.0"

__all__ = [
    # Core components
    "RuleEngine",
    "GovernanceAgent",
    "AuditLogger",
    "AuditEntry",
    "DataProfiler",
    "DatasetProfile",
    "FieldProfile",

    # LLM providers
    "LLMProvider",
    "OllamaProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "create_provider",

    # Metrics
    "StatisticalFidelityMetrics",
    "PrivacyRiskMetrics",

    # Public API
    "evaluate_governance",
    "GovernanceResult",
]
