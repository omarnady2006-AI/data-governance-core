# Requirements Checklist

All 5 capabilities verified against source and `invariance_proofs.py`.

| # | Requirement | File | Function | Invariant |
|---|-------------|------|----------|-----------|
| 1 | Structural Contract Validation | `governance_core/metrics/statistical_fidelity.py` | `StatisticalFidelityMetrics.compute_structural_contract_validation` | **true** |
| 2 | Distribution Shift Detection (quantile-space) | `governance_core/metrics/statistical_fidelity.py` | `StatisticalFidelityMetrics.compute_distribution_shift` | **true** |
| 3 | Mode Collapse Detection | `governance_core/metrics/statistical_fidelity.py` | `StatisticalFidelityMetrics.compute_mode_collapse` | **true** |
| 4 | Duplicate Identifier Detection | `governance_core/metrics/privacy_risk.py` | `PrivacyRiskMetrics.detect_duplicates` | **true** |
| 5 | Membership Leakage Detection (DOMIAS) | `governance_core/metrics/privacy_risk.py` | `PrivacyRiskMetrics.run_domias_attack` | **true** |

## Orchestration

- `governance_core/rule_engine.py` → `RuleEngine.evaluate_synthetic_data` calls all metrics
- `governance_core/api.py` → `evaluate_governance` maps metrics to threat signals
- `governance_core/cli.py` → CLI entrypoint

## Invariance Proof Results

```
distribution_shift   | true   (3x+7 ✓, exp ✓, x³ ✓, sort ✓)
mode_collapse        | true   (permutation ✓, scaling ✓)
structural_contract  | true   (int_codes ✓, cat_codes ✓, hash ✓, perm ✓, dtype ✓)
duplicate_detection  | true   (noise σ=1e-16..1e-12 ✓)
leakage_domias       | true   (row_perm ✓, col_swap ✓, scaling ✓)

ALL INVARIANT: true
```
