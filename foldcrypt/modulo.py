"""Centered modulo folding and low-bit quantization.

ASSUMPTION (named): we use the *central* modulo of Vaghela et al.:
    M_λ(x) ≜ mod(x + λ, 2λ) − λ  ∈ [−λ, λ)

This is the wrap that a modulo-ADC applies before quantization.
Unknown integer wraps live in the kernel of M_λ (adding 2λz does nothing).
"""

from __future__ import annotations

import numpy as np


def central_modulo(x: np.ndarray | float, lam: float) -> np.ndarray | float:
    """M_λ(x) = mod(x + λ, 2λ) − λ, range [−λ, λ).

    ASSUMPTION: lam > 0. For arrays, applied elementwise.
    """
    if lam <= 0:
        raise ValueError("lam must be positive")
    # Use floor-based form for numerical stability near boundaries.
    # Equivalent to ((x + lam) % (2*lam)) - lam, mapped into [-lam, lam).
    y = x + lam
    two = 2.0 * lam
    y = y - two * np.floor(y / two)
    out = y - lam
    # Map +lam endpoint to -lam to keep half-open interval [-lam, lam).
    if isinstance(out, np.ndarray):
        out = np.where(out >= lam - 1e-15, out - two, out)
    elif out >= lam - 1e-15:
        out = out - two
    return out


def quantize_folded(
    y_folded: np.ndarray,
    lam: float,
    bits: int,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, float]:
    """Uniform mid-riser quantizer on [−λ, λ) with `bits` resolution.

    ASSUMPTION (paper eq.): step Δ = λ / 2^{R−1}, quantization noise
    modeled as uniform on [−Δ/2, Δ/2] with variance σ_q² = Δ²/12.
    Here we *actually* quantize (not just add Gaussian surrogate).

    Returns (y_q, sigma_q2).
    """
    if bits < 1:
        raise ValueError("bits must be >= 1")
    delta = lam / (2 ** (bits - 1))
    # Mid-riser levels in [-lam, lam)
    n_levels = 2**bits
    # Map continuous folded value to nearest reconstruction level.
    # Scale to [0, n_levels).
    u = (y_folded + lam) / (2.0 * lam)  # in [0, 1)
    u = np.clip(u, 0.0, 1.0 - 1e-15)
    idx = np.floor(u * n_levels).astype(int)
    idx = np.clip(idx, 0, n_levels - 1)
    # Reconstruction at bin centers
    y_q = -lam + (idx + 0.5) * (2.0 * lam / n_levels)
    # Keep in [-lam, lam)
    y_q = central_modulo(y_q, lam)
    sigma_q2 = (delta**2) / 12.0
    return y_q, sigma_q2
