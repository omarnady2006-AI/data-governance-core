# Leakage and Distribution Metrics (Evidence-Based)

This project reports statistical evidence, not rule-based pass/fail claims.

## Structural Contract Validation
- Schema inference: per-column probabilistic type profile using parseability, cardinality, and entropy.
- Type drift: Jensen-Shannon divergence between baseline and synthetic type probability vectors.
- Nullability drift: binomial test comparing observed null count to baseline null rate.

## Distribution Shift
- Continuous columns:
  - Kolmogorov-Smirnov statistic + p-value
  - Wasserstein distance
- Categorical columns:
  - Jensen-Shannon divergence
  - Population Stability Index (PSI)
  - Chi-square p-value for frequency-table shift
- Required outputs:
  - `shift_score`
  - `confidence`
  - `sample_size_warning`

## Mode Collapse
- Numeric entropy comparison: `entropy(real)` vs `entropy(synthetic)`.
- Numeric support shrinkage: convex hull volume ratio `volume_syn / volume_real`.
- Category collapse: category coverage ratio `|syn ∩ real| / |real|`.
- Output: `collapse_probability` in `[0,1]`.

## Duplicate and Memorization Risk
- Level 1 exact duplicates: stable row hashing.
- Level 2 near duplicates: nearest-neighbor cosine similarity in encoded feature space.
- Level 3 memorization risk: classifier separability + calibration evidence (AUC, Brier, ECE), combined into `leakage_risk_score`.

## Evidence Record Format
Core engine evidence uses machine-readable records:

```json
{
  "signal": "distribution_shift",
  "metric": "KS",
  "value": 0.34,
  "p_value": 0.002,
  "confidence": 0.998
}
```
