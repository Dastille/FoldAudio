"""Blind absolute-level recovery for ShockDAQ — no original capture needed.

Problem (NOTES slice #2): Itoh unwrap recovers the folded waveform only up to an
unknown global offset 2λk. v0 picked k with the *original* signal (demo oracle),
which a live DAQ never has.

Prior used here (named ASSUMPTIONS — keep honest):
1. IEPE sensors are AC-coupled (constant-current bias + coupling cap), so the
   true acceleration signal has a near-zero long-run mean. If |mean(x)| < λ,
   k = round(−mean(ŷ) / 2λ) picks the right level exactly.
2. "quiet_window" variant: the lowest-variance window of the record sits on the
   AC-coupled baseline (near 0). Same physics, more robust when a big burst is
   asymmetric and drags the global mean.
3. Fails honestly if the record is one long DC-shifted event (|mean| ≳ λ) or the
   quietest window itself is offset by ≥ λ — that's reported, not hidden.
4. Pure numpy, CPU only. Itoh still needs max |Δx| < λ (unchanged limit).
"""

from __future__ import annotations

import numpy as np

from .unfold_detect import itoh_unwrap


def _offset_for_level(level: float, lam: float) -> int:
    """Integer k so that level + 2λk lands nearest 0."""
    return int(np.round(-level / (2.0 * lam)))


def quietest_window_mean(y: np.ndarray, win: int) -> float:
    """Mean of the minimum-variance length-`win` window (cumsum, O(n))."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n <= win:
        return float(np.mean(y))
    c1 = np.concatenate(([0.0], np.cumsum(y)))
    c2 = np.concatenate(([0.0], np.cumsum(y * y)))
    s1 = c1[win:] - c1[:-win]
    s2 = c2[win:] - c2[:-win]
    mean = s1 / win
    var = s2 / win - mean**2
    i = int(np.argmin(var))
    return float(mean[i])


def recover_blind(
    y_folded: np.ndarray,
    lam: float,
    *,
    prior: str = "zero_mean",
    win: int = 2048,
    fold_gain: float = 0.0,
) -> tuple[np.ndarray, int]:
    """Itoh unwrap + pick the 2λ offset from an AC-coupling prior (no original).

    Returns (recovered, k). prior ∈ {"zero_mean", "quiet_window"}.

    fold_gain = ĝ (2026-10-12 calibration slice): the front end's fold step is
    2λ(1+ĝ) instead of 2λ (gain mismatch, see failmap.NonIdeal.gain_err). Wraps
    are still *detected* with the 2λ Itoh rule, but each one is undone with the
    calibrated step 2λ(1+ĝ). ĝ comes from calibrate.estimate_front_end.
    fold_gain=0 is bit-identical to the uncalibrated path.
    """
    y = np.asarray(y_folded, dtype=float)
    y_hat = itoh_unwrap(y, lam)
    step = 2.0 * lam
    if fold_gain:
        wraps = np.round((y_hat - y) / (2.0 * lam))
        step = 2.0 * lam * (1.0 + fold_gain)
        y_hat = y + step * wraps
    if prior == "zero_mean":
        level = float(np.mean(y_hat))
    elif prior == "quiet_window":
        level = quietest_window_mean(y_hat, win)
    else:
        raise ValueError(f"unknown prior {prior!r}")
    k = int(np.round(-level / step))
    return y_hat + step * k, k


def inl_inverse(y_folded: np.ndarray, lam: float, coefs) -> np.ndarray:
    """Undo a calibrated INL bow: y − Σ_k α_k·sin(kπ·y/λ) (coefs = α_1..α_K in volts)."""
    y = np.asarray(y_folded, dtype=float)
    out = y.copy()
    for k, a in enumerate(coefs, start=1):
        out -= a * np.sin(k * np.pi * y / lam)
    return out


def rail_mask(y_folded: np.ndarray, lam: float, *, bits: int | None = None) -> np.ndarray:
    """Samples sitting at the ADC rails (value clipped; true folded value lies beyond)."""
    tol = lam * 1e-9 + (lam / 2 ** (bits - 1) if bits else 0.0)
    return np.abs(np.asarray(y_folded, dtype=float)) >= lam - tol


def naive_k0(y_folded: np.ndarray, lam: float) -> np.ndarray:
    """What v0 did with no anchor: trust folded[0] as the true level (k=0)."""
    return itoh_unwrap(np.asarray(y_folded, dtype=float), lam)


# ---------------------------------------------------------------------------
# Blind self-checks (moved here from failmap so shockdaq can use them without
# a circular import; failmap re-exports them).
# ---------------------------------------------------------------------------

EDGE_FRAC = 0.9


def slip_flag(recovered: np.ndarray, lam: float, *, frac: float = 0.2, win: int = 1024) -> bool:
    """Blind check: quiet baseline at the start vs end of record differ by > λ."""
    r = np.asarray(recovered, dtype=float)
    m = max(int(len(r) * frac), win + 1)
    a = quietest_window_mean(r[:m], win)
    b = quietest_window_mean(r[-m:], win)
    return bool(abs(a - b) > lam)


def edge_flag(y_folded: np.ndarray, lam: float, *, frac: float = EDGE_FRAC) -> bool:
    """Blind check: any wrapped folded step |d| ≥ frac·λ (recovery at its limit)."""
    d = np.diff(np.asarray(y_folded, dtype=float))
    d = d - 2.0 * lam * np.round(d / (2.0 * lam))
    return bool(np.any(np.abs(d) >= frac * lam))
