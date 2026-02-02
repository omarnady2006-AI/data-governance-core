# Outside Data Governance Engine

**An interpretation layer that maps synthetic data metrics to privacy, utility, and consistency risk signals.**

---

## 🎯 Why This Exists

- **Problem**: Synthetic data evaluations produce disconnected metrics. Security teams can't efficiently assess privacy risks or utility degradation.
- **Solution**: Standardized threat signal mapping with severity, confidence, and transparent aggregation logic.
- **Non-Goal**: This is **NOT** a decision engine. It interprets risks. It does not approve, reject, or gate deployments.
- **Role**: Advisory-only component between metric computation and human/policy decision-making.

---

## 🏗️ Architecture

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                         EXTERNAL COMPONENTS                               ║
║                                                                           ║
║   ┌─────────────────┐            ┌──────────────────┐                   ║
║   │  Synthetic      │   Data     │   Evaluation     │                   ║
║   │  Data Generator │  ────────▶ │   Metrics Engine │                   ║
║   │  (CTGAN, etc.)  │            │   (Privacy, etc.)│                   ║
║   └─────────────────┘            └─────────┬────────┘                   ║
║                                             │                             ║
╚═════════════════════════════════════════════╪═════════════════════════════╝
                                              │
                                              │ Raw Metrics Dict
                                              │ {privacy_score: 0.85,
                                              │  utility_score: 0.90,
                                              │  privacy_risk: {...}}
                                              │
                                              ▼
╔═══════════════════════════════════════════════════════════════════════════╗
║                  🛡️  THIS ENGINE (Advisory Only)                          ║
╚═══════════════════════════════════════════════════════════════════════════╝

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  PHASE 1: THREAT MAPPING (Deterministic, Rule-Based)           ┃
    ┃                                                                 ┃
    ┃  Input:  Raw metrics                                           ┃
    ┃  Output: Categorized threat signals                            ┃
    ┃                                                                 ┃
    ┃  Examples:                                                      ┃
    ┃  • Membership Inference    → confidence: 0.7, severity: MEDIUM ┃
    ┃  • Distribution Drift      → confidence: 0.9, severity: HIGH   ┃
    ┃  • Record Linkage Risk     → confidence: 0.4, severity: LOW    ┃
    ┃  • Near-Duplicate Detected → confidence: 0.8, severity: HIGH   ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              │
                              │ Threat Signals
                              │
                              ▼
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  PHASE 2: RISK AGGREGATION (Deterministic, Transparent)        ┃
    ┃                                                                 ┃
    ┃  Input:  Threat signals                                        ┃
    ┃  Output: Dataset-level risk summary                            ┃
    ┃                                                                 ┃
    ┃  Aggregates:                                                    ┃
    ┃  • Overall Risk Level:  "warning" ┃ "low" ┃ "critical"         ┃
    ┃  • Top Threats: [drift, inference, linkage]                    ┃
    ┃  • Severity Breakdown: {high: 2, medium: 3, low: 1}            ┃
    ┃  • Uncertainty Flag: True (3 missing metrics)                  ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                │                                   
                │ Risk Summary                      ┌─────────────────────────────┐
                │ (deterministic)                   │ 🧠 LLM ADVISORY (Optional)  │
                │                                   │ ─────────────────────────── │
                ├──────────── read-only ──────────▶ │ Zero-Trust Model:           │
                │                                   │                             │
                │                                   │ ✓ Sanitized metrics only    │
                │                    explanations   │ ✓ Generates explanations    │
                │              ◀─── (non-binding)   │ ✗ CANNOT modify signals     │
                │                                   │ ✗ CANNOT change risk level  │
                │                                   │ ✓ Audit logged             │
                │                                   │ ✓ Graceful fallback        │
                │                                   └─────────────────────────────┘
                │
                ▼
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  PHASE 3: STRUCTURED OUTPUT                                     ┃
    ┃                                                                 ┃
    ┃  GovernanceResult {                                             ┃
    ┃    • dataset_risk_summary  ← Always deterministic              ┃
    ┃    • threats[]             ← Always deterministic              ┃
    ┃    • has_uncertainty       ← Data quality flag                 ┃
    ┃    • llm_explanation       ← Optional, advisory only           ┃
    ┃    • disclaimers[]         ← "Advisory only, no decisions"     ┃
    ┃    • metadata              ← Version, timestamp, config        ┃
    ┃  }                                                              ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                              │
                              │ Interpretive Signals
                              │ (NO DECISIONS MADE)
                              │
                              ▼
