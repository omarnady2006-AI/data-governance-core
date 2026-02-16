"""
Adversarial Scientific Audit — Outside Data Governance Engine

Attempts to BREAK each engine capability via counterexamples,
invariance violations, evasion attacks, and hypothesis testing.

Outputs: audit_report.json
"""

import json
import sys
import warnings
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Engine imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from governance_core.metrics.statistical_fidelity import StatisticalFidelityMetrics
from governance_core.metrics.privacy_risk import PrivacyRiskMetrics

RNG = np.random.default_rng(42)
N = 1000  # default sample size


# ============================================================================
# HELPERS
# ============================================================================

def _float(v):
    """Safely convert to JSON-friendly float."""
    if v is None:
        return None
    v = float(v)
    if np.isnan(v) or np.isinf(v):
        return None
    return round(v, 6)


def _make_baseline_df(n=N):
    """Multivariate numeric baseline with correlated columns + categorical."""
    x1 = RNG.standard_normal(n)
    x2 = x1 + RNG.standard_normal(n) * 0.5  # correlated with x1
    x3 = x1 * 2 + RNG.standard_normal(n) * 0.3  # strongly correlated with x1
    return pd.DataFrame({
        "x1": x1,
        "x2": x2,
        "x3": x3,
        "cat": RNG.choice(["A", "B", "C", "D", "E"], n),
    })


# ============================================================================
# SECTION 1 — STRUCTURAL CONTRACT ROBUSTNESS
# ============================================================================

