"""
Tests for confidence calibration (Platt scaling) — Phase 11.3.
"""
import json
from pathlib import Path

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── ECE computation tests ───────────────────────────────────────────────────

class TestComputeECE:
    """Test the Expected Calibration Error function."""

    def _get_compute_ece(self):
        """Import compute_ece from the training script."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from train_risk_classifier import compute_ece
        return compute_ece

    def test_perfect_calibration_has_zero_ece(self):
        """A perfectly calibrated model should have ECE = 0."""
        compute_ece = self._get_compute_ece()

        # 100 samples, 2 classes, perfectly calibrated:
        # model says 90% confident -> 90% correct
        rng = np.random.RandomState(42)
        n = 200
        y_prob = np.zeros((n, 2))
        y_true = np.zeros(n, dtype=int)

        # Create samples where accuracy matches confidence
        for i in range(n):
            conf = 0.95  # high confidence
            y_prob[i, 1] = conf
            y_prob[i, 0] = 1.0 - conf
            # Make 95% of them correct
            y_true[i] = 1 if rng.random() < conf else 0

        ece, buckets = compute_ece(y_true, y_prob, n_bins=10)
        # With enough samples, ECE should be small for well-calibrated predictions
        assert ece < 0.1, f"ECE should be small for well-calibrated model, got {ece}"

    def test_badly_calibrated_has_high_ece(self):
        """An overconfident model should have higher ECE."""
        compute_ece = self._get_compute_ece()

        n = 100
        y_prob = np.zeros((n, 2))
        y_true = np.zeros(n, dtype=int)

        # Model always says 99% confident, but only 50% correct
        for i in range(n):
            y_prob[i, 1] = 0.99
            y_prob[i, 0] = 0.01
            y_true[i] = 1 if i < 50 else 0

        ece, buckets = compute_ece(y_true, y_prob, n_bins=10)
        # ECE should be high (roughly 0.49)
        assert ece > 0.3, f"ECE should be high for overconfident model, got {ece}"

    def test_ece_returns_bucket_data(self):
        """compute_ece should return per-bucket calibration data."""
        compute_ece = self._get_compute_ece()

        n = 50
        y_prob = np.random.RandomState(42).dirichlet([1, 1], size=n)
        y_true = np.random.RandomState(42).randint(0, 2, size=n)

        ece, buckets = compute_ece(y_true, y_prob, n_bins=10)

        assert len(buckets) == 10
        for b in buckets:
            assert "bin" in b
            assert "count" in b
            assert "avg_confidence" in b
            assert "avg_accuracy" in b
            assert "gap" in b

    def test_ece_is_bounded(self):
        """ECE should always be between 0 and 1."""
        compute_ece = self._get_compute_ece()

        n = 100
        y_prob = np.random.RandomState(0).dirichlet([1, 1, 1], size=n)
        y_true = np.random.RandomState(0).randint(0, 3, size=n)

        ece, _ = compute_ece(y_true, y_prob, n_bins=10)
        assert 0.0 <= ece <= 1.0, f"ECE out of bounds: {ece}"


# ── Calibration data file tests ─────────────────────────────────────────────

CALIBRATION_DATA_PATH = PROJECT_ROOT / "data" / "models" / "calibration_data.json"


@pytest.mark.skipif(
    not CALIBRATION_DATA_PATH.exists(),
    reason="Calibration data file not found (run training first)",
)
class TestCalibrationDataFile:
    """Test that the saved calibration data is well-formed."""

    def test_calibration_data_is_valid_json(self):
        with open(CALIBRATION_DATA_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_calibration_data_has_expected_keys(self):
        with open(CALIBRATION_DATA_PATH) as f:
            data = json.load(f)

        # Should have an "overall" key
        assert "overall" in data, "Missing 'overall' key in calibration data"
        assert "ece" in data["overall"]
        assert "buckets" in data["overall"]

    def test_calibration_data_buckets_structure(self):
        with open(CALIBRATION_DATA_PATH) as f:
            data = json.load(f)

        buckets = data["overall"]["buckets"]
        assert len(buckets) == 10, f"Expected 10 buckets, got {len(buckets)}"
        for b in buckets:
            assert "bin" in b
            assert "count" in b


# ── Model calibration tests ─────────────────────────────────────────────────

MODEL_PATH = PROJECT_ROOT / "data" / "models" / "risk_classifier.pkl"


@pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="Risk classifier model not found (run training first)",
)
class TestCalibratedModel:
    """Test that the saved model bundle supports calibrated probabilities."""

    def _load_bundle(self):
        import pickle
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)

    def test_model_has_calibrated_flag(self):
        bundle = self._load_bundle()
        if bundle.get("version", "1.0") < "2.0":
            pytest.skip("Model predates calibration (retrain to update)")
        assert bundle.get("calibrated") is True, (
            "Model bundle should have 'calibrated': True"
        )

    def test_classifiers_have_predict_proba(self):
        bundle = self._load_bundle()
        for cat in bundle["categories"]:
            clf = bundle["classifiers"][cat]
            assert hasattr(clf, "predict_proba"), (
                f"Classifier for {cat} missing predict_proba"
            )

    def test_calibrated_probs_sum_to_one(self):
        """Calibrated probabilities should sum to 1 for each prediction."""
        bundle = self._load_bundle()
        # Create a dummy embedding (384-dim for MiniLM-L6-v2)
        dummy = np.random.RandomState(42).randn(1, 384)

        for cat in bundle["categories"]:
            clf = bundle["classifiers"][cat]
            probs = clf.predict_proba(dummy)[0]
            total = sum(probs)
            assert abs(total - 1.0) < 1e-6, (
                f"Probabilities for {cat} sum to {total}, expected 1.0"
            )
