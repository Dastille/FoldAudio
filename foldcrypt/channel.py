"""Oversampled sinc channel model (paper §2).

ASSUMPTIONS (named):
- Pulse g(t) = sinc(2 W t) with T = 1/(2W) = 1 ⇒ W = 1/2.
- Oversampling factor OF: Fs = OF · 2W ⇒ Ts = 1/OF.
- Interpolation matrix H[n,m] = sinc(n/OF − m).
- Bandlimited noise after LPF: R_w(τ) = σ² sinc(2W τ) = σ² sinc(τ)
  sampled: Σ_w[i,j] = σ² sinc((i−j)/OF).
- Observation window: samples at n = 0..N−1 with N = (Ns − 1)*OF + 1,
  symbols at integer times m = 0..Ns−1. (Toy window; paper Fig. 2 uses
  main-lobe bounds — we name this simplification.)
"""

from __future__ import annotations

import numpy as np


def sinc(x: np.ndarray | float) -> np.ndarray | float:
    """Normalized sinc: sin(πx)/(πx), with sinc(0)=1."""
    return np.sinc(x)  # numpy sinc is sin(πx)/(πx)


def build_H(Ns: int, OF: int) -> np.ndarray:
    """H ∈ R^{N×Ns}, N = (Ns-1)*OF + 1."""
    if Ns < 1 or OF < 1:
        raise ValueError("Ns and OF must be >= 1")
    N = (Ns - 1) * OF + 1
    H = np.zeros((N, Ns), dtype=float)
    for n in range(N):
        for m in range(Ns):
            H[n, m] = float(sinc(n / OF - m))
    return H


def noise_covariance(N: int, OF: int, sigma: float) -> np.ndarray:
    """Σ_w[i,j] = σ² sinc((i−j)/OF)."""
    idx = np.arange(N)
    lags = idx[:, None] - idx[None, :]
    return (sigma**2) * sinc(lags / OF)


def sample_noise(Sigma: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Draw w ~ N(0, Σ). Falls back to eigendecomp if Cholesky fails."""
    N = Sigma.shape[0]
    try:
        L = np.linalg.cholesky(Sigma + 1e-12 * np.eye(N))
        return L @ rng.standard_normal(N)
    except np.linalg.LinAlgError:
        vals, vecs = np.linalg.eigh(Sigma)
        vals = np.clip(vals, 0.0, None)
        return vecs @ (np.sqrt(vals) * rng.standard_normal(N))


def transmit(
    a: np.ndarray,
    H: np.ndarray,
    lam: float,
    sigma: float,
    bits: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Generate folded+quantized observation y_λ = M_λ(H a + w) then quantize.

    Returns (y_q, Sigma_w, sigma_q2).
    """
    from .modulo import central_modulo, quantize_folded

    N = H.shape[0]
    OF_implied = max(1, (N - 1) // max(1, (len(a) - 1))) if len(a) > 1 else 1
    # Caller passes consistent OF via H; recover OF from H shape convention.
    # We recompute Sigma from N and inferred OF — prefer explicit OF.
    raise NotImplementedError("use transmit_with_OF")


def transmit_with_OF(
    a: np.ndarray,
    H: np.ndarray,
    OF: int,
    lam: float,
    sigma: float,
    bits: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    """y_λ pipeline: f=Ha, w~N(0,Σ_w), fold, quantize; also return unclipped path.

    Returns (y_q, Sigma_w, sigma_q2, y_unc) where y_unc = Ha + w (no fold, no quant).
    Oracle uses y_unc with sigma_q2=0; quantize_folded only covers [-λ, λ), so we
    skip quant on the unclipped reference for a clean ADC lower bound.
    """
    from .modulo import central_modulo, quantize_folded

    N = H.shape[0]
    Sigma = noise_covariance(N, OF, sigma)
    w = sample_noise(Sigma, rng)
    f = H @ a
    # Unclipped oracle observation: same noise draw, no fold / no quant.
    y_unc = f + w
    y_fold = central_modulo(y_unc, lam)
    y_q, sigma_q2 = quantize_folded(y_fold, lam, bits)
    return y_q, Sigma, sigma_q2, y_unc
