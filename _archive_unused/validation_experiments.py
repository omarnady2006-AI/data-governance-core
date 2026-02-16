import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from governance_core.metrics.statistical_fidelity import StatisticalFidelityMetrics
from governance_core.metrics.privacy_risk import PrivacyRiskMetrics


def _print_table(df: pd.DataFrame) -> None:
    print(df.to_string(index=False))
    print()


def _distribution_shift_experiment() -> None:
    rng = np.random.default_rng(42)
    n = 5000

    a = rng.normal(0.0, 1.0, n)
    b = a[rng.permutation(n)]
    c = rng.normal(1.0, 1.0, n)

    real = pd.DataFrame({"x": a})
    shuf = pd.DataFrame({"x": b})
    shifted = pd.DataFrame({"x": c})

    sf = StatisticalFidelityMetrics()
    ab = sf.compute_distribution_shift(shuf, real)
    ac = sf.compute_distribution_shift(shifted, real)

    rows = [
        {
            "pair": "A_vs_B",
            "shift_score": ab["shift_score"],
            "confidence": ab["confidence"],
            "sample_size_warning": int(ab["sample_size_warning"]),
            "ks_statistic_x": ab["ks_statistics"]["x"]["statistic"],
            "ks_p_value_x": ab["ks_statistics"]["x"]["p_value"],
            "wasserstein_x": ab["continuous"]["x"]["wasserstein_distance"],
        },
        {
            "pair": "A_vs_C",
            "shift_score": ac["shift_score"],
            "confidence": ac["confidence"],
            "sample_size_warning": int(ac["sample_size_warning"]),
            "ks_statistic_x": ac["ks_statistics"]["x"]["statistic"],
            "ks_p_value_x": ac["ks_statistics"]["x"]["p_value"],
            "wasserstein_x": ac["continuous"]["x"]["wasserstein_distance"],
        },
    ]
    _print_table(pd.DataFrame(rows))


def _mode_collapse_experiment() -> None:
    rng = np.random.default_rng(7)
    n = 4000

    real = pd.DataFrame(
        {
            "u1": rng.uniform(0.0, 1.0, n),
            "u2": rng.uniform(0.0, 1.0, n),
            "cat": rng.choice(["a", "b", "c", "d"], size=n),
        }
    )

    syn_uniform = pd.DataFrame(
        {
            "u1": rng.uniform(0.0, 1.0, n),
            "u2": rng.uniform(0.0, 1.0, n),
            "cat": rng.choice(["a", "b", "c", "d"], size=n),
        }
    )

    syn_concentrated = pd.DataFrame(
        {
            "u1": np.clip(rng.normal(0.5, 0.02, n), 0.0, 1.0),
            "u2": np.clip(rng.normal(0.5, 0.02, n), 0.0, 1.0),
            "cat": rng.choice(["a"], size=n),
        }
    )

    sf = StatisticalFidelityMetrics()
    base = sf.compute_mode_collapse(syn_uniform, real)
    collapsed = sf.compute_mode_collapse(syn_concentrated, real)

    rows = [
        {
            "scenario": "uniform_vs_uniform",
            "collapse_probability": base["collapse_probability"],
            "support_volume_ratio": base["support_volume_ratio"],
            "mean_entropy_loss": np.mean([v["entropy_loss"] for v in base["entropy_by_column"].values()]),
            "mean_category_coverage": np.mean([v["coverage_ratio"] for v in base["category_coverage_by_column"].values()]),
        },
        {
            "scenario": "uniform_vs_concentrated",
            "collapse_probability": collapsed["collapse_probability"],
            "support_volume_ratio": collapsed["support_volume_ratio"],
            "mean_entropy_loss": np.mean([v["entropy_loss"] for v in collapsed["entropy_by_column"].values()]),
            "mean_category_coverage": np.mean([v["coverage_ratio"] for v in collapsed["category_coverage_by_column"].values()]),
        },
    ]
    _print_table(pd.DataFrame(rows))


