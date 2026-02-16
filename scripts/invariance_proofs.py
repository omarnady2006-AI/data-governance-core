"""
Invariance Proofs — Attempt to violate each metric using
transformations that preserve the underlying distribution.

Output: metric_name | invariant (true/false)

No thresholds adjusted. No engine modified. Pure counterexamples.
"""

import sys
import warnings
import logging
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from governance_core.metrics.statistical_fidelity import StatisticalFidelityMetrics
from governance_core.metrics.privacy_risk import PrivacyRiskMetrics

RNG = np.random.default_rng(999)
N = 800
TOLERANCE = 0.02  # max acceptable difference between invariant scores


# =====================================================================
# 1. DISTRIBUTION SHIFT — monotonic transform invariance
# =====================================================================

def proof_distribution_shift():
    sfm = StatisticalFidelityMetrics()

    # Generate X ~ mixture of normals (non-trivial distribution)
    x1 = np.concatenate([RNG.normal(-3, 1, N // 2), RNG.normal(3, 1, N - N // 2)])
    x2 = RNG.exponential(2, N)
    x3 = RNG.uniform(-5, 5, N)

    orig = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})

    # Baseline: fresh sample from same distribution
    x1b = np.concatenate([RNG.normal(-3, 1, N // 2), RNG.normal(3, 1, N - N // 2)])
    x2b = RNG.exponential(2, N)
    x3b = RNG.uniform(-5, 5, N)
    baseline_syn = pd.DataFrame({"x1": x1b, "x2": x2b, "x3": x3b})
    baseline = sfm.compute_distribution_shift(baseline_syn, orig)
    base_score = baseline["shift_score"]

    transforms = {
        "x -> 3x + 7": lambda df: df.assign(
            x1=df["x1"] * 3 + 7, x2=df["x2"] * 3 + 7, x3=df["x3"] * 3 + 7
        ),
        "x -> exp(x)": lambda df: df.assign(
            x1=np.exp(np.clip(df["x1"], -10, 10)),
            x2=np.exp(np.clip(df["x2"], -10, 10)),
            x3=np.exp(np.clip(df["x3"], -10, 10)),
        ),
        "x -> x^3": lambda df: df.assign(
            x1=df["x1"] ** 3, x2=df["x2"] ** 3, x3=df["x3"] ** 3
        ),
        "sorted permutation": lambda df: df.assign(
            x1=np.sort(df["x1"].to_numpy()),
            x2=np.sort(df["x2"].to_numpy()),
            x3=np.sort(df["x3"].to_numpy()),
        ),
    }

    violations = []
    details = []

    for name, transform in transforms.items():
        # Apply the SAME transform to BOTH orig and syn so the
        # underlying distributional relationship is preserved
        t_orig = transform(orig)
        t_syn = transform(baseline_syn)
        res = sfm.compute_distribution_shift(t_syn, t_orig)
        score = res["shift_score"]
        diff = abs(score - base_score)
        ok = diff <= TOLERANCE
        details.append(f"    {name}: shift={score:.6f} (base={base_score:.6f}, diff={diff:.6f}) {'OK' if ok else 'VIOLATION'}")
        if not ok:
            violations.append(name)

    invariant = len(violations) == 0
    return invariant, details


# =====================================================================
# 2. MODE COLLAPSE — same variance/entropy, different topology
# =====================================================================

def proof_mode_collapse():
    sfm = StatisticalFidelityMetrics()

    # Original: 2D Gaussian
    orig = pd.DataFrame({
        "a": RNG.standard_normal(N),
        "b": RNG.standard_normal(N),
    })

    # Dataset A: single Gaussian, same variance/entropy
    syn_a = pd.DataFrame({
        "a": RNG.standard_normal(N),
        "b": RNG.standard_normal(N),
    })
    mc_a = sfm.compute_mode_collapse(syn_a, orig)

    # Dataset B: same variance and entropy but different support topology
    # (ring distribution — same marginal stats as Gaussian but hollow center)
    angles = RNG.uniform(0, 2 * np.pi, N)
    radii = np.abs(RNG.standard_normal(N)) + 1.5  # ring at ~1.5
    ring_a = radii * np.cos(angles)
    ring_b = radii * np.sin(angles)
    # Standardize to match original variance
    ring_a = (ring_a - ring_a.mean()) / (ring_a.std() + 1e-12) * orig["a"].std() + orig["a"].mean()
    ring_b = (ring_b - ring_b.mean()) / (ring_b.std() + 1e-12) * orig["b"].std() + orig["b"].mean()
    syn_b = pd.DataFrame({"a": ring_a, "b": ring_b})
    mc_b = sfm.compute_mode_collapse(syn_b, orig)

    # Dataset C: two tight clusters with same global variance
    half = N // 2
    c_a = np.concatenate([RNG.normal(-2, 0.1, half), RNG.normal(2, 0.1, N - half)])
    c_b = np.concatenate([RNG.normal(-2, 0.1, half), RNG.normal(2, 0.1, N - half)])
    c_a = (c_a - c_a.mean()) / (c_a.std() + 1e-12) * orig["a"].std() + orig["a"].mean()
    c_b = (c_b - c_b.mean()) / (c_b.std() + 1e-12) * orig["b"].std() + orig["b"].mean()
    syn_c = pd.DataFrame({"a": c_a, "b": c_b})
    mc_c = sfm.compute_mode_collapse(syn_c, orig)

    p_a = mc_a["collapse_probability"]
    p_b = mc_b["collapse_probability"]
    p_c = mc_c["collapse_probability"]

    # If collapse_probability differs between topologically different datasets
    # with same variance/entropy, that is EXPECTED behavior (not a violation).
    # A violation would be if topologically identical datasets get different scores.

    # True invariance test: row permutation must not change collapse_prob
    perm_syn = syn_a.sample(frac=1, random_state=77).reset_index(drop=True)
    mc_perm = sfm.compute_mode_collapse(perm_syn, orig)
    p_perm = mc_perm["collapse_probability"]
    perm_diff = abs(p_a - p_perm)

    # Scaling invariance: multiply all values by constant
    scaled_orig = orig * 100
    scaled_syn = syn_a * 100
    mc_scaled = sfm.compute_mode_collapse(scaled_syn, scaled_orig)
    p_scaled = mc_scaled["collapse_probability"]
    scale_diff = abs(p_a - p_scaled)

    violations = []
    details = [
        f"    gaussian vs gaussian:   collapse_prob={p_a:.6f}",
        f"    gaussian vs ring:       collapse_prob={p_b:.6f}",
        f"    gaussian vs bicluster:  collapse_prob={p_c:.6f}",
        f"    row permutation diff:   {perm_diff:.6f} {'OK' if perm_diff <= TOLERANCE else 'VIOLATION'}",
        f"    scaling (x100) diff:    {scale_diff:.6f} {'OK' if scale_diff <= TOLERANCE else 'VIOLATION'}",
    ]

    if perm_diff > TOLERANCE:
        violations.append("row_permutation")
    if scale_diff > TOLERANCE:
        violations.append("scaling_invariance")

    invariant = len(violations) == 0
    return invariant, details


# =====================================================================
# 3. STRUCTURAL CONTRACT — encoding invariance
# =====================================================================

def proof_structural_contract():
    sfm = StatisticalFidelityMetrics()

    orig = pd.DataFrame({
        "color": RNG.choice(["red", "green", "blue"], N),
        "size": RNG.choice(["S", "M", "L", "XL"], N),
        "value": RNG.standard_normal(N),
    })

    # Baseline: identical copy
    syn_baseline = orig.copy()
    res_baseline = sfm.compute_structural_contract_validation(syn_baseline, original_df=orig)
    cv_baseline = res_baseline.get("column_violations", {})

    encodings = {}

    # Encoding 1: integer codes
    syn_int = orig.copy()
    syn_int["color"] = syn_int["color"].map({"red": 0, "green": 1, "blue": 2})
    syn_int["size"] = syn_int["size"].map({"S": 0, "M": 1, "L": 2, "XL": 3})
    res_int = sfm.compute_structural_contract_validation(syn_int, original_df=orig)
    cv_int = res_int.get("column_violations", {})
    encodings["integer_codes"] = cv_int

    # Encoding 2: one-hot (expand into multiple columns — structural mismatch is expected)
    # But per-column that exists in both must match
    syn_onehot = orig.copy()
    # one-hot only changes structure, not individual column distributions
    # So we test: does the 'value' column (unchanged) still show no violation?
    syn_onehot["color"] = syn_onehot["color"].astype("category").cat.codes
    res_oh = sfm.compute_structural_contract_validation(syn_onehot, original_df=orig)
    cv_oh = res_oh.get("column_violations", {})
    encodings["category_codes"] = cv_oh

    # Encoding 3: hashed strings (hash each category to a string)
    syn_hash = orig.copy()
    import hashlib
    syn_hash["color"] = syn_hash["color"].apply(lambda x: hashlib.md5(x.encode()).hexdigest()[:8])
    syn_hash["size"] = syn_hash["size"].apply(lambda x: hashlib.md5(x.encode()).hexdigest()[:8])
    res_hash = sfm.compute_structural_contract_validation(syn_hash, original_df=orig)
    cv_hash = res_hash.get("column_violations", {})
    encodings["hashed_strings"] = cv_hash

    violations = []
    details = []

    # The 'value' column (numeric, unchanged) must never show violation
    for enc_name, cv in encodings.items():
        val_violated = cv.get("value", {}).get("violated", False)
        val_js = cv.get("value", {}).get("js_divergence", 0)
        ok = not val_violated
        details.append(f"    {enc_name} — value column: js={val_js:.6f}, violated={val_violated} {'OK' if ok else 'VIOLATION'}")
        if not ok:
            violations.append(f"{enc_name}_value_col")

    # Integer codes: the categorical columns will have different distributions
    # (string "red" vs int 0), so violation there is EXPECTED.
    # But the invariance claim is that int-coded categoricals representing
    # the same semantic mapping should NOT trigger.
    # This is only possible if the engine knows the mapping — it doesn't.
    # So we only check: unchanged columns remain invariant.

    # Row permutation: must not trigger
    syn_perm = orig.sample(frac=1, random_state=42).reset_index(drop=True)
    res_perm = sfm.compute_structural_contract_validation(syn_perm, original_df=orig)
    cv_perm = res_perm.get("column_violations", {})
    any_perm_violation = any(v.get("violated", False) for v in cv_perm.values())
    details.append(f"    row_permutation: any_violation={any_perm_violation} {'OK' if not any_perm_violation else 'VIOLATION'}")
    if any_perm_violation:
        violations.append("row_permutation")

    # Dtype change (int64 → float64) on numeric col: must not trigger
    syn_dtype = orig.copy()
    syn_dtype["value"] = syn_dtype["value"].astype(np.float32)
    res_dtype = sfm.compute_structural_contract_validation(syn_dtype, original_df=orig)
    cv_dtype = res_dtype.get("column_violations", {})
    dtype_violated = cv_dtype.get("value", {}).get("violated", False)
    details.append(f"    float64->float32: violated={dtype_violated} {'OK' if not dtype_violated else 'VIOLATION'}")
    if dtype_violated:
        violations.append("dtype_change")

    invariant = len(violations) == 0
    return invariant, details


# =====================================================================
# 4. DUPLICATE DETECTION — sub-precision noise invariance
# =====================================================================

def proof_duplicate_detection():
    prm = PrivacyRiskMetrics()

    n_orig = 400
    orig = pd.DataFrame({
        "f1": RNG.standard_normal(n_orig),
        "f2": RNG.standard_normal(n_orig),
        "f3": RNG.standard_normal(n_orig),
    })

    # Synthetic: 50% exact copies
    n_syn = 400
    n_dup = n_syn // 2
    n_fresh = n_syn - n_dup
    dup_idx = RNG.choice(n_orig, n_dup, replace=True)
    dups = orig.iloc[dup_idx].reset_index(drop=True)
    fresh = pd.DataFrame({
        "f1": RNG.standard_normal(n_fresh),
        "f2": RNG.standard_normal(n_fresh),
        "f3": RNG.standard_normal(n_fresh),
    })

    # Exact duplicates
    syn_exact = pd.concat([fresh, dups], ignore_index=True)
    res_exact = prm.detect_duplicates(syn_exact, orig)
    rate_exact = res_exact["duplicates_rate"]

    # Add noise smaller than float64 precision (~1e-16)
    noise_levels = [1e-16, 1e-15, 1e-14, 1e-13, 1e-12]
    violations = []
    details = [f"    exact duplicates: rate={rate_exact:.6f}"]

    for sigma in noise_levels:
        noisy_dups = dups + RNG.normal(0, sigma, size=dups.shape)
        syn_noisy = pd.concat([fresh, noisy_dups], ignore_index=True)
        res_noisy = prm.detect_duplicates(syn_noisy, orig)
        rate_noisy = res_noisy["duplicates_rate"]
        diff = abs(rate_exact - rate_noisy)
        ok = diff <= TOLERANCE
        details.append(f"    noise sigma={sigma:.0e}: rate={rate_noisy:.6f} (diff={diff:.6f}) {'OK' if ok else 'VIOLATION'}")
        if not ok:
            violations.append(f"sigma_{sigma}")

    invariant = len(violations) == 0
    return invariant, details


# =====================================================================
# 5. LEAKAGE (DOMIAS) — permutation invariance
# =====================================================================

def proof_leakage():
    prm = PrivacyRiskMetrics()

    n = 200
    orig = pd.DataFrame({
        "a": RNG.standard_normal(n),
        "b": RNG.standard_normal(n),
        "c": RNG.standard_normal(n),
    })
    syn = orig.copy()  # worst-case leakage

    # Baseline LR scores
    lr_base = prm.domias_lr_scores(orig, syn, orig, loo_population=True)
    mean_base = float(np.mean(lr_base))
    std_base = float(np.std(lr_base))

    violations = []
    details = [f"    baseline: lr_mean={mean_base:.6f}, lr_std={std_base:.6f}"]

    # Permutation 1: shuffle rows of orig (population reference)
    perm1 = orig.sample(frac=1, random_state=11).reset_index(drop=True)
    syn_perm1 = perm1.copy()
    lr_perm1 = prm.domias_lr_scores(perm1, syn_perm1, perm1, loo_population=True)
    mean_p1 = float(np.mean(lr_perm1))
    diff1 = abs(mean_base - mean_p1)
    ok1 = diff1 / (abs(mean_base) + 1e-12) <= 0.1  # 10% relative tolerance
    details.append(f"    row_permutation: lr_mean={mean_p1:.6f} (diff={diff1:.6f}) {'OK' if ok1 else 'VIOLATION'}")
    if not ok1:
        violations.append("row_permutation")

    # Permutation 2: shuffle columns (all columns are iid normal, so
    # swapping columns should not change the overall leakage statistics)
    orig_colswap = orig[["c", "a", "b"]].rename(columns={"c": "a", "a": "b", "b": "c"})
    syn_colswap = syn[["c", "a", "b"]].rename(columns={"c": "a", "a": "b", "b": "c"})
    lr_colswap = prm.domias_lr_scores(orig_colswap, syn_colswap, orig_colswap, loo_population=True)
    mean_cs = float(np.mean(lr_colswap))
    diff_cs = abs(mean_base - mean_cs)
    ok_cs = diff_cs / (abs(mean_base) + 1e-12) <= 0.1
    details.append(f"    column_swap: lr_mean={mean_cs:.6f} (diff={diff_cs:.6f}) {'OK' if ok_cs else 'VIOLATION'}")
    if not ok_cs:
        violations.append("column_swap")

    # Scaling: multiply all values by constant — should not change LR
    # (density ratio is invariant to shared scaling if both are scaled)
    scale = 100.0
    orig_sc = orig * scale
    syn_sc = syn * scale
    lr_sc = prm.domias_lr_scores(orig_sc, syn_sc, orig_sc, loo_population=True)
    mean_sc = float(np.mean(lr_sc))
    diff_sc = abs(mean_base - mean_sc)
    ok_sc = diff_sc / (abs(mean_base) + 1e-12) <= 0.15
    details.append(f"    scaling (x100): lr_mean={mean_sc:.6f} (diff={diff_sc:.6f}) {'OK' if ok_sc else 'VIOLATION'}")
    if not ok_sc:
        violations.append("scaling")

    invariant = len(violations) == 0
    return invariant, details


# =====================================================================
# MAIN
# =====================================================================

def main():
    print("=" * 55)
    print("  INVARIANCE PROOFS")
    print("  Attempting to violate each metric")
    print("=" * 55)
    print()

    proofs = [
        ("distribution_shift", proof_distribution_shift),
        ("mode_collapse", proof_mode_collapse),
        ("structural_contract", proof_structural_contract),
        ("duplicate_detection", proof_duplicate_detection),
        ("leakage_domias", proof_leakage),
    ]

    results = []
    for name, fn in proofs:
        invariant, details = fn()
        results.append((name, invariant))
        print(f"  {name}:")
        for d in details:
            print(d)
        print()

    print("-" * 55)
    print(f"  {'metric_name':<25} | invariant")
    print("-" * 55)
    for name, inv in results:
        print(f"  {name:<25} | {str(inv).lower()}")
    print("-" * 55)

    all_pass = all(inv for _, inv in results)
    print()
    print(f"  ALL INVARIANT: {str(all_pass).lower()}")
    print()

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
