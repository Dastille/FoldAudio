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
) -> tuple[np.ndarray, int]:
    """Itoh unwrap + pick the 2λ offset from an AC-coupling prior (no original).

    Returns (recovered, k). prior ∈ {"zero_mean", "quiet_window"}.
    """
    y_hat = itoh_unwrap(np.asarray(y_folded, dtype=float), lam)
    if prior == "zero_mean":
        level = float(np.mean(y_hat))
    elif prior == "quiet_window":
        level = quietest_window_mean(y_hat, win)
    else:
        raise ValueError(f"unknown prior {prior!r}")
    k = _offset_for_level(level, lam)
    return y_hat + 2.0 * lam * k, k


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