def _memorization_risk_experiment() -> None:
    rng = np.random.default_rng(123)
    n = 2500

    real = pd.DataFrame(
        {
            "x1": rng.normal(0.0, 1e-4, n),
            "x2": rng.normal(1.0, 1e-4, n),
            "x3": rng.normal(-1.0, 1e-4, n),
            "cat": rng.choice(["a", "b", "c"], size=n, p=[0.5, 0.3, 0.2]),
        }
    )

    eps = 0.001
    copy_noise = real.copy()
    copy_noise["x1"] = copy_noise["x1"] + eps
    copy_noise["x2"] = copy_noise["x2"] + eps
    copy_noise["x3"] = copy_noise["x3"] + eps

    kde = gaussian_kde(real[["x1", "x2", "x3"]].to_numpy().T)
    kde_sample = kde.resample(n).T
    kde_syn = pd.DataFrame(kde_sample, columns=["x1", "x2", "x3"])
    kde_syn["cat"] = rng.choice(["a", "b", "c"], size=n, p=real["cat"].value_counts(normalize=True).sort_index().reindex(["a", "b", "c"]).to_numpy())

    pr = PrivacyRiskMetrics()
    noisy = pr.compute_all(copy_noise, real)
    gan_like = pr.compute_all(kde_syn, real)

    rows = [
        {
            "scenario": "copy_plus_noise_eps_0p001",
            "leakage_risk_score": noisy["leakage_risk_score"],
            "membership_inference_auc": noisy["membership_inference_auc"],
            "membership_inference_ece": noisy["membership_inference_ece"],
            "exact_duplicates_rate": noisy["exact_duplicates_rate"],
            "near_duplicates_rate": noisy["near_duplicates_rate"],
        },
        {
            "scenario": "kde_sampled",
            "leakage_risk_score": gan_like["leakage_risk_score"],
            "membership_inference_auc": gan_like["membership_inference_auc"],
            "membership_inference_ece": gan_like["membership_inference_ece"],
            "exact_duplicates_rate": gan_like["exact_duplicates_rate"],
            "near_duplicates_rate": gan_like["near_duplicates_rate"],
        },
    ]
    _print_table(pd.DataFrame(rows))


def _duplicate_detection_experiment() -> None:
    rng = np.random.default_rng(202)
    n = 2000

    real = pd.DataFrame(
        {
            "f1": rng.normal(0, 1, n),
            "f2": rng.normal(1, 2, n),
            "f3": rng.normal(-1, 1, n),
            "cat": rng.choice(["x", "y", "z"], size=n),
        }
    )

    kde = gaussian_kde(real[["f1", "f2", "f3"]].to_numpy().T)
    syn_num = kde.resample(n).T
    synthetic = pd.DataFrame(syn_num, columns=["f1", "f2", "f3"])
    synthetic["cat"] = rng.choice(real["cat"].unique(), size=n)

    injected = synthetic.copy()
    copy_n = int(0.1 * n)
    injected_rows = real.sample(n=copy_n, random_state=202).reset_index(drop=True)
    injected.loc[: copy_n - 1, ["f1", "f2", "f3", "cat"]] = injected_rows[["f1", "f2", "f3", "cat"]].to_numpy()

    pr = PrivacyRiskMetrics()
    base = pr.compute_all(synthetic, real)
    inj = pr.compute_all(injected, real)

    rows = [
        {
            "scenario": "baseline_0pct_injected",
            "exact_duplicates_rate": base["exact_duplicates_rate"],
            "exact_duplicates_count": base["exact_duplicates_count"],
            "near_duplicates_rate": base["near_duplicates_rate"],
            "privacy_score": base["privacy_score"],
        },
        {
            "scenario": "injected_10pct_copies",
            "exact_duplicates_rate": inj["exact_duplicates_rate"],
            "exact_duplicates_count": inj["exact_duplicates_count"],
            "near_duplicates_rate": inj["near_duplicates_rate"],
            "privacy_score": inj["privacy_score"],
        },
    ]
    _print_table(pd.DataFrame(rows))


if __name__ == "__main__":
    np.set_printoptions(suppress=True)
    pd.set_option("display.float_format", lambda x: f"{x:.6f}")

    _distribution_shift_experiment()
    _mode_collapse_experiment()
    _memorization_risk_experiment()
    _duplicate_detection_experiment()
