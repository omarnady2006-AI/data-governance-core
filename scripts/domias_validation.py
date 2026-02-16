import sys
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import gaussian_kde

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from governance_core.metrics.privacy_risk import PrivacyRiskMetrics


def _make_real(seed: int = 0, n: int = 2000) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "x1": rng.normal(0.0, 1.0, n),
            "x2": rng.normal(3.0, 2.0, n),
            "x3": rng.normal(-1.0, 1.5, n),
        }
    )


def _kde_sample(real: pd.DataFrame, seed: int = 1, bw: float | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    numeric = real.select_dtypes(include=[np.number]).columns.tolist()
    kde = gaussian_kde(real[numeric].to_numpy().T, bw_method=bw)
    samp = kde.resample(len(real)).T
    out = pd.DataFrame(samp, columns=numeric)
    return out[real.columns]


def _auc_from_scores(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    combined = np.concatenate([pos, neg])
    ranks = pd.Series(combined).rank(method="average").to_numpy()
    r_pos = ranks[: len(pos)]
    u = np.sum(r_pos) - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(pos) * len(neg)))


def _run_case(case: str, R: pd.DataFrame, S: pd.DataFrame, members: np.ndarray, nonmembers: np.ndarray) -> dict:
    pr = PrivacyRiskMetrics(domias_alpha=1.0, random_state=0)
    lr_all = pr.domias_lr_scores(R, S, R, loo_population=True)
    mean_lr = float(np.mean(lr_all))
    top_k = max(1, int(np.ceil(0.01 * len(lr_all))))
    top1 = float(np.mean(np.partition(lr_all, -top_k)[-top_k:]))
    auc = _auc_from_scores(lr_all[members], lr_all[nonmembers])
    return {"case": case, "mean_lr": mean_lr, "top1_lr": top1, "auc_separating_members": auc}


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.6f}")
    rng = np.random.default_rng(123)

    R = _make_real(seed=0, n=2000).reset_index(drop=True)

    # Case A: S = shuffled copy of R
    S_a = R.sample(frac=1.0, random_state=1).reset_index(drop=True)
    # For AUC, create an OUT set from an independent population draw.
    R_out = _make_real(seed=999, n=2000).reset_index(drop=True)

    # Case B: S = KDE sampled from R
    S_b = _kde_sample(R, seed=2, bw=None)

    # Case C: S built from subset training members (memorization)
    train_idx = rng.choice(np.arange(len(R)), size=int(0.3 * len(R)), replace=False)
    member_mask = np.zeros(len(R), dtype=bool)
    member_mask[train_idx] = True
    nonmember_mask = ~member_mask
    S_c = R.iloc[train_idx].reset_index(drop=True)

    rows = []
    # A: AUC uses members=R vs nonmembers=R_out, both scored against the same (R as population reference, S_a as synthetic).
    pr = PrivacyRiskMetrics(domias_alpha=1.0, random_state=0)
    lr_a_in = pr.domias_lr_scores(R, S_a, R, loo_population=True)
    lr_a_out = pr.domias_lr_scores(R, S_a, R_out, loo_population=False)
    rows.append(
        {
            "case": "A_shuffled_copy",
            "mean_lr": float(np.mean(lr_a_in)),
            "top1_lr": float(np.mean(np.partition(lr_a_in, -max(1, int(np.ceil(0.01 * len(lr_a_in)))))[-max(1, int(np.ceil(0.01 * len(lr_a_in)))):])),
            "auc_separating_members": _auc_from_scores(lr_a_in, lr_a_out),
        }
    )

    # B: members vs nonmembers with R_out.
    pr = PrivacyRiskMetrics(domias_alpha=1.0, random_state=0)
    lr_b_in = pr.domias_lr_scores(R, S_b, R, loo_population=True)
    lr_b_out = pr.domias_lr_scores(R, S_b, R_out, loo_population=False)
    rows.append(
        {
            "case": "B_kde_sampled",
            "mean_lr": float(np.mean(lr_b_in)),
            "top1_lr": float(np.mean(np.partition(lr_b_in, -max(1, int(np.ceil(0.01 * len(lr_b_in)))))[-max(1, int(np.ceil(0.01 * len(lr_b_in)))):])),
            "auc_separating_members": _auc_from_scores(lr_b_in, lr_b_out),
        }
    )

    # C: AUC members vs nonmembers within R using the same S_c.
    pr = PrivacyRiskMetrics(domias_alpha=1.0, random_state=0)
    lr_c = pr.domias_lr_scores(R, S_c, R, loo_population=True)
    rows.append(
        {
            "case": "C_subset_training",
            "mean_lr": float(np.mean(lr_c)),
            "top1_lr": float(np.mean(np.partition(lr_c, -max(1, int(np.ceil(0.01 * len(lr_c)))))[-max(1, int(np.ceil(0.01 * len(lr_c)))):])),
            "auc_separating_members": _auc_from_scores(lr_c[member_mask], lr_c[nonmember_mask]),
        }
    )

    print(pd.DataFrame(rows).to_string(index=False))
