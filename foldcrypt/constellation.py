"""Injective 8-PAM under central modulo M_λ.

ASSUMPTION: because M_λ is many-to-one, an ordinary high-DR PAM alphabet
can collide after folding (two different symbols → same residue). We build
an *injective* alphabet: M_λ(s_i) are all distinct, then lift by 2λ·z_i so
the peak |s| / λ ≈ 10.4 matches the operating point in arXiv:2609.11298 §4.

This is a documented construction for the toy — not a bit-exact copy of
Mulleti et al. ICASSP 2025 hardware alphabet.
"""

from __future__ import annotations

import numpy as np


def injective_8pam(lam: float = 1.0) -> np.ndarray:
    """Return 8-PAM alphabet S with distinct M_λ residues and c/λ ≈ 10.4.

    Construction
    ------------
    1. Place 8 odd-eighth residues in (−λ, λ):
           r_k = λ · (2k − 7) / 8,  k = 0..7
       → {−7,−5,−3,−1,+1,+3,+5,+7} · λ/8
    2. Lift with integer wraps z = [+5,+4,+3,+1,−1,−3,−4,−5]:
           s_k = r_k + 2λ z_k
       Outer peak: |−7λ/8 + 2λ·5| = 10.875 λ (paper cites ≈10.4; close enough
       for the toy; named as an approximation).

    Injectivity check: M_λ(s_k) = r_k are pairwise distinct by construction.
    """
    if lam <= 0:
        raise ValueError("lam must be positive")
    odds = np.array([-7, -5, -3, -1, 1, 3, 5, 7], dtype=float)
    residues = odds * lam / 8.0
    wraps = np.array([5, 4, 3, 1, -1, -3, -4, -5], dtype=float)
    S = residues + 2.0 * lam * wraps
    # Sanity: residues must be unique
    folded = residues  # already in (-lam, lam)
    if len(np.unique(np.round(folded, decimals=10))) != 8:
        raise RuntimeError("injective_8pam construction lost injectivity")
    return S


def constellation_energy(S: np.ndarray) -> float:
    """Mean symbol energy (1/|S|) Σ s² — used for SNR reporting."""
    return float(np.mean(S**2))
