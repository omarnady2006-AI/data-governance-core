# Outside Data Governance Engine

Quantitative governance signals for synthetic data. Five deterministic metrics measure structural fidelity, distributional shift, mode collapse, duplicate leakage, and membership inference risk. All metrics are computed without AI/LLM involvement; an optional LLM layer provides human-readable interpretation but cannot override scores. The distribution shift metric operates in quantile space and is provably invariant to any shared monotonic transform.

## Mathematical Guarantees

**Distribution shift** transforms both datasets into quantile space via the reference ECDF before comparing:

```
u = F_ref(x)                         # map to [0, 1]
CvM(u_ref, u_syn)                    # Cramér–von Mises distance
tail_diff = |P(u < 0.05) − 0.05|    # tail mass deviation
            + |P(u > 0.95) − 0.05|
```

Because `F_ref` is a monotonic function, any shared monotonic transform `g` satisfies `F_{g(ref)}(g(x)) = F_ref(x)`, so the score is invariant.

**Verified invariances** (run `scripts/invariance_proofs.py`):

| Metric | Invariant to |
|--------|-------------|
| distribution_shift | monotonic transforms (3x+7, exp, x³), row permutation |
| mode_collapse | row permutation, uniform scaling |
| structural_contract | row permutation, dtype cast (float64→float32), encoding |
| duplicate_detection | sub-precision noise (σ ≤ 1e-12) |
| leakage (DOMIAS) | row permutation, column swap, uniform scaling |

## System Architecture

The engine is organized into four layers. Each layer has a single responsibility. Data flows strictly downward — no layer can feed back into a layer above it.

### Layer 1 — Measurement Layer

Deterministic statistical metrics computed directly from the data. No AI, no heuristics, no learned parameters. Five metrics are computed independently:

- **Structural contract validation** — per-column JS divergence, nullability binomial test, MI-based column-swap detection
- **Distribution shift** — PIT via reference ECDF → Cramér–von Mises + tail mass deviation (quantile space)
- **Mode collapse** — Local Intrinsic Dimensionality (kNN MLE) + per-column entropy loss
- **Duplicate detection** — kNN identity-manifold matching with adaptive epsilon
- **Membership leakage** — DOMIAS log-likelihood ratio attack with quantile-binned calibration

### Layer 2 — Signal Layer

Raw metric outputs are mapped to typed threat signals (`threat_mapping.py`) and aggregated into a dataset-level risk summary (`threat_aggregation.py`). Each signal carries a severity, confidence, and evidence trace. No thresholds gate passage — all signals propagate.

### Layer 3 — Decision Layer

The `RuleEngine` orchestrates metric computation and emits a machine-readable governance report containing all scores, evidence arrays, and uncertainty flags. This report is the primary output. It is fully deterministic and reproducible.

### Layer 4 — Interpretation Layer (LLM)

An optional `GovernanceAgent` forwards the finished report to a local or remote LLM (Ollama, Anthropic, OpenAI) to generate a natural-language explanation. The LLM receives only sanitized, aggregated metrics — never raw data.

> **Safety rule:** The LLM layer is advisory only. It cannot override, adjust, filter, or recompute any metric. All numeric scores in the governance report are final before the LLM is invoked. If the LLM is unavailable, the system falls back to a deterministic rule-based interpretation.

### Data Flow

```
         ┌──────────────────────────────────┐
         │        original + synthetic       │
         │            datasets               │
         └────────────────┬─────────────────┘
                          │
                          ▼
   ┌─────────────────────────────────────────────┐
   │  LAYER 1 — MEASUREMENT (deterministic)      │
   │                                             │
   │  structural   distribution   mode    dup    │
   │  contract     shift          collapse detect │
   │                       leakage (DOMIAS)      │
   └────────────────────┬────────────────────────┘
                        │  raw metric dicts
                        ▼
   ┌─────────────────────────────────────────────┐
   │  LAYER 2 — SIGNAL                           │
   │  threat_mapping  →  threat_aggregation       │
   └────────────────────┬────────────────────────┘
                        │  typed threat signals
                        ▼
   ┌─────────────────────────────────────────────┐
   │  LAYER 3 — DECISION                         │
   │  RuleEngine produces governance report       │
   │  (scores, evidence, uncertainty flags)       │
   └──────────┬──────────────────────────────────┘
              │
              ├──── governance report (machine-readable)
              │     ← primary output, always available
              │
              ▼
   ┌─────────────────────────────────────────────┐
   │  LAYER 4 — INTERPRETATION (optional LLM)    │
   │  natural-language explanation                │
   │  CANNOT modify any numeric result            │
   └─────────────────────────────────────────────┘
```

## Quickstart

### Numeric-only usage (no LLM)