╔═══════════════════════════════════════════════════════════════════════════╗
║                         CONSUMER SYSTEMS                                  ║
║  (Decision-making happens HERE, not in the engine above)                  ║
║                                                                           ║
║  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       ║
║  │  Human Review    │  │  Policy Engine   │  │  Audit System    │       ║
║  │  Dashboard       │  │  (Rule-Based)    │  │  (Compliance)    │       ║
║  │                  │  │                  │  │                  │       ║
║  │  • View signals  │  │  • Apply policy  │  │  • Log decisions │       ║
║  │  • Make decision │  │  • Gate pipeline │  │  • Track history │       ║
║  └──────────────────┘  └──────────────────┘  └──────────────────┘       ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

**Key Insight**: This engine sits in the **interpretation layer**—it transforms raw numbers into risk context, but never decides what to do about it.

### 🧠 LLM's Role (Optional, Zero-Trust)

The LLM is an **optional advisory component** that can enhance explanations:

- **Purpose**: Generates human-readable explanations and additional context
- **Input**: Sanitized aggregate metrics only (NO raw data, NO PII)
- **Output**: Non-binding explanations that CANNOT influence threat signals or risk levels
- **Security**: All interactions are audited, logged, and can be disabled entirely
- **Fallback**: System works fully deterministically without LLM (graceful degradation)

**Critical Constraint**: The LLM receives threat signals as **read-only input**. It cannot modify, create, or remove threats. Risk aggregation is always deterministic.

---

## 🧠 Core Design Philosophy

| Principle | Meaning |
|-----------|---------|
| **Advisory-Only** | Outputs describe risks, never make approve/reject decisions |
| **Non-Gateable by Design** | No boolean "is_safe" field exists—results require explicit interpretation |
| **Separation of Concerns** | Threat interpretation ≠ Policy enforcement |
| **Zero Silent Approvals** | Missing data triggers uncertainty flags, not silent defaults |

**Design Goal**: Make automated misuse architecturally impossible.

---

## ✅ What This Engine DOES

- 🔍 **Threat Signal Mapping** – Interprets metrics into categorized threats (privacy, utility, consistency)
- 📊 **Risk Aggregation** – Combines threats into dataset-level summaries (low/warning/critical)
- 🏷️ **Structured Output** – JSON-serializable results with metadata and uncertainty flags
- 🛡️ **Safe Degradation** – Handles missing/invalid metrics gracefully without crashes
- 📝 **Auditability** – Tracks triggered conditions and escalation logic transparently

---

## ⚠️ What This Engine DOES NOT DO

| ❌ Non-Goal | Explanation |
|------------|-------------|
| **Pipeline Decisions** | Does NOT approve, reject, allow, block, or gate deployments |
| **Data Modification** | Does NOT regenerate, fix, transform, or sanitize datasets |
| **Metric Computation** | Does NOT run statistical tests—operates on pre-computed metrics |
| **Compliance Enforcement** | Does NOT implement GDPR, HIPAA, or regulatory rules |
| **Privacy Guarantees** | Does NOT prove differential privacy or k-anonymity |
| **Autonomous Operation** | Does NOT run as standalone service without oversight |

**Critical**: This system provides **risk context**, not **action decisions**.

---

## 📦 Minimal Example