def audit_structural_contracts():
    print("[1/5] Structural contract robustness ...")
    sfm = StatisticalFidelityMetrics()

    orig = pd.DataFrame({
        "age": RNG.integers(18, 80, N).astype(np.int64),
        "score": RNG.standard_normal(N),
        "label": RNG.choice(["X", "Y", "Z"], N),
        "active": RNG.choice([True, False], N),
    })
    # inject ~5% nulls so baseline null_rate > 0
    mask = RNG.random(N) < 0.05
    orig.loc[mask, "score"] = np.nan

    invariance_tests = {}
    sensitivity_tests = {}

    # ---------- INVARIANCE (should NOT trigger) ----------

    # 1a. int64 vs float64 — identical values
    syn_float = orig.copy()
    syn_float["age"] = syn_float["age"].astype(np.float64)
    res = sfm.compute_structural_contract_validation(syn_float, original_df=orig)
    cv = res.get("column_violations", {})
    triggered = any(v.get("violated", False) for v in cv.values())
    invariance_tests["int_vs_float"] = {
        "triggered": triggered,
        "details": {k: _float(v.get("js_divergence")) for k, v in cv.items()},
    }

    # 1b. categorical as int codes vs string labels
    syn_codes = orig.copy()
    mapping = {"X": 0, "Y": 1, "Z": 2}
    syn_codes["label"] = syn_codes["label"].map(mapping)
    res = sfm.compute_structural_contract_validation(syn_codes, original_df=orig)
    cv = res.get("column_violations", {})
    js_label = cv.get("label", {}).get("js_divergence", 0)
    invariance_tests["cat_as_int_codes"] = {
        "triggered": cv.get("label", {}).get("violated", False),
        "js_divergence": _float(js_label),
    }

    # 1c. same null ratio but different row positions
    syn_null_pos = orig.copy()
    null_col = "score"
    null_count = orig[null_col].isna().sum()
    syn_null_pos[null_col] = syn_null_pos[null_col].fillna(0)
    new_mask_idx = RNG.choice(N, size=null_count, replace=False)
    syn_null_pos.loc[new_mask_idx, null_col] = np.nan
    res = sfm.compute_structural_contract_validation(syn_null_pos, original_df=orig)
    nt = res.get("nullability_tests", {})
    p_val = nt.get(null_col, {}).get("p_value", 1.0)
    invariance_tests["null_position_shuffle"] = {
        "triggered": p_val is not None and p_val < 0.05,
        "p_value": _float(p_val),
    }

    # 1d. row permutation only
    syn_perm = orig.sample(frac=1, random_state=7).reset_index(drop=True)
    res = sfm.compute_structural_contract_validation(syn_perm, original_df=orig)
    cv = res.get("column_violations", {})
    triggered = any(v.get("violated", False) for v in cv.values())
    invariance_tests["row_permutation"] = {"triggered": triggered}

    # ---------- SENSITIVITY (MUST trigger) ----------

    # 1e. swap two columns with same dtype (semantic break)
    syn_swap = orig.copy()
    syn_swap["age"], syn_swap["score"] = (
        orig["score"].copy(),
        orig["age"].astype(float).copy(),
    )
    res = sfm.compute_structural_contract_validation(syn_swap, original_df=orig)
    cv = res.get("column_violations", {})
    cs = res.get("column_swap_violations", {})
    nt = res.get("nullability_tests", {})
    detected_cv = any(v.get("violated", False) for v in cv.values())
    detected_cs = any(v.get("violated", False) for v in cs.values())
    detected_nt = any(v.get("violated", False) for v in nt.values())
    detected = detected_cv or detected_cs or detected_nt
    sensitivity_tests["swapped_columns"] = {"detected": detected}

    # 1f. column replaced with random data of same dtype
    syn_rand = orig.copy()
    syn_rand["age"] = RNG.integers(0, 1000, N)
    res = sfm.compute_structural_contract_validation(syn_rand, original_df=orig)
    cv = res.get("column_violations", {})
    cs = res.get("column_swap_violations", {})
    detected_cv = any(v.get("violated", False) for v in cv.values())
    detected_cs = any(v.get("violated", False) for v in cs.values())
    sensitivity_tests["random_replacement"] = {
        "detected": detected_cv or detected_cs
    }

    # 1g. all nulls injected in non-nullable column
    syn_all_null = orig.copy()
    syn_all_null["age"] = np.nan
    res = sfm.compute_structural_contract_validation(syn_all_null, original_df=orig)
    nt = res.get("nullability_tests", {})
    p_age = nt.get("age", {}).get("p_value", 1)
    sensitivity_tests["all_nulls"] = {
        "detected": p_age is not None and p_age < 0.05,
        "p_value": _float(p_age),
    }

    # --- metrics ---
    inv_failures = [k for k, v in invariance_tests.items() if v.get("triggered")]
    sens_failures = [k for k, v in sensitivity_tests.items() if not v.get("detected")]

    n_inv = len(invariance_tests)
    n_sens = len(sensitivity_tests)
    fp = len(inv_failures)
    fn = len(sens_failures)
    tp = n_sens - fn
    tn = n_inv - fp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    adversarial_fpr = fp / n_inv if n_inv > 0 else 0.0

    return {
        "precision": _float(precision),
        "recall": _float(recall),
        "adversarial_false_positive_rate": _float(adversarial_fpr),
        "invariance_tests": invariance_tests,
        "sensitivity_tests": sensitivity_tests,
        "invariance_failures": inv_failures,
        "sensitivity_failures": sens_failures,
        "pass_or_fail": "PASS" if (adversarial_fpr <= 0.25 and recall >= 0.5) else "FAIL",
    }


# ============================================================================
# SECTION 2 — DISTRIBUTION SHIFT RELIABILITY
# ============================================================================

