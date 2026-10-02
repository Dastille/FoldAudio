"""Naive unfold-then-detect baseline (intentionally weaker).

ASSUMPTION (named): we do *not* reimplement ITER-SIS / B2R2 / CBHF from the
paper.  Those are heavy.  For the toy comparison we use classic first-order
Itoh-style phase unwrapping on the folded samples, then nearest-constellation
ML *without* modulo on the unwrapped waveform.

This is a fair "do people still unfold?" strawman: it needs oversampling to
keep consecutive sample jumps < λ, and it fails when wraps + noise create
ambiguous jumps — exactly the regime WrapCancel is meant to beat.
"""

from __future__ import annotations

import itertools

import numpy as np

from .modulo import central_modulo


def itoh_unwrap(y_lam: np.ndarray, lam: float) -> np.ndarray:
    """First-order unwrap: correct jumps whose absolute value exceeds λ.

    Absolute level is anchored at y_lam[0] (folded).  Global 2λ ambiguity
    is resolved later by trying a few integer offsets at detection time.
    """
    y = np.asarray(y_lam, dtype=float)
    out = np.empty_like(y)
    out[0] = y[0]
    for i in range(1, len(y)):
        d = y[i] - y[i - 1]
        # Bring difference into (−λ, λ] by subtracting 2λ wraps
        d = d - 2.0 * lam * np.round(d / (2.0 * lam))
        out[i] = out[i - 1] + d
    return out


def unfold_then_detect(
    y_lam: np.ndarray,
    H: np.ndarray,
    alphabet: np.ndarray,
    lam: float,
    Sigma_w: np.ndarray,
    sigma_q2: float,
    offset_search: int = 3,
) -> tuple[np.ndarray, float]:
    """Unwrap with Itoh, then Mahalanobis ML on (ŷ − Ha), trying 2λ offsets.

    `offset_search`: try global additive offsets {−K..K}·2λ on the unwrapped
    waveform to absorb absolute-level ambiguity (ASSUMPTION: small K enough
    for our injective alphabet with |z|≤5).
    """
    Ns = H.shape[1]
    N = H.shape[0]
    y_hat = itoh_unwrap(y_lam, lam)
    Sigma = Sigma_w + sigma_q2 * np.eye(N)
    Sigma_inv = np.linalg.inv(Sigma + 1e-12 * np.eye(N))

    best_a = None
    best_m = np.inf
    for k in range(-offset_search, offset_search + 1):
        y_try = y_hat + 2.0 * lam * k
        for idxs in itertools.product(range(len(alphabet)), repeat=Ns):
            a = alphabet[list(idxs)]
            r = y_try - H @ a
            m = float(r @ (Sigma_inv @ r))
            if m < best_m:
                best_m = m
                best_a = a.copy()
    assert best_a is not None
    return best_a, best_m
