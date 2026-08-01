"""Feature engineering for Kepler light curves.

A transit is a *short, periodic* dimming of the star — typically a handful
of points deep, repeating every tens to hundreds of samples. Raw Kepler
photometry is dominated by long-period instrumental drift and flares, so
the pipeline here is:

1. ``normalize_curve``   - median/MAD standardization (robust to outliers)
2. ``detrend``           - remove slow drift with a rolling median, so
                           short dips are not buried in the baseline
3. feature families      - statistics, dip morphology, periodicity

The decisive family is the **autocorrelation grid**: the normalized and
detrended curve correlated with itself at every lag from 1 to a few
hundred samples. Periodic transits show a strong, repeating correlation
bump at the transit period; non-transit variability does not. The grid
is consumed as-is by the tree model (400 features), which can find the
relevant lags directly.

All features are numpy-only, deterministic, and interpretable.
"""
from __future__ import annotations

import numpy as np


class FeatureError(ValueError):
    """Raised when a light curve cannot be turned into features."""


def normalize_curve(flux) -> np.ndarray:
    """Median/MAD standardization of a 1-D flux array."""
    x = np.asarray(flux, dtype=float)
    if x.ndim != 1 or x.size < 16:
        raise FeatureError("light curve must be a 1-D array with at least 16 points")
    if not np.all(np.isfinite(x)):
        raise FeatureError("light curve contains non-finite values")
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    if mad == 0.0:  # constant curve
        mad = 1e-9
    return (x - med) / mad


def detrend(z: np.ndarray, window: int = 64) -> np.ndarray:
    """Remove slow drift with a centered rolling median.

    The rolling median is robust to the short transit dips themselves, so
    the residual keeps the dips but drops the baseline wander.
    """
    if window < 3:
        raise FeatureError("detrend window must be at least 3")
    z = np.asarray(z, dtype=float)
    pad_left, pad_right = window // 2, window - 1 - window // 2
    padded = np.pad(z, (pad_left, pad_right), mode="edge")
    view = np.lib.stride_tricks.sliding_window_view(padded, window)
    return z - np.median(view, axis=1)


def _moments(z: np.ndarray) -> tuple[float, float]:
    std = float(z.std())
    if std == 0.0:
        return 0.0, 0.0
    m2, m3, m4 = float((z**2).mean()), float((z**3).mean()), float((z**4).mean())
    return m3 / m2**1.5, m4 / m2**2 - 3.0


def _autocorr_grid(x: np.ndarray, max_lag: int) -> np.ndarray:
    """Normalized autocorrelation at lags 1..max_lag (dot-product based)."""
    x = np.asarray(x, dtype=float)
    xc = x - x.mean()
    denom = float(np.dot(xc, xc))
    if denom == 0.0:
        return np.zeros(max_lag)
    grid = np.empty(max_lag)
    for lag in range(1, max_lag + 1):
        grid[lag - 1] = np.dot(xc[:-lag], xc[lag:]) / denom
    return grid


def _fft_features(z: np.ndarray) -> tuple[float, float]:
    spectrum = np.abs(np.fft.rfft(z - z.mean()))
    if spectrum.size < 2 or float(spectrum[1:].sum()) == 0.0:
        return 0.0, 0.0
    dominant = int(np.argmax(spectrum[1:])) + 1
    rel_freq = dominant / z.size
    eps = 1e-12
    flatness = float(np.exp(np.mean(np.log(spectrum[1:] + eps))) / (np.mean(spectrum[1:]) + eps))
    return rel_freq, flatness


def _max_consecutive(mask: np.ndarray) -> int:
    best = cur = 0
    for flagged in mask:
        cur = cur + 1 if flagged else 0
        if cur > best:
            best = cur
    return best


def extract_features(
    flux,
    detrend_window: int = 64,
    dip_threshold_mad: float = 3.0,
    autocorr_max_lag: int = 400,
) -> dict[str, float]:
    """Turn one light curve into an ordered dict of scalar features.

    The autocorrelation grid runs over lags 1..``autocorr_max_lag``; the
    full grid is kept because tree models can pick out the relevant lags
    (i.e. the transit period) themselves.
    """
    if detrend_window < 3:
        raise FeatureError("detrend_window must be at least 3")
    if dip_threshold_mad <= 0:
        raise FeatureError("dip_threshold_mad must be positive")
    if autocorr_max_lag < 8:
        raise FeatureError("autocorr_max_lag must be at least 8")

    z0 = normalize_curve(flux)
    z = detrend(z0, detrend_window)

    feats: dict[str, float] = {}
    feats["mean"] = float(z.mean())
    feats["std"] = float(z.std())
    skew, kurt = _moments(z)
    feats["skew"] = skew
    feats["kurtosis"] = kurt
    feats["min"] = float(z.min())
    feats["max"] = float(z.max())
    feats["p01"], feats["p05"], feats["p50"], feats["p95"], feats["p99"] = (
        float(p) for p in np.percentile(z, [1, 5, 50, 95, 99])
    )

    # dip morphology on the detrended curve (dips are short, drift is gone)
    dip_mask = z < -dip_threshold_mad
    feats["dip_count"] = float(dip_mask.sum())
    feats["dip_fraction"] = float(dip_mask.mean())
    feats["max_consecutive_dips"] = float(_max_consecutive(dip_mask))
    dip_values = z[dip_mask]
    feats["mean_dip_depth"] = float(dip_values.mean()) if dip_values.size else 0.0
    feats["deepest_dip"] = float(z.min())

    # periodicity: full autocorrelation grid + summary stats
    grid = _autocorr_grid(z, autocorr_max_lag)
    for lag in range(1, autocorr_max_lag + 1):
        feats[f"autocorr_{lag:03d}"] = float(grid[lag - 1])
    feats["peak_autocorr"] = float(grid.max())
    feats["best_lag"] = float(1 + int(np.argmax(grid)))

    rel_freq, flatness = _fft_features(z)
    feats["fft_dominant_freq"] = rel_freq
    feats["fft_flatness"] = flatness

    return feats