```python
from governance_core import evaluate_governance

# Input: pre-computed metrics
metrics = {
    "privacy_score": 0.85,
    "utility_score": 0.90,
    "privacy_risk": {"membership_inference_auc": 0.52}
}

# Evaluate (advisory only)
result = evaluate_governance(metrics, output_mode="summary")

# Interpret results
print(result.dataset_risk_summary.overall_risk_level)  # "low" | "warning" | "critical"
print(result.has_uncertainty)  # Boolean flag
print(result.disclaimers)  # Advisory-only notices

# Decision-making happens OUTSIDE this engine
if result.dataset_risk_summary.overall_risk_level == "critical":
    notify_security_team(result)  # Human review required
```

**What this returns**: Risk interpretation, NOT "approved" or "should_deploy".

---

## 🔗 Where This Fits

### Integration Patterns

```
Pattern 1: Synthetic Data Pipeline
┌─────────┐   ┌─────────┐   ┌──────────────┐   ┌───────────┐
│ Generate│──▶│ Evaluate│──▶│ THIS ENGINE  │──▶│ Dashboard │
│ Synth   │   │ Metrics │   │ (interpret)  │   │ (review)  │
└─────────┘   └─────────┘   └──────────────┘   └───────────┘
```

```
Pattern 2: Policy Engine Integration
┌──────────────┐   ┌──────────────┐   ┌─────────────┐
│ THIS ENGINE  │──▶│ Policy Engine│──▶│ Deployment  │
│ (advisory)   │   │ (decides)    │   │ (action)    │
└──────────────┘   └──────────────┘   └─────────────┘
```

```
Pattern 3: Audit Trail
┌──────────────┐   ┌──────────────┐
│ THIS ENGINE  │──▶│ Audit System │
│ (signals)    │   │ (log/track)  │
└──────────────┘   └──────────────┘
```

**What this engine does NOT provide**: CI/CD integration, IDE extensions, deployment automation.

**What you must build**: The decision logic that consumes this engine's output.

---

## 📋 Quick Reference

### Input
```python
{
    "privacy_score": float,      # 0.0–1.0
    "utility_score": float,      # 0.0–1.0
    "privacy_risk": {...},       # Detailed risk metrics
    "statistical_fidelity": {...},
    "semantic_invariants": {...}
}
```

### Output
```python
GovernanceResult(
    dataset_risk_summary,   # Overall risk level + breakdown
    threats,                # Individual threat signals (optional)
    has_uncertainty,        # Data quality flag
    uncertainty_notes,      # Human-readable issues
    disclaimers,            # Advisory-only notices
    metadata               # Version, timestamp, config
)
```

### Risk Levels (Interpretive, Not Decisions)
- **`low`** – No significant threats detected
- **`warning`** – Medium-severity threats present, review recommended
- **`critical`** – High-severity threats detected, manual review required
- **`unknown`** – Insufficient data for assessment

---

## 🎓 Learn More

| Document | Purpose |
|----------|---------|
| [Scope and Boundaries](docs/SCOPE_AND_BOUNDARIES.md) | Detailed technical boundaries |
| [Threat Model](docs/THREAT_MODEL.md) | Threat catalog and detection logic |
| [Leakage Metrics](docs/LEAKAGE_METRICS.md) | Privacy risk metrics |
| [Examples](examples/) | Usage patterns and test cases |

---

## 📌 Philosophy Summary

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  This engine answers: "What privacy, utility, and           │
│  consistency risks are present in this dataset?"            │
│                                                              │
│  It does NOT answer: "Should I deploy this dataset?"        │
│                                                              │
│  ────────────────────────────────────────────────────────── │
│                                                              │
│  Interpretation  ✓  (this engine)                           │
│  Enforcement     ✗  (your responsibility)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Advisory-Only Notice**: This engine provides risk interpretation, not deployment authorization. All results inform human review or policy engine logic—they do not replace it.

---

**Version**: 2.1.0 | **License**: MIT | **Dependencies**: Python 3.7+ (stdlib only)
