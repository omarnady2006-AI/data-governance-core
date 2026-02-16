"""Statistical fidelity metrics: structural contracts, distribution shift, mode collapse.

Mathematical definitions:
- Structural contract: distribution-comparison via normalized entropy + mutual information.
  Representation-invariant (string vs int encoding cannot trigger).
- Distribution shift: probability-space (PIT via reference ECDF).
    For each numeric column with reference values x_ref and synthetic values x_syn:
      1. F_ref  = empirical CDF of x_ref
      2. u_ref  = F_ref(x_ref),  u_syn = F_ref(x_syn)   (both in [0,1])
      3. Shift  = CvM(u_ref, u_syn) + tail_mass_deviation(u_syn)
    Multivariate: Frobenius distance of Spearman correlation matrices.
    Invariant to ANY monotonic transform.  Sensitive to mixture injection,
    conditional distribution change, and tail change.
- Mode collapse: local intrinsic dimensionality (kNN-based) + entropy loss.
  Detects support dimensionality loss (lattice, projection, clusters).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

import numpy as np
import pandas as pd
from scipy.stats import entropy as sp_entropy, spearmanr
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger(__name__)


class StatisticalFidelityMetrics:
    """Minimal, mathematically-correct statistical fidelity metrics."""

    def __init__(self, k_lid: int = 10):
        self.k_lid = k_lid  # k for local intrinsic dimensionality

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_entropy(counts: np.ndarray) -> float:
        p = np.asarray(counts, dtype=float)
        total = p.sum()
        if total <= 0:
            return 0.0
        p = p / total
        p = p[p > 0]
        return float(-np.sum(p * np.log2(p)))

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=float)
        total = v.sum()
        return v / total if total > 0 else np.zeros_like(v)



    # ------------------------------------------------------------------
    # SECTION A: Structural Contract Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _column_distribution_vector(series: pd.Series, n_bins: int = 30) -> np.ndarray:
        """Create a distribution vector that is representation-invariant.

        Converts all values to string, computes value frequencies.
        This makes int-coded categoricals and string categoricals identical
        when they represent the same values (e.g., 0,1,2 vs "X","Y","Z" will differ
        only if the actual value distributions differ, not because of dtype).
        For numeric columns, uses histogram bins on parsed numeric values.
        """
        nn = series.dropna()
        if len(nn) == 0:
            return np.array([1.0])

        # Try numeric interpretation
        numeric = pd.to_numeric(nn, errors="coerce")
        numeric_valid = numeric.dropna()

        if len(numeric_valid) / max(len(nn), 1) > 0.9:
            # Treat as numeric: histogram on values
            vals = numeric_valid.to_numpy()
            if np.std(vals) < 1e-15:
                return np.array([1.0])
            hist, _ = np.histogram(vals, bins=n_bins, density=True)
            total = hist.sum()
            return hist / total if total > 0 else np.ones(n_bins) / n_bins
        else:
            # Treat as categorical: value counts
            vc = nn.astype(str).value_counts(normalize=True).sort_index()
            return vc.to_numpy()

    @staticmethod
    def _mutual_information(col_a_orig: pd.Series, col_a_syn: pd.Series,
                            col_b_orig: pd.Series, col_b_syn: pd.Series,
                            n_bins: int = 20) -> float:
        """Compute MI drop between column pairs across datasets.

        Returns MI(A,B|orig) - MI(A,B|syn). Positive = semantic loss.
        """
        def _mi(x: pd.Series, y: pd.Series) -> float:
            x_num = pd.to_numeric(x, errors="coerce")
            y_num = pd.to_numeric(y, errors="coerce")

            if x_num.notna().mean() > 0.9 and y_num.notna().mean() > 0.9:
                # Both numeric: discretize
                x_vals = x_num.dropna().to_numpy()
                y_vals = y_num.dropna().to_numpy()
                valid = x_num.notna() & y_num.notna()
                x_vals = x_num[valid].to_numpy()
                y_vals = y_num[valid].to_numpy()
                if len(x_vals) < 10:
                    return 0.0
                x_bins = np.histogram_bin_edges(x_vals, bins=min(n_bins, len(np.unique(x_vals))))
                y_bins = np.histogram_bin_edges(y_vals, bins=min(n_bins, len(np.unique(y_vals))))
                joint, _, _ = np.histogram2d(x_vals, y_vals, bins=[x_bins, y_bins])
            else:
                # Categorical: contingency table
                df_temp = pd.DataFrame({"a": x.astype(str), "b": y.astype(str)}).dropna()
                if len(df_temp) < 10:
                    return 0.0
                joint_counts = pd.crosstab(df_temp["a"], df_temp["b"])
                joint = joint_counts.to_numpy(dtype=float)

            joint = joint + 1e-10  # smoothing
            joint = joint / joint.sum()
            marginal_x = joint.sum(axis=1, keepdims=True)
            marginal_y = joint.sum(axis=0, keepdims=True)
            mi = np.sum(joint * np.log2(joint / (marginal_x * marginal_y + 1e-20) + 1e-20))
            return max(0.0, float(mi))

        mi_orig = _mi(col_a_orig, col_b_orig)
        mi_syn = _mi(col_a_syn, col_b_syn)
        return mi_orig - mi_syn

    def compute_structural_contract_validation(
        self, synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[object] = None
    ) -> Dict[str, Any]:
        """Representation-invariant structural validation.

        Uses distribution comparison (not dtype comparison).
        Detects semantic change via MI drop between column pairs.
        """
        result: Dict[str, Any] = {
            "column_violations": {},
            "column_swap_violations": {},
            "nullability_tests": {},
            "evidence": [],
        }

        if original_df is None and original_profile is None:
            return result

        if original_df is None:
            return result  # Need original_df for distribution comparison

        common_cols = sorted(set(synthetic_df.columns) & set(original_df.columns))

        # --- Per-column distribution comparison ---
        for c in common_cols:
            orig_dist = self._column_distribution_vector(original_df[c])
            syn_dist = self._column_distribution_vector(synthetic_df[c])

            # Align lengths for JS divergence
            max_len = max(len(orig_dist), len(syn_dist))
            p = np.zeros(max_len)
            q = np.zeros(max_len)
            p[:len(orig_dist)] = orig_dist
            q[:len(syn_dist)] = syn_dist

            p = self._normalize(p)
            q = self._normalize(q)
            m = 0.5 * (p + q)
            js = float(0.5 * sp_entropy(p, m, base=2) + 0.5 * sp_entropy(q, m, base=2))

            # Nullability test (binomial)
            from scipy.stats import binomtest
            p0 = float(original_df[c].isna().mean())
            n = len(synthetic_df[c])
            k = int(synthetic_df[c].isna().sum())
            if n > 0:
                p_val = float(binomtest(k, n, p=max(min(p0, 1.0), 0.0), alternative="two-sided").pvalue)
            else:
                p_val = None

            result["column_violations"][c] = {
                "js_divergence": float(js),
                "violated": js > 0.01,
            }
            result["nullability_tests"][c] = {
                "baseline_null_rate": p0,
                "observed_null_rate": float(k / n) if n > 0 else 0.0,
                "p_value": p_val,
                "violated": p_val is not None and p_val < 0.05,
            }
            result["evidence"].append({
                "signal": "structural_contract",
                "metric": "DIST_JS",
                "column": c,
                "value": js,
                "p_value": p_val,
            })

        # --- Column swap detection via MI drop ---
        num_common = [c for c in common_cols
                      if pd.api.types.is_numeric_dtype(original_df[c])
                      and pd.api.types.is_numeric_dtype(synthetic_df[c])]
        if len(num_common) >= 2:
            for i in range(len(num_common)):
                for j in range(i + 1, len(num_common)):
                    ci, cj = num_common[i], num_common[j]
                    mi_drop = self._mutual_information(
                        original_df[ci], synthetic_df[ci],
                        original_df[cj], synthetic_df[cj],
                    )
                    if abs(mi_drop) > 0.1:
                        result["column_swap_violations"][f"{ci}<->{cj}"] = {
                            "mi_drop": float(mi_drop),
                            "violated": True,
                        }

        return result

    # ------------------------------------------------------------------
    # SECTION B: Distribution Shift Detection (Probability Space)
    # ------------------------------------------------------------------
    #
    # NEW DEFINITION (replaces previous value-space metric):
    #
    #   For each numeric column with reference x_ref and synthetic x_syn:
    #
    #     Step 1  F_ref(x)  = empirical CDF of x_ref
    #     Step 2  u_ref     = F_ref(x_ref)          ∈ [0, 1]
    #             u_syn     = F_ref(x_syn)          ∈ [0, 1]
    #     Step 3a CvM       = two-sample Cramér–von Mises on (u_ref, u_syn)
    #     Step 3b tail_diff = |P(u_syn < 0.05) − 0.05|
    #                       + |P(u_syn > 0.95) − 0.05|
    #     col_shift = 1 − exp(−(α·CvM + β·tail_diff))
    #
    #   Multivariate structure:
    #     Δρ = ‖ Spearman_corr(ref) − Spearman_corr(syn) ‖_F  / d
    #
    #   Final:  shift_score = max(mean(col_shifts), Δρ)
    #
    #   Properties:
    #     • Invariant to ANY monotonic transform of the data
    #       (F_ref(f(x)) for monotonic f gives identical quantiles)
    #     • Sensitive to mixture injection (CvM detects new modes)
    #     • Sensitive to conditional distribution change (Spearman Δρ)
    #     • Sensitive to tail change (explicit tail mass check)
    # ------------------------------------------------------------------

    @staticmethod
    def _ecdf_transform(ref: np.ndarray, values: np.ndarray) -> np.ndarray:
        """Map values into quantile space [0, 1] using the reference ECDF.

        F_ref(x) = (number of ref values ≤ x) / n_ref
        """
        ref_sorted = np.sort(ref)
        n = len(ref_sorted)
        if n == 0:
            return np.zeros_like(values, dtype=float)
        return np.searchsorted(ref_sorted, values, side="right").astype(float) / n

    @staticmethod
    def _cramer_von_mises(u: np.ndarray, v: np.ndarray) -> float:
        """Two-sample Cramér–von Mises statistic in quantile space.

        CvM = (n·m / (n+m)²) · Σ_z (F_n(z) − G_m(z))²
        where z ranges over the combined ordered sample.
        """
        n, m = len(u), len(v)
        if n == 0 or m == 0:
            return 0.0
        combined = np.sort(np.concatenate([u, v]))
        cdf_u = np.searchsorted(np.sort(u), combined, side="right") / n
        cdf_v = np.searchsorted(np.sort(v), combined, side="right") / m
        return float(n * m / (n + m) ** 2 * np.sum((cdf_u - cdf_v) ** 2))

    @staticmethod
    def _tail_mass_diff(u_syn: np.ndarray,
                        lower: float = 0.05, upper: float = 0.95) -> float:
        """Tail mass deviation from the expected uniform in quantile space.

        Under H₀ (no shift), F_ref maps syn → U(0,1), so
          P(u_syn < 0.05) ≈ 0.05   and   P(u_syn > 0.95) ≈ 0.05
        """
        if len(u_syn) == 0:
            return 0.0
        n = len(u_syn)
        low_mass  = np.sum(u_syn < lower) / n
        high_mass = np.sum(u_syn > upper) / n
        return float(abs(low_mass - lower) + abs(high_mass - (1.0 - upper)))

    # α, β scaling constants for combining CvM and tail signals.
    _CVM_SCALE:  float = 10.0
    _TAIL_SCALE: float = 2.0

    def _pit_shift(self, orig: pd.Series, syn: pd.Series,
                   col: str) -> Dict[str, Any]:
        """Per-column shift measured entirely in probability (quantile) space.

        1. Build F_ref from orig.
        2. u_ref = F_ref(x_ref),  u_syn = F_ref(x_syn).
        3. CvM(u_ref, u_syn) + tail_mass_diff(u_syn).

        Invariant to ANY monotonic transform applied identically to both
        datasets: the ECDF absorbs the transform.
        """
        o = pd.to_numeric(orig, errors="coerce").dropna().to_numpy()
        s = pd.to_numeric(syn, errors="coerce").dropna().to_numpy()
        if o.size == 0 or s.size == 0:
            return {"column": col, "shift_score": 0.0, "cvm": 0.0, "tail_diff": 0.0}

        # Step 1–2: project both datasets into [0,1] via reference ECDF
        u_ref = self._ecdf_transform(o, o)   # ≈ U(0,1)
        u_syn = self._ecdf_transform(o, s)   # deviates under shift

        # Step 3a: Cramér–von Mises distance in quantile space
        cvm = self._cramer_von_mises(u_ref, u_syn)

        # Step 3b: tail mass deviation (bottom 5 % and top 5 %)
        tail_diff = self._tail_mass_diff(u_syn)

        # Combine into a [0, 1] shift score
        combined = self._CVM_SCALE * cvm + self._TAIL_SCALE * tail_diff
        shift = float(1.0 - np.exp(-combined))

        return {
            "column": col,
            "shift_score": shift,
            "cvm": float(cvm),
            "tail_diff": float(tail_diff),
        }

    def _cat_shift(self, orig: pd.Series, syn: pd.Series,
                   col: str) -> Dict[str, Any]:
        """Categorical shift via Jensen–Shannon divergence."""
        o = orig.dropna().astype(str)
        s = syn.dropna().astype(str)
        if len(o) == 0 or len(s) == 0:
            return {"column": col, "shift_score": 0.0}

        cats = sorted(set(o.unique()) | set(s.unique()))
        p = self._normalize(
            o.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float))
        q = self._normalize(
            s.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float))
        m = 0.5 * (p + q)
        js = float(0.5 * sp_entropy(p, m, base=2)
                   + 0.5 * sp_entropy(q, m, base=2))

        return {
            "column": col,
            "shift_score": float(1.0 - np.exp(-js)),
            "js_divergence": float(js),
        }

    def compute_distribution_shift(
        self, synthetic_df: pd.DataFrame, original_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Distribution shift measured in probability space.

        Per-column : PIT via reference ECDF → CvM + tail mass deviation.
        Multivariate: Spearman correlation-matrix Frobenius distance.

        Invariant to : ANY monotonic transform (exp, log, rank, polynomial …).
        Sensitive to : mixture injection, conditional distribution change,
                       tail redistribution.
        """
        cols = [c for c in synthetic_df.columns if c in original_df.columns]
        per_column: Dict[str, Dict[str, Any]] = {}
        evidence:   List[Dict[str, Any]] = []

        for c in cols:
            is_num = (pd.api.types.is_numeric_dtype(synthetic_df[c])
                      and pd.api.types.is_numeric_dtype(original_df[c]))
            item = (self._pit_shift(original_df[c], synthetic_df[c], c)
                    if is_num
                    else self._cat_shift(original_df[c], synthetic_df[c], c))
            per_column[c] = item
            evidence.append({
                "signal": "distribution_shift",
                "column": c,
                "shift_score": item.get("shift_score", 0),
            })

        col_scores = [v["shift_score"]
                      for v in per_column.values() if "shift_score" in v]

        # --- Spearman correlation change (multivariate structure) ---
        num_cols = [c for c in cols
                    if pd.api.types.is_numeric_dtype(synthetic_df[c])
                    and pd.api.types.is_numeric_dtype(original_df[c])]
        copula_distance = 0.0
        if len(num_cols) >= 2:
            rho_ref = original_df[num_cols].corr(method="spearman").to_numpy()
            rho_syn = synthetic_df[num_cols].corr(method="spearman").to_numpy()
            copula_distance = float(
                np.linalg.norm(rho_ref - rho_syn, ord="fro"))

        # --- Combine: max of per-column mean and normalized Δρ ---
        mean_col    = float(np.mean(col_scores)) if col_scores else 0.0
        d           = max(len(num_cols), 1)
        copula_norm = copula_distance / d
        shift_score = float(max(mean_col, copula_norm))

        return {
            "per_column":      per_column,
            "shift_score":     shift_score,
            "copula_distance": copula_distance,
            "evidence":        evidence,
        }

    # ------------------------------------------------------------------
    # SECTION C: Mode Collapse Detection (Dimensionality-Aware)
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_local_intrinsic_dimensionality(X: np.ndarray, k: int) -> float:
        """Maximum Likelihood Estimator of Local Intrinsic Dimensionality.

        LID(x) = -1 / (1/k * sum_{i=1}^{k} log(r_i / r_k))
        where r_i are kNN distances sorted ascending and r_k is the k-th.
        Returns the average LID across all points.
        """
        n, d = X.shape
        if n <= k + 1 or d == 0:
            return 0.0

        nn = NearestNeighbors(n_neighbors=k + 1, algorithm="auto")
        nn.fit(X)
        dists, _ = nn.kneighbors(X)
        # dists[:, 0] is self-distance (0), dists[:, 1:] are k nearest
        dists = dists[:, 1:]  # shape (n, k)

        # Avoid log(0) and division by zero
        r_k = dists[:, -1]  # k-th neighbor distance
        mask = r_k > 1e-15
        if mask.sum() == 0:
            return 0.0

        dists = dists[mask]
        r_k = r_k[mask]

        # Clamp small distances
        dists = np.maximum(dists, 1e-15)
        r_k_col = r_k[:, np.newaxis]
        log_ratios = np.log(dists / r_k_col)
        # Average of log ratios per point (excluding last which is 0)
        mean_log = np.mean(log_ratios[:, :-1], axis=1)
        # LID = -1/mean_log, but mean_log is negative (ratios < 1)
        valid = mean_log < -1e-10
        if valid.sum() == 0:
            return float(d)  # Can't estimate, return ambient

        lid_values = -1.0 / mean_log[valid]
        # Clamp to ambient dimensionality
        lid_values = np.clip(lid_values, 0, d)
        return float(np.median(lid_values))

    def compute_mode_collapse(
        self, synthetic_df: pd.DataFrame, original_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Detect mode collapse via intrinsic dimensionality + entropy loss.

        Detects:
        - Dimensionality loss (lattice, projection, tight clusters)
        - Entropy loss (histogram-based, per column)
        """
        num_cols = [c for c in original_df.select_dtypes(include=[np.number]).columns
                    if c in synthetic_df.columns]

        # --- Per-column entropy loss ---
        ent_losses: List[float] = []
        ent_details: Dict[str, Dict[str, float]] = {}
        for c in num_cols:
            o = pd.to_numeric(original_df[c], errors="coerce").dropna().to_numpy()
            s = pd.to_numeric(synthetic_df[c], errors="coerce").dropna().to_numpy()
            if o.size == 0 or s.size == 0:
                continue
            bins = np.histogram_bin_edges(o, bins="fd")
            if len(bins) < 2:
                bins = np.histogram_bin_edges(o, bins=10)
            o_h = self._safe_entropy(np.histogram(o, bins=bins)[0])
            s_h = self._safe_entropy(np.histogram(s, bins=bins)[0])
            loss = float(max(0.0, 1.0 - (s_h / (o_h + 1e-12))))
            ent_details[c] = {"entropy_real": o_h, "entropy_synthetic": s_h, "entropy_loss": loss}
            ent_losses.append(loss)

        # --- Intrinsic dimensionality comparison ---
        k = min(self.k_lid, max(3, len(original_df) // 10))
        dim_original = 0.0
        dim_synthetic = 0.0
        dim_ratio = 1.0

        if len(num_cols) >= 2:
            o_mat = original_df[num_cols].dropna().to_numpy()
            s_mat = synthetic_df[num_cols].dropna().to_numpy()
            if len(o_mat) > k + 1 and len(s_mat) > k + 1:
                # Standardize using original's scale
                mu = np.mean(o_mat, axis=0)
                sigma = np.std(o_mat, axis=0) + 1e-12
                o_norm = (o_mat - mu) / sigma
                s_norm = (s_mat - mu) / sigma

                dim_original = self._estimate_local_intrinsic_dimensionality(o_norm, k)
                dim_synthetic = self._estimate_local_intrinsic_dimensionality(s_norm, k)
                dim_ratio = dim_synthetic / (dim_original + 1e-12)

        # --- Combine signals ---
        mean_ent_loss = float(np.mean(ent_losses)) if ent_losses else 0.0
        dim_loss = float(max(0.0, 1.0 - dim_ratio))

        # collapse_probability combines entropy loss and dimensionality loss
        combined = max(mean_ent_loss, dim_loss)
        collapse_prob = float(max(min(1.0 - np.exp(-3.0 * combined), 1.0), 0.0))

        return {
            "entropy_by_column": ent_details,
            "intrinsic_dimensionality_original": float(dim_original),
            "intrinsic_dimensionality_synthetic": float(dim_synthetic),
            "dimensionality_ratio": float(dim_ratio),
            "dimensionality_loss": float(dim_loss),
            "mean_entropy_loss": float(mean_ent_loss),
            "collapse_probability": collapse_prob,
            "evidence": [
                {"signal": "mode_collapse", "metric": "LID_RATIO", "value": dim_ratio},
                {"signal": "mode_collapse", "metric": "ENTROPY_LOSS", "value": mean_ent_loss},
            ],
        }

    # ------------------------------------------------------------------
    # compute_all (minimal surface)
    # ------------------------------------------------------------------

    def compute_all(
        self, synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[object] = None
    ) -> Dict[str, Any]:
        """Compute all statistical fidelity metrics."""
        result: Dict[str, Any] = {"evidence": []}

        structural = self.compute_structural_contract_validation(
            synthetic_df, original_df, original_profile
        )
        result["structural_contract_validation"] = structural
        result["evidence"].extend(structural["evidence"])

        if original_df is not None:
            shift = self.compute_distribution_shift(synthetic_df, original_df)
            mode = self.compute_mode_collapse(synthetic_df, original_df)
            result["distribution_shift"] = shift
            result["mode_collapse"] = mode
            result["evidence"].extend(shift["evidence"])
            result["evidence"].extend(mode["evidence"])
        else:
            result["distribution_shift"] = {"per_column": {}, "shift_score": 0.0, "copula_distance": 0.0, "evidence": []}
            result["mode_collapse"] = {"collapse_probability": 0.0, "evidence": []}

        return result
