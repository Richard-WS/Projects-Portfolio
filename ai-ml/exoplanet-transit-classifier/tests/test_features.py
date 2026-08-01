"""Feature engineering tests on synthetic light curves."""
from __future__ import annotations

import numpy as np
import pytest

from exoplanet_classifier.features import (
    FeatureError,
    detrend,
    extract_features,
    normalize_curve,
)
from tests.conftest import make_curve


def test_normalize_constant_curve():
    z = normalize_curve(np.ones(64))
    assert np.allclose(z, 0.0)


def test_normalize_centers_and_scales():
    flux = 100.0 + np.random.default_rng(0).normal(0, 1, 1000)
    z = normalize_curve(flux)
    assert abs(float(np.median(z))) < 0.05
    assert abs(float(np.median(np.abs(z))) - 1.0) < 0.1


def test_normalize_rejects_short_curve():
    with pytest.raises(FeatureError):
        normalize_curve(np.ones(4))


def test_normalize_rejects_non_finite():
    flux = np.ones(64)
    flux[3] = np.nan
    with pytest.raises(FeatureError):
        normalize_curve(flux)


def test_extract_features_shape_and_keys():
    feats = extract_features(make_curve(seed=1), autocorr_max_lag=50)
    assert "skew" in feats and "kurtosis" in feats
    assert "dip_count" in feats and "max_consecutive_dips" in feats
    assert "autocorr_001" in feats and "autocorr_050" in feats
    assert "peak_autocorr" in feats and "best_lag" in feats
    assert "fft_dominant_freq" in feats
    assert all(isinstance(v, float) for v in feats.values())
    assert len([k for k in feats if k.startswith("autocorr_")]) == 50


def test_extract_features_default_grid_size():
    feats = extract_features(make_curve(seed=2))
    assert len([k for k in feats if k.startswith("autocorr_")]) == 400


def test_extract_features_deterministic():
    a = extract_features(make_curve(transit=True, seed=5))
    b = extract_features(make_curve(transit=True, seed=5))
    assert a == b


def test_transit_curve_has_dips_noise_curve_does_not():
    transit = extract_features(make_curve(transit=True, depth=0.05, dips=4, seed=3))
    plain = extract_features(make_curve(transit=False, seed=3))
    assert transit["dip_count"] > plain["dip_count"]
    assert transit["deepest_dip"] < plain["deepest_dip"]
    assert transit["max_consecutive_dips"] >= 1


def test_periodic_curve_autocorrelation_higher():
    noisy = make_curve(transit=False, seed=9)
    periodic = make_curve(transit=True, dips=5, depth=0.03, seed=9)
    feats_noisy = extract_features(noisy)
    feats_periodic = extract_features(periodic)
    assert feats_periodic["peak_autocorr"] > feats_noisy["peak_autocorr"]
    assert feats_periodic["best_lag"] > 0


def test_detrend_removes_slow_drift():
    n = 1024
    t = np.linspace(0, 1, n)
    drift = 5.0 * t  # strong linear baseline
    rng = np.random.default_rng(1)
    flux = 1.0 + drift + rng.normal(0, 0.01, n)
    z = detrend(normalize_curve(flux), window=64)
    # residual median near 0 and slope mostly gone
    assert abs(float(np.median(z))) < 0.5
    assert abs(float(z[: n // 2].mean() - z[n // 2 :].mean())) < 0.5


def test_extract_features_bad_params():
    with pytest.raises(FeatureError):
        extract_features(make_curve(), detrend_window=1)
    with pytest.raises(FeatureError):
        extract_features(make_curve(), autocorr_max_lag=3)
    with pytest.raises(FeatureError):
        extract_features(make_curve(), dip_threshold_mad=0.0)
