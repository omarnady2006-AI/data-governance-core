"""Privacy risk metrics: identity-manifold duplicate detection + DOMIAS membership inference.

Mathematical definitions:
- Duplicate detection: kNN-graph connected components with radius epsilon
  adaptive to data scale. duplicates = records in micro-clusters with >= 2
  members from both original and synthetic. Not hash-based — noise-resistant.
- DOMIAS: raw log-likelihood ratio scores. No sigmoid conversion.
  Calibration via quantile binning instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from scipy.special import logsumexp
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


# ======================================================================
# KDE density estimator (kept for DOMIAS)
# ======================================================================

@dataclass
class _KDECategoricalDensity:
    """Mixed density: Gaussian KDE (numeric) + smoothed empirical (categorical)."""

    numeric_cols: List[str]
    categorical_cols: List[str]
    alpha: float
    kde: Optional[gaussian_kde]
    cat_probs: Dict[str, Dict[str, float]]
    cat_default: Dict[str, float]
    num_fill: Dict[str, float]

    def log_likelihood(self, df: pd.DataFrame) -> np.ndarray:
        df = df.copy()
        ll = np.zeros(len(df), dtype=float)
        if self.numeric_cols:
            for c in self.numeric_cols:
                if c not in df.columns:
                    df[c] = self.num_fill[c]
            num = df[self.numeric_cols].apply(pd.to_numeric, errors="coerce")
            num = num.fillna(pd.Series(self.num_fill))
            x = num.to_numpy().T
            if self.kde is not None:
                ll += np.log(np.maximum(self.kde(x), 1e-300))
        for c in self.categorical_cols:
            vals = df[c].astype(str).fillna("__nan__") if c in df.columns else pd.Series(["__nan__"] * len(df))
            probs = self.cat_probs.get(c, {})
            default_p = self.cat_default.get(c, 1e-12)
            p = vals.map(probs).fillna(default_p).to_numpy(dtype=float)
            ll += np.log(np.maximum(p, 1e-300))
        return ll


def _fit_kde_categorical_density(df: pd.DataFrame, alpha: float = 1.0) -> _KDECategoricalDensity:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [c for c in df.columns if c not in numeric_cols]
    num_fill: Dict[str, float] = {}
    kde = None
    if numeric_cols:
        num = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        med = num.median(numeric_only=True)
        num_fill = {c: float(med.get(c, 0.0)) for c in numeric_cols}
        num = num.fillna(pd.Series(num_fill))
        if len(num) >= 3:
            kde = gaussian_kde(num.to_numpy().T)
    cat_probs: Dict[str, Dict[str, float]] = {}
    cat_default: Dict[str, float] = {}
    for c in categorical_cols:
        s = df[c].astype(str).fillna("__nan__")
        counts = s.value_counts(dropna=False)
        m = max(int(len(counts)), 1)
        denom = float(len(s) + alpha * m)
        probs = {str(k): float((v + alpha) / denom) for k, v in counts.items()}
        cat_probs[c] = probs
        cat_default[c] = float(alpha / denom)
    return _KDECategoricalDensity(
        numeric_cols=numeric_cols, categorical_cols=categorical_cols,
        alpha=float(alpha), kde=kde, cat_probs=cat_probs,
        cat_default=cat_default, num_fill=num_fill,
    )


# ======================================================================
# Low-level KDE helpers (for DOMIAS LOO)
# ======================================================================

def _numeric_matrix(df: pd.DataFrame, numeric_cols: List[str], fill: Dict[str, float]) -> np.ndarray:
    if not numeric_cols:
        return np.zeros((len(df), 0), dtype=float)
    return df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(pd.Series(fill)).to_numpy(dtype=float)


def _kde_kernel_params(x_train: np.ndarray) -> Tuple[np.ndarray, float]:
    if x_train.shape[0] < 3 or x_train.shape[1] == 0:
        cov = np.eye(max(1, x_train.shape[1]), dtype=float)
        return cov, 0.0
    kde = gaussian_kde(x_train.T)
    cov = np.asarray(kde.covariance, dtype=float)
    d = cov.shape[0]
    cov = cov + 1e-9 * np.eye(d)
    sign, logdet = np.linalg.slogdet(cov)
    if sign <= 0:
        cov = cov + 1e-6 * np.eye(d)
        sign, logdet = np.linalg.slogdet(cov)
    log_const = float(-0.5 * (d * np.log(2.0 * np.pi) + logdet))
    return cov, log_const


def _pairwise_mahalanobis_sq(x_eval: np.ndarray, x_train: np.ndarray, inv_cov: np.ndarray) -> np.ndarray:
    a = x_eval @ inv_cov
    q_eval = np.sum(a * x_eval, axis=1, keepdims=True)
    b = x_train @ inv_cov
    q_train = np.sum(b * x_train, axis=1, keepdims=True).T
    cross = a @ x_train.T
    return np.maximum(q_eval + q_train - 2.0 * cross, 0.0)


def _kde_log_density(x_eval: np.ndarray, x_train: np.ndarray, cov: np.ndarray, log_const: float) -> np.ndarray:
    if x_train.shape[1] == 0:
        return np.zeros(len(x_eval), dtype=float)
    inv_cov = np.linalg.pinv(cov)
    dist2 = _pairwise_mahalanobis_sq(x_eval, x_train, inv_cov)
    log_k = log_const - 0.5 * dist2
    return logsumexp(log_k, axis=1) - np.log(max(len(x_train), 1))


def _kde_log_density_loo(x_train: np.ndarray, cov: np.ndarray, log_const: float) -> np.ndarray:
    n, d = x_train.shape
    if d == 0:
        return np.zeros(n, dtype=float)
    if n <= 1:
        return np.full(n, -np.inf, dtype=float)
    inv_cov = np.linalg.pinv(cov)
    dist2 = _pairwise_mahalanobis_sq(x_train, x_train, inv_cov)
    log_k = log_const - 0.5 * dist2
    log_sum_all = logsumexp(log_k, axis=1)
    delta = log_const - log_sum_all
    log_sum_others = log_sum_all + np.log1p(-np.exp(np.minimum(delta, -1e-16)))
    return log_sum_others - np.log(float(n - 1))


# ======================================================================
# Main class
# ======================================================================

class PrivacyRiskMetrics:
    """Duplicate detection via identity manifold + DOMIAS membership inference."""

    def __init__(self, domias_alpha: float = 1.0, random_state: int = 42):
        self.domias_alpha = domias_alpha
        self.random_state = random_state

    # ------------------------------------------------------------------
    # D) Duplicate Detection — kNN identity manifold
    # ------------------------------------------------------------------

    def detect_duplicates(
        self, synthetic_df: pd.DataFrame, original_df: pd.DataFrame,
        epsilon_quantile: float = 0.01, min_neighbors: int = 1,
    ) -> Dict[str, Any]:
        """Detect duplicates as records on the same identity manifold.

        Uses kNN with adaptive radius epsilon based on data scale.
        A synthetic record is a duplicate if its nearest neighbor in
        the original set is within epsilon (adaptive to inter-record distances).

        epsilon = quantile(nearest-neighbor distances in original, epsilon_quantile)
        """
        common_cols = [c for c in synthetic_df.columns if c in original_df.columns]
        if not common_cols:
            return {"duplicates_count": 0, "duplicates_rate": 0.0, "epsilon": 0.0}

        # Numeric encoding
        num_cols = [c for c in common_cols
                    if pd.api.types.is_numeric_dtype(original_df[c])
                    and pd.api.types.is_numeric_dtype(synthetic_df[c])]
        cat_cols = [c for c in common_cols if c not in num_cols]

        # Build feature matrices
        orig_parts = []
        syn_parts = []

        if num_cols:
            scaler = StandardScaler()
            o_num = original_df[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy()
            scaler.fit(o_num)
            orig_parts.append(scaler.transform(o_num))
            s_num = synthetic_df[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy()
            syn_parts.append(scaler.transform(s_num))

        if cat_cols:
            # Encode categoricals as frequency-based numeric
            for c in cat_cols:
                freq = original_df[c].astype(str).value_counts(normalize=True)
                o_enc = original_df[c].astype(str).map(freq).fillna(0).to_numpy().reshape(-1, 1)
                s_enc = synthetic_df[c].astype(str).map(freq).fillna(0).to_numpy().reshape(-1, 1)
                orig_parts.append(o_enc)
                syn_parts.append(s_enc)

        if not orig_parts:
            return {"duplicates_count": 0, "duplicates_rate": 0.0, "epsilon": 0.0}

        X_orig = np.hstack(orig_parts)
        X_syn = np.hstack(syn_parts)

        # Compute adaptive epsilon from intra-original NN distances
        k_eps = min(2, len(X_orig))
        nn_orig = NearestNeighbors(n_neighbors=k_eps, algorithm="auto")
        nn_orig.fit(X_orig)
        intra_dists, _ = nn_orig.kneighbors(X_orig)
        # Use k-th neighbor (last column), exclude self
        nn_dists = intra_dists[:, -1] if intra_dists.shape[1] > 1 else intra_dists[:, 0]
        epsilon = float(np.quantile(nn_dists[nn_dists > 1e-15], epsilon_quantile)) if np.any(nn_dists > 1e-15) else 1e-10

        # Find synthetic records within epsilon of any original record
        nn_cross = NearestNeighbors(n_neighbors=1, algorithm="auto")
        nn_cross.fit(X_orig)
        cross_dists, _ = nn_cross.kneighbors(X_syn)
        cross_dists = cross_dists[:, 0]

        is_duplicate = cross_dists <= epsilon
        dup_count = int(is_duplicate.sum())
        dup_rate = float(dup_count / len(X_syn)) if len(X_syn) > 0 else 0.0

        return {
            "duplicates_count": dup_count,
            "duplicates_rate": dup_rate,
            "epsilon": float(epsilon),
            "synthetic_total": int(len(X_syn)),
            "original_total": int(len(X_orig)),
            "nearest_distances_mean": float(np.mean(cross_dists)),
            "nearest_distances_std": float(np.std(cross_dists)),
        }

    # ------------------------------------------------------------------
    # E) DOMIAS Membership Inference
    # ------------------------------------------------------------------

    def _fit_population_components(self, population_ref_df: pd.DataFrame) -> Dict[str, Any]:
        r = population_ref_df.reset_index(drop=True)
        numeric_cols = r.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = [c for c in r.columns if c not in numeric_cols]

        num = r[numeric_cols].apply(pd.to_numeric, errors="coerce") if numeric_cols else pd.DataFrame(index=r.index)
        med = num.median(numeric_only=True) if numeric_cols else pd.Series(dtype=float)
        fill = {c: float(med.get(c, 0.0)) for c in numeric_cols}
        x = _numeric_matrix(r, numeric_cols, fill)

        cov_base, log_const_base = _kde_kernel_params(x)
        if x.shape[1] > 0:
            feat_std = np.std(x, axis=0) + 1e-12
            noise_std = 0.05 * feat_std
            cov_noise = np.diag(noise_std ** 2)
            cov_sm = cov_base + cov_noise
            d = cov_sm.shape[0]
            cov_sm = cov_sm + 1e-9 * np.eye(d)
            sign, logdet = np.linalg.slogdet(cov_sm)
            if sign <= 0:
                cov_sm = cov_sm + 1e-6 * np.eye(d)
                sign, logdet = np.linalg.slogdet(cov_sm)
            log_const_sm = float(-0.5 * (d * np.log(2.0 * np.pi) + logdet))
        else:
            noise_std = np.zeros((0,), dtype=float)
            cov_sm = cov_base
            log_const_sm = 0.0

        cat_counts = {}
        cat_m = {}
        for c in cat_cols:
            s = r[c].astype(str).fillna("__nan__")
            vc = s.value_counts(dropna=False)
            cat_counts[c] = vc
            cat_m[c] = max(int(len(vc)), 1)

        return {
            "numeric_cols": numeric_cols, "cat_cols": cat_cols,
            "fill": fill, "x_train": x, "cov_sm": cov_sm,
            "log_const_sm": log_const_sm, "cat_counts": cat_counts, "cat_m": cat_m,
        }

    def _population_loglik_loo(self, population_ref_df: pd.DataFrame, comps: Dict[str, Any]) -> np.ndarray:
        r = population_ref_df.reset_index(drop=True)
        x = comps["x_train"]
        ll = np.zeros(len(r), dtype=float)
        if x.shape[1] > 0:
            ll += _kde_log_density_loo(x, comps["cov_sm"], comps["log_const_sm"])
        n = len(r)
        for c in comps["cat_cols"]:
            s = r[c].astype(str).fillna("__nan__")
            vc = comps["cat_counts"][c]
            m = comps["cat_m"][c]
            denom = float((n - 1) + 1.0 * m)
            counts = s.map(vc).fillna(0.0).to_numpy(dtype=float)
            p = np.maximum(counts / denom, 1e-300)
            ll += np.log(p)
        return ll

    def _population_loglik_full(self, eval_df: pd.DataFrame, comps: Dict[str, Any]) -> np.ndarray:
        ll = np.zeros(len(eval_df), dtype=float)
        x_train = comps["x_train"]
        if x_train.shape[1] > 0:
            x_eval = _numeric_matrix(eval_df, comps["numeric_cols"], comps["fill"])
            ll += _kde_log_density(x_eval, x_train, comps["cov_sm"], comps["log_const_sm"])
        n = int(len(x_train))
        for c in comps["cat_cols"]:
            s = eval_df[c].astype(str).fillna("__nan__") if c in eval_df.columns else pd.Series(["__nan__"] * len(eval_df))
            vc = comps["cat_counts"][c]
            m = comps["cat_m"][c]
            denom = float(n + 1.0 * m)
            counts = s.map(vc).fillna(0.0).to_numpy(dtype=float)
            p = np.maximum((counts + 1.0) / denom, 1e-300)
            ll += np.log(p)
        return ll

    def _synthetic_loglik(self, eval_df: pd.DataFrame, synthetic_df: pd.DataFrame) -> np.ndarray:
        s_model = _fit_kde_categorical_density(synthetic_df, alpha=self.domias_alpha)
        return s_model.log_likelihood(eval_df)

    def domias_lr_scores(
        self, population_ref_df: pd.DataFrame, synthetic_df: pd.DataFrame,
        eval_df: pd.DataFrame, loo_population: bool
    ) -> np.ndarray:
        """Raw log-likelihood ratios. No sigmoid conversion."""
        comps = self._fit_population_components(population_ref_df)
        ll_s = self._synthetic_loglik(eval_df, synthetic_df)
        if loo_population:
            ll_pop = self._population_loglik_loo(population_ref_df, comps)
        else:
            ll_pop = self._population_loglik_full(eval_df, comps)
        return ll_s - ll_pop

    def run_domias_attack(
        self, population_ref_df: pd.DataFrame, synthetic_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Run DOMIAS attack. Reports raw LR statistics with quantile-binned calibration."""
        lr = self.domias_lr_scores(population_ref_df, synthetic_df, population_ref_df, loo_population=True)
        mean_lr = float(np.mean(lr)) if len(lr) else 0.0
        std_lr = float(np.std(lr)) if len(lr) else 0.0
        top_k = max(1, int(np.ceil(0.01 * len(lr))))
        top1 = float(np.mean(np.partition(lr, -top_k)[-top_k:])) if len(lr) else 0.0

        # Quantile-binned calibration
        n_bins = 10
        quantile_calibration: List[Dict[str, float]] = []
        if len(lr) > n_bins:
            bin_edges = np.quantile(lr, np.linspace(0, 1, n_bins + 1))
            for i in range(n_bins):
                mask = (lr >= bin_edges[i]) & (lr < bin_edges[i + 1])
                if i == n_bins - 1:
                    mask = (lr >= bin_edges[i]) & (lr <= bin_edges[i + 1])
                if mask.sum() > 0:
                    quantile_calibration.append({
                        "bin": i,
                        "lr_low": float(bin_edges[i]),
                        "lr_high": float(bin_edges[i + 1]),
                        "count": int(mask.sum()),
                        "mean_lr": float(np.mean(lr[mask])),
                    })

        return {
            "lr_scores": lr,
            "lr_distribution_mean": mean_lr,
            "lr_distribution_std": std_lr,
            "top1_percent_lr": top1,
            "quantile_calibration": quantile_calibration,
        }

    @staticmethod
    def _auc_from_scores(pos_scores: np.ndarray, neg_scores: np.ndarray) -> float:
        """AUC via Mann-Whitney U."""
        pos = np.asarray(pos_scores, dtype=float)
        neg = np.asarray(neg_scores, dtype=float)
        if len(pos) == 0 or len(neg) == 0:
            return float("nan")
        combined = np.concatenate([pos, neg])
        ranks = pd.Series(combined).rank(method="average").to_numpy()
        r_pos = ranks[:len(pos)]
        u = np.sum(r_pos) - len(pos) * (len(pos) + 1) / 2.0
        return float(u / (len(pos) * len(neg)))

    # ------------------------------------------------------------------
    # compute_all (minimal surface)
    # ------------------------------------------------------------------

    def compute_all(
        self, synthetic_df: pd.DataFrame,
        original_df: Optional[pd.DataFrame] = None,
        original_profile: Optional[object] = None
    ) -> Dict[str, Any]:
        """Compute all privacy risk metrics."""
        result: Dict[str, Any] = {"evidence": []}

        if original_df is not None:
            dup = self.detect_duplicates(synthetic_df, original_df)
            result.update(dup)
            domias = self.run_domias_attack(original_df.reset_index(drop=True), synthetic_df.reset_index(drop=True))
            result.update({
                "lr_distribution_mean": domias["lr_distribution_mean"],
                "lr_distribution_std": domias["lr_distribution_std"],
                "top1_percent_lr": domias["top1_percent_lr"],
                "quantile_calibration": domias["quantile_calibration"],
            })
        else:
            result.update({
                "duplicates_count": 0, "duplicates_rate": 0.0,
                "lr_distribution_mean": None, "lr_distribution_std": None,
                "top1_percent_lr": None, "quantile_calibration": [],
            })

        return result