def audit_distribution_shift():
    print("[2/5] Distribution shift reliability ...")
    sfm = StatisticalFidelityMetrics()

    orig = _make_baseline_df(N)

    # invariance cases (label=0 -> should NOT trigger)
    invariance_cases = {}

    # 2a. row permutation
    syn = orig.sample(frac=1, random_state=99).reset_index(drop=True)
    res = sfm.compute_distribution_shift(syn, orig)
    invariance_cases["row_permutation"] = {
        "shift_score": _float(res["shift_score"]),
        "label": 0,
    }

    # 2b. monotonic scaling x -> 2x (numeric cols only)
    syn = orig.copy()
    for c in ["x1", "x2", "x3"]:
        syn[c] = syn[c] * 2.0
    res = sfm.compute_distribution_shift(syn, orig)
    invariance_cases["monotonic_2x"] = {
        "shift_score": _float(res["shift_score"]),
        "label": 0,
    }

    # 2c. unit change x -> 100x
    syn = orig.copy()
    for c in ["x1", "x2", "x3"]:
        syn[c] = syn[c] * 100.0
    res = sfm.compute_distribution_shift(syn, orig)
    invariance_cases["unit_change_100x"] = {
        "shift_score": _float(res["shift_score"]),
        "label": 0,
    }

    # sensitivity cases (label=1 -> MUST trigger)
    sensitivity_cases = {}

    # 2d. 20% mixture injection
    syn = orig.copy()
    n_inject = int(0.2 * N)
    idx = RNG.choice(N, n_inject, replace=False)
    syn.loc[idx, "x1"] = RNG.normal(10, 1, n_inject)
    res = sfm.compute_distribution_shift(syn, orig)
    sensitivity_cases["mixture_injection"] = {
        "shift_score": _float(res["shift_score"]),
        "copula_distance": _float(res.get("copula_distance", 0)),
        "label": 1,
    }

    # 2e. conditional shift — different mean for first half
    syn = orig.copy()
    syn.loc[: N // 2, "x1"] = syn.loc[: N // 2, "x1"] + 3.0
    res = sfm.compute_distribution_shift(syn, orig)
    sensitivity_cases["conditional_shift"] = {
        "shift_score": _float(res["shift_score"]),
        "copula_distance": _float(res.get("copula_distance", 0)),
        "label": 1,
    }

    # 2f. covariate interaction change — flip correlation
    syn = orig.copy()
    syn["x2"] = -syn["x2"]
    res = sfm.compute_distribution_shift(syn, orig)
    sensitivity_cases["correlation_flip"] = {
        "shift_score": _float(res["shift_score"]),
        "copula_distance": _float(res.get("copula_distance", 0)),
        "label": 1,
    }

    # 2g. heavy tail (replace x1 with Student-t)
    syn = orig.copy()
    syn["x1"] = RNG.standard_t(3, N)
    res = sfm.compute_distribution_shift(syn, orig)
    sensitivity_cases["heavy_tail"] = {
        "shift_score": _float(res["shift_score"]),
        "copula_distance": _float(res.get("copula_distance", 0)),
        "label": 1,
    }

    # 2h. rank-preserving x -> x^3 (changes shape: Normal -> heavy-tailed)
    syn = orig.copy()
    for c in ["x1", "x2", "x3"]:
        syn[c] = syn[c] ** 3
    res = sfm.compute_distribution_shift(syn, orig)
    sensitivity_cases["rank_preserving_cube"] = {
        "shift_score": _float(res["shift_score"]),
        "copula_distance": _float(res.get("copula_distance", 0)),
        "label": 1,
    }

    # --- ROC / calibration ---
    all_cases = {**invariance_cases, **sensitivity_cases}
    scores = [v["shift_score"] or 0 for v in all_cases.values()]
    labels = [v["label"] for v in all_cases.values()]

    # Use combined score: max(shift_score, copula_distance / num_cols_norm)
    # to capture both marginal and structural changes
    combined_scores = []
    for v in all_cases.values():
        s_val = v.get("shift_score") or 0
        c_val = (v.get("copula_distance") or 0) / max(1.0, 3.0)  # normalize
        combined_scores.append(max(s_val, c_val))
    scores = combined_scores

    pos_scores = [s for s, l in zip(scores, labels) if l == 1]
    neg_scores = [s for s, l in zip(scores, labels) if l == 0]

    if pos_scores and neg_scores:
        u_stat, u_p = stats.mannwhitneyu(pos_scores, neg_scores, alternative="greater")
        roc_auc = u_stat / (len(pos_scores) * len(neg_scores))
    else:
        roc_auc = None
        u_p = 1.0

    threshold = np.median(scores)
    predicted_positive = [1 if s > threshold else 0 for s in scores]
    calibration_error = abs(
        np.mean([l for l, p in zip(labels, predicted_positive) if p == 1])
        - np.mean([s for s, p in zip(scores, predicted_positive) if p == 1])
    ) if any(p == 1 for p in predicted_positive) else None

    # Invariance failure = combined_score > 0.1 for label=0
    inv_failures = []
    for k, v in invariance_cases.items():
        s_val = v.get("shift_score") or 0
        c_val = (v.get("copula_distance") or 0) / max(1.0, 3.0)
        if max(s_val, c_val) > 0.1:
            inv_failures.append(k)

    # Sensitivity failure = combined_score < 0.05 for label=1
    sens_failures = []
    for k, v in sensitivity_cases.items():
        s_val = v.get("shift_score") or 0
        c_val = (v.get("copula_distance") or 0) / max(1.0, 3.0)
        if max(s_val, c_val) < 0.05:
            sens_failures.append(k)

    return {
        "roc_auc": _float(roc_auc),
        "mann_whitney_p": _float(u_p),
        "calibration_error": _float(calibration_error),
        "invariance_cases": invariance_cases,
        "sensitivity_cases": sensitivity_cases,
        "invariance_failures": inv_failures,
        "sensitivity_failures": sens_failures,
        "pass_or_fail": "PASS" if (
            roc_auc is not None and roc_auc >= 0.7
            and len(sens_failures) == 0
        ) else "FAIL",
    }


# ============================================================================
# SECTION 3 — MODE COLLAPSE FAILURE CASES
# ============================================================================

def audit_mode_collapse():
    print("[3/5] Mode collapse failure cases ...")
    sfm = StatisticalFidelityMetrics()

    # Multi-modal original
    orig = pd.DataFrame({
        "v1": np.concatenate([
            RNG.normal(-5, 1, N // 3),
            RNG.normal(0, 1, N // 3),
            RNG.normal(5, 1, N - 2 * (N // 3)),
        ]),
        "v2": np.concatenate([
            RNG.normal(0, 2, N // 2),
            RNG.normal(8, 2, N - N // 2),
        ]),
    })

    results = {}
    collapse_probs = {}

    # 3a. Identical distribution (control, should be low)
    syn = orig.sample(frac=1, random_state=1).reset_index(drop=True)
    mc = sfm.compute_mode_collapse(syn, orig)
    results["identical"] = {
        "collapse_probability": _float(mc["collapse_probability"]),
        "lid_original": _float(mc.get("intrinsic_dimensionality_original")),
        "lid_synthetic": _float(mc.get("intrinsic_dimensionality_synthetic")),
        "expected": "low",
    }
    collapse_probs["identical"] = mc["collapse_probability"]

    # 3b. Lattice sampling — preserves mean/std but collapses support
    v1_grid = np.linspace(orig["v1"].min(), orig["v1"].max(), N)
    v2_grid = np.linspace(orig["v2"].min(), orig["v2"].max(), N)
    for arr, col in [(v1_grid, "v1"), (v2_grid, "v2")]:
        arr -= arr.mean()
        arr /= (arr.std() + 1e-12)
        arr *= orig[col].std()
        arr += orig[col].mean()
    syn = pd.DataFrame({"v1": v1_grid, "v2": v2_grid})
    mc = sfm.compute_mode_collapse(syn, orig)
    results["lattice"] = {
        "collapse_probability": _float(mc["collapse_probability"]),
        "lid_original": _float(mc.get("intrinsic_dimensionality_original")),
        "lid_synthetic": _float(mc.get("intrinsic_dimensionality_synthetic")),
        "expected": "high (uniform lattice erases modes)",
    }
    collapse_probs["lattice"] = mc["collapse_probability"]

    # 3c. Repeated tight clusters
    cluster_centers = [(-5, 0), (0, 4), (5, 8)]
    pts_per = N // len(cluster_centers)
    v1_parts, v2_parts = [], []
    for cx, cy in cluster_centers:
        v1_parts.append(RNG.normal(cx, 0.01, pts_per))
        v2_parts.append(RNG.normal(cy, 0.01, pts_per))
    remainder = N - pts_per * len(cluster_centers)
    if remainder > 0:
        v1_parts.append(RNG.normal(0, 0.01, remainder))
        v2_parts.append(RNG.normal(4, 0.01, remainder))
    syn = pd.DataFrame({
        "v1": np.concatenate(v1_parts),
        "v2": np.concatenate(v2_parts),
    })
    mc = sfm.compute_mode_collapse(syn, orig)
    results["repeated_clusters"] = {
        "collapse_probability": _float(mc["collapse_probability"]),
        "lid_original": _float(mc.get("intrinsic_dimensionality_original")),
        "lid_synthetic": _float(mc.get("intrinsic_dimensionality_synthetic")),
        "expected": "high (tight clusters = low entropy)",
    }
    collapse_probs["repeated_clusters"] = mc["collapse_probability"]

    # 3d. Projection to rank-1 manifold
    direction = np.array([1.0, 0.5])
    direction /= np.linalg.norm(direction)
    t = RNG.standard_normal(N)
    t = t * orig["v1"].std() + orig["v1"].mean()
    syn = pd.DataFrame({
        "v1": t * direction[0],
        "v2": t * direction[1],
    })
    mc = sfm.compute_mode_collapse(syn, orig)
    results["low_dim_projection"] = {
        "collapse_probability": _float(mc["collapse_probability"]),
        "lid_original": _float(mc.get("intrinsic_dimensionality_original")),
        "lid_synthetic": _float(mc.get("intrinsic_dimensionality_synthetic")),
        "expected": "high (rank-1 support)",
    }
    collapse_probs["low_dim_projection"] = mc["collapse_probability"]

    # 3e. Constant columns
    syn = pd.DataFrame({"v1": np.zeros(N), "v2": np.zeros(N)})
    mc = sfm.compute_mode_collapse(syn, orig)
    results["constant"] = {
        "collapse_probability": _float(mc["collapse_probability"]),
        "expected": "maximal",
    }
    collapse_probs["constant"] = mc["collapse_probability"]

    # --- metrics ---
    adversarial_cases = ["lattice", "repeated_clusters", "low_dim_projection", "constant"]
    threshold = 0.3
    undetected = [c for c in adversarial_cases if collapse_probs.get(c, 0) < threshold]
    undetected_rate = len(undetected) / len(adversarial_cases)

    expected_order = ["identical", "lattice", "repeated_clusters", "constant"]
    actual_vals = [collapse_probs.get(k, 0) for k in expected_order]
    if len(set(actual_vals)) > 1:
        spearman_r, spearman_p = stats.spearmanr(range(len(expected_order)), actual_vals)
    else:
        spearman_r, spearman_p = 0.0, 1.0

    return {
        "collapse_probabilities": {k: _float(v) for k, v in collapse_probs.items()},
        "cases": results,
        "undetected_collapses": undetected,
        "undetected_collapse_rate": _float(undetected_rate),
        "monotonicity_spearman_r": _float(spearman_r),
        "monotonicity_spearman_p": _float(spearman_p),
        "pass_or_fail": "PASS" if (undetected_rate <= 0.25 and (spearman_r or 0) >= 0.6) else "FAIL",
    }


# ============================================================================
# SECTION 4 — DUPLICATE DETECTION EVASION
# ============================================================================

def audit_duplicate_evasion():
    print("[4/5] Duplicate detection evasion ...")
    prm = PrivacyRiskMetrics()

    n_orig = 500
    orig = pd.DataFrame({
        "f1": RNG.standard_normal(n_orig),
        "f2": RNG.standard_normal(n_orig),
        "f3": RNG.standard_normal(n_orig),
    })

    # Create synthetic with 30% exact duplicates injected
    n_syn = 500
    n_dup = int(0.3 * n_syn)
    n_fresh = n_syn - n_dup
    dup_idx = RNG.choice(n_orig, n_dup, replace=True)
    fresh = pd.DataFrame({
        "f1": RNG.standard_normal(n_fresh),
        "f2": RNG.standard_normal(n_fresh),
        "f3": RNG.standard_normal(n_fresh),
    })
    dups = orig.iloc[dup_idx].reset_index(drop=True)

    noise_levels = [0, 1e-10, 1e-6, 1e-4, 1e-2, 0.1, 0.5]
    evasion_curve = {}

    for sigma in noise_levels:
        noisy_dups = dups.copy()
        if sigma > 0:
            noise = RNG.normal(0, sigma, size=noisy_dups.shape)
            noisy_dups = noisy_dups + noise
        syn = pd.concat([fresh, noisy_dups], ignore_index=True)
        syn = syn.sample(frac=1, random_state=77).reset_index(drop=True)

        result = prm.detect_duplicates(syn, original_df=orig)
        evasion_curve[str(sigma)] = {
            "duplicates_rate": _float(result["duplicates_rate"]),
            "epsilon": _float(result["epsilon"]),
        }

    # How fast does detection degrade?
    rates = [evasion_curve[str(s)]["duplicates_rate"] or 0 for s in noise_levels]
    detection_at_zero = rates[0]

    # Find smallest sigma where detection drops to < 50% of initial
    critical_sigma = None
    for i, sigma in enumerate(noise_levels[1:], 1):
        if rates[i] < 0.5 * detection_at_zero and detection_at_zero > 0:
            critical_sigma = sigma
            break

    # Robustness at small noise
    rate_at_small_noise = evasion_curve.get(str(1e-4), {}).get("duplicates_rate", 0) or 0

    return {
        "evasion_curve": evasion_curve,
        "detection_at_zero_noise": _float(detection_at_zero),
        "critical_evasion_sigma": _float(critical_sigma),
        "detection_at_1e-4_noise": _float(rate_at_small_noise),
        "pass_or_fail": "PASS" if (
            detection_at_zero > 0.2
            and (critical_sigma is None or critical_sigma >= 1e-4)
        ) else "FAIL",
    }


# ============================================================================
# SECTION 5 — PRIVACY ATTACK VALIDITY (DOMIAS)
# ============================================================================

def audit_domias_attack():
    print("[5/5] DOMIAS attack validity ...")
    prm = PrivacyRiskMetrics()

    n = 300
    orig = pd.DataFrame({
        "a": RNG.standard_normal(n),
        "b": RNG.standard_normal(n),
        "c": RNG.standard_normal(n),
    })

    # Use original as synthetic (worst-case leakage)
    syn = orig.copy()

    # Non-members: fresh noise
    non_members = pd.DataFrame({
        "a": RNG.standard_normal(n),
        "b": RNG.standard_normal(n),
        "c": RNG.standard_normal(n),
    })

    # Member LR scores
    lr_members = prm.domias_lr_scores(orig, syn, orig, loo_population=True)

    # Non-member LR scores
    lr_non_members = prm.domias_lr_scores(orig, syn, non_members, loo_population=False)

    # Hypothesis test: H0: LR_member == LR_nonmember
    u_stat, u_p = stats.mannwhitneyu(lr_members, lr_non_members, alternative="greater")

    # AUC
    auc = prm._auc_from_scores(lr_members, lr_non_members)

    # --- Quantile-binned calibration ---
    all_lr = np.concatenate([lr_members, lr_non_members])
    all_labels = np.array([1] * len(lr_members) + [0] * len(lr_non_members))

    n_bins = 10
    ece = 0.0
    if len(all_lr) > n_bins:
        bin_edges = np.quantile(all_lr, np.linspace(0, 1, n_bins + 1))
        for i in range(n_bins):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            if i == n_bins - 1:
                mask = (all_lr >= lo) & (all_lr <= hi)
            else:
                mask = (all_lr >= lo) & (all_lr < hi)
            if mask.sum() == 0:
                continue
            # In each quantile bin: compare actual positive rate to mean LR rank
            bin_positive_rate = all_labels[mask].mean()
            # Use rank-based confidence (fraction of bin above global median)
            bin_rank_confidence = (all_lr[mask] > np.median(all_lr)).mean()
            ece += (mask.sum() / len(all_labels)) * abs(bin_positive_rate - bin_rank_confidence)

    attack_valid = u_p < 0.05

    # Test with independent synthetic (should show AUC ~ 0.5)
    independent_syn = pd.DataFrame({
        "a": RNG.standard_normal(n),
        "b": RNG.standard_normal(n),
        "c": RNG.standard_normal(n),
    })
    lr_mem_ind = prm.domias_lr_scores(orig, independent_syn, orig, loo_population=True)
    lr_nonmem_ind = prm.domias_lr_scores(orig, independent_syn, non_members, loo_population=False)
    auc_independent = prm._auc_from_scores(lr_mem_ind, lr_nonmem_ind)
    _, u_p_ind = stats.mannwhitneyu(lr_mem_ind, lr_nonmem_ind, alternative="greater")

    discriminability = (auc or 0.5) - (auc_independent or 0.5)

    return {
        "membership_hypothesis_p_value": _float(u_p),
        "attack_valid": attack_valid,
        "auc_leaked_synthetic": _float(auc),
        "auc_independent_synthetic": _float(auc_independent),
        "discriminability_gap": _float(discriminability),
        "quantile_calibration_error": _float(ece),
        "independent_attack_p_value": _float(u_p_ind),
        "lr_member_mean": _float(float(np.mean(lr_members))),
        "lr_nonmember_mean": _float(float(np.mean(lr_non_members))),
        "pass_or_fail": "PASS" if (
            attack_valid
            and (auc or 0) > 0.6
            and discriminability > 0.1
        ) else "FAIL",
    }


# ============================================================================
# MAIN — ASSEMBLE AUDIT REPORT
# ============================================================================

def main():
    print("=" * 60)
    print("  ADVERSARIAL SCIENTIFIC AUDIT")
    print("  Outside Data Governance Engine")
    print("=" * 60)

    s1 = audit_structural_contracts()
    s2 = audit_distribution_shift()
    s3 = audit_mode_collapse()
    s4 = audit_duplicate_evasion()
    s5 = audit_domias_attack()

    # --- Global metrics ---
    all_inv_failures = (
        s1.get("invariance_failures", [])
        + s2.get("invariance_failures", [])
    )

    section_passes = [
        s1["pass_or_fail"] == "PASS",
        s2["pass_or_fail"] == "PASS",
        s3["pass_or_fail"] == "PASS",
        s4["pass_or_fail"] == "PASS",
        s5["pass_or_fail"] == "PASS",
    ]

    robustness_score = sum(section_passes) / len(section_passes)

    final_verdict = "PASS" if all(section_passes) else "SCIENTIFICALLY_UNRELIABLE"

    report = {
        "robustness_score": _float(robustness_score),
        "invariance_failures": all_inv_failures,
        "undetected_collapse_rate": s3.get("undetected_collapse_rate"),
        "duplicate_evasion_curve": s4.get("evasion_curve"),
        "membership_hypothesis_p_value": s5.get("membership_hypothesis_p_value"),
        "calibration_error": s5.get("quantile_calibration_error"),
        "final_verdict": final_verdict,
        "sections": {
            "structural_contract": s1,
            "distribution_shift": s2,
            "mode_collapse": s3,
            "duplicate_detection": s4,
            "leakage_attack": s5,
        },
    }

    out_path = Path(__file__).resolve().parent.parent / "audit_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print()
    print("=" * 60)
    print(f"  FINAL VERDICT: {final_verdict}")
    print(f"  Robustness Score: {robustness_score:.0%}")
    print(f"  Report: {out_path}")
    print("=" * 60)

    names = [
        "structural_contract", "distribution_shift",
        "mode_collapse", "duplicate_detection", "leakage_attack",
    ]
    verdicts = [s1, s2, s3, s4, s5]
    for name, v in zip(names, verdicts):
        status = v["pass_or_fail"]
        marker = "[OK]" if status == "PASS" else "[!!]"
        print(f"  {marker} {name}: {status}")

    print()
    return 0 if final_verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