```python
import pandas as pd
from governance_core import RuleEngine

engine = RuleEngine()
result = engine.evaluate_synthetic_data(
    synthetic_df=pd.read_csv("synthetic.csv"),
    original_df=pd.read_csv("original.csv"),
)

# All scores are deterministic — no LLM involved
print(result["distribution_shift_score"])   # float ∈ [0, 1]
print(result["mode_collapse_probability"])   # float ∈ [0, 1]
print(result["duplicates_rate"])             # float ∈ [0, 1]

# Full evidence breakdown
for col, info in result["statistical_fidelity"]["distribution_shift"]["per_column"].items():
    print(f"  {col}: shift={info['shift_score']:.4f}")
```

### With LLM explanation

```python
from governance_core import RuleEngine
from governance_core.governance_agent import GovernanceAgent

# Step 1: compute metrics (deterministic, no LLM)
engine = RuleEngine()
result = engine.evaluate_synthetic_data(
    synthetic_df=synthetic_df,
    original_df=original_df,
)

# Step 2: optional — ask LLM to explain the finished report
agent = GovernanceAgent(provider_type="ollama")  # or "anthropic", "openai"
interpretation = agent.interpret_metrics(result)
print(interpretation["explanation"])  # natural-language summary
# The numeric scores in `result` are unchanged — the LLM only explains them.
```

## Signals

| Signal | What it measures | Key output |
|--------|-----------------|------------|
| **Structural contract** | Per-column distributional match via JS divergence, nullability changes, column swap detection | `column_violations`, `any_violation` |
| **Distribution shift** | Marginal shift in quantile space (CvM + tail) and multivariate shift (Spearman Δρ) | `shift_score` ∈ [0, 1] |
| **Mode collapse** | Support volume loss, entropy loss, intrinsic dimensionality drop, categorical coverage | `collapse_probability` ∈ [0, 1] |
| **Duplicate detection** | Exact and near-duplicate rates between synthetic and original | `duplicates_rate`, `exact_duplicates_count` |
| **Membership leakage** | DOMIAS likelihood-ratio attack: KDE density ratio for each record | `leakage_risk_score`, `membership_inference_auc` |

## Limitations

- **Sample size**: CvM and KDE estimates degrade below ~200 rows per dataset. A `sample_size_warning` flag is emitted.
- **High dimensionality**: KDE-based metrics (DOMIAS, mode collapse) suffer from curse of dimensionality. Effective above ~10-15 numeric columns only.
- **Categorical-only data**: Distribution shift falls back to JS divergence for categoricals, which does not share the monotonic invariance guarantee.
- **No causal analysis**: Metrics detect statistical symptoms, not root causes of data quality issues.
- **Adversarial robustness**: Duplicate detection can be evaded with noise σ > 1e-2. Near-duplicate thresholds are adaptive but not foolproof.
- **LLM dependency**: The optional LLM interpretation layer requires Ollama, Anthropic, or OpenAI. Without it, the system still produces all numeric signals.

### What this system is NOT

- **Not a data cleaning tool.** It does not repair, impute, or transform data. It measures properties of synthetic outputs.
- **Not a fairness auditor.** It does not evaluate bias, protected-attribute parity, or demographic impact.
- **Not causal inference.** It detects distributional symptoms, not causal mechanisms behind data quality problems.
- **Not a semantic equivalence detector.** It compares statistical distributions, not whether two datasets "mean the same thing" in context.
- **Not a deployment approval system.** It produces advisory signals for human review. It never emits approve/reject decisions.

## Repository Structure

```
governance_core/          # Core library
├── metrics/
│   ├── statistical_fidelity.py   # Structural contract, distribution shift, mode collapse
│   └── privacy_risk.py           # Duplicate detection, DOMIAS leakage
├── rule_engine.py                # Deterministic metric orchestrator
├── api.py                        # Public API (evaluate_governance)
├── cli.py                        # Command-line interface
├── governance_agent.py           # Optional LLM interpretation layer
├── llm_provider.py               # Ollama / Anthropic / OpenAI adapters
├── threat_mapping.py             # Metric → threat signal mapping
├── threat_aggregation.py         # Dataset-level risk summary
├── data_profiles.py              # Statistical profiling
├── audit_logger.py               # Immutable audit log
└── requirements.txt

scripts/                  # Verification scripts
├── invariance_proofs.py          # Formal invariance tests for all 5 metrics
├── adversarial_audit.py          # Adversarial robustness audit
└── domias_validation.py          # DOMIAS attack calibration

tests/                    # Test suite
docs/                     # Documentation
examples/                 # Usage examples
policy/                   # Policy specifications
_archive_unused/          # Archived legacy code (not part of active system)
```

## Dependencies

```
numpy
pandas
scipy
scikit-learn
```

Optional: `requests` (for Ollama/API LLM providers).

## License

See LICENSE file.
