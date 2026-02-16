import numpy as np
import pandas as pd
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from governance_core.metrics.privacy_risk import PrivacyRiskMetrics
from governance_core.metrics.statistical_fidelity import StatisticalFidelityMetrics


def _make_data(seed: int = 0):
    rng = np.random.default_rng(seed)
    original = pd.DataFrame(
        {
            "x": rng.normal(0.0, 1.0, 200),
            "y": rng.normal(5.0, 2.0, 200),
            "cat": rng.choice(["a", "b", "c"], 200, p=[0.6, 0.3, 0.1]),
            "label": rng.integers(0, 2, 200),
        }
    )
    synthetic = pd.DataFrame(
        {
            "x": rng.normal(0.8, 1.3, 180),
            "y": rng.normal(4.5, 1.0, 180),
            "cat": rng.choice(["a", "b"], 180, p=[0.9, 0.1]),
            "label": rng.integers(0, 2, 180),
        }
    )
    return original, synthetic


def test_distribution_shift_outputs_evidence_fields():
    original, synthetic = _make_data()
    metrics = StatisticalFidelityMetrics().compute_all(synthetic, original)
    shift = metrics["distribution_shift"]

    assert "shift_score" in shift
    assert "confidence" in shift
    assert "sample_size_warning" in shift
    assert isinstance(shift["evidence"], list)
    assert 0.0 <= shift["shift_score"] <= 1.0
    assert 0.0 <= shift["confidence"] <= 1.0


def test_mode_collapse_probability_in_unit_interval():
    original, synthetic = _make_data()
    mode = StatisticalFidelityMetrics().compute_all(synthetic, original)["mode_collapse"]
    assert 0.0 <= mode["collapse_probability"] <= 1.0


def test_privacy_risk_reports_three_levels_and_leakage_score():
    original, synthetic = _make_data()
    out = PrivacyRiskMetrics().compute_all(synthetic, original)

    assert "exact_duplicates_rate" in out
    assert "near_duplicates_rate" in out
    assert "leakage_risk_score" in out
    assert 0.0 <= out["privacy_score"] <= 1.0
    if out["leakage_risk_score"] is not None:
        assert 0.0 <= out["leakage_risk_score"] <= 1.0
