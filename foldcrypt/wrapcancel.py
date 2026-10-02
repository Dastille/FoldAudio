"""WrapCancel Mahalanobis detector (arXiv:2609.11298 §3.1).

Core idea in plain language
---------------------------
Folding adds unknown integer wraps z.  If you subtract a candidate symbol
vector Ha from the folded observation and wrap again,

    r(a) ≜ M_λ(y_λ − H a)

the unknown wraps cancel (they live in the kernel of M_λ).  When noise is
not too large relative to λ (λ/σ ≳ 2–3), r(a_true) ≈ w + q, so the best
candidate is the one whose residual has smallest Mahalanobis length under
the known noise covariance:

    â = arg min_a  r(a)ᵀ Σ_T⁻¹ r(a),   Σ_T = Σ_w + σ_q² I

ASSUMPTION: wrapcancel_detect uses exhaustive search over S^{Ns}
(Ns small, ≤3 or 4). For long sequences use block_mahalanobis_detect
(paper Alg. 1) in block_search.py — see NOTES.md / README.
"""

from __future__ import annotations

import itertools
from typing import Sequence

import numpy as np

from .modulo import central_modulo


def mahalanobis_metric(
    y_lam: np.ndarray,
    a: np.ndarray,
    H: np.ndarray,
    lam: float,
    Sigma_T_inv: np.ndarray,
) -> float:
    """Compute r(a)ᵀ Σ_T⁻¹ r(a) with r(a) = M_λ(y_λ − H a)."""
    r = central_modulo(y_lam - H @ a, lam)
    return float(r @ (Sigma_T_inv @ r))


def wrapcancel_detect(
    y_lam: np.ndarray,
    H: np.ndarray,
    alphabet: np.ndarray,
    lam: float,
    Sigma_w: np.ndarray,
    sigma_q2: float,
) -> tuple[np.ndarray, float]:
    """Exhaustive WrapCancel ML over alphabet^{Ns}.

    Returns (â, best_metric).
    """
    Ns = H.shape[1]
    N = H.shape[0]
    Sigma_T = Sigma_w + sigma_q2 * np.eye(N)
    # Stabilize inverse
    Sigma_T_inv = np.linalg.inv(Sigma_T + 1e-12 * np.eye(N))

    best_a = None
    best_m = np.inf
    # itertools product over alphabet indices
    for idxs in itertools.product(range(len(alphabet)), repeat=Ns):
        a = alphabet[list(idxs)]
        m = mahalanobis_metric(y_lam, a, H, lam, Sigma_T_inv)
        if m < best_m:
            best_m = m
            best_a = a.copy()
    assert best_a is not None
    return best_a, best_m


def oracle_unclipped_detect(
    y_unclipped: np.ndarray,
    H: np.ndarray,
    alphabet: np.ndarray,
    Sigma_w: np.ndarray,
    sigma_q2: float = 0.0,
) -> tuple[np.ndarray, float]:
    """ML on unclipped (no modulo) observations — performance lower bound.

    Metric: (y − Ha)ᵀ Σ⁻¹ (y − Ha).  Used only as a reference curve.
    """
    Ns = H.shape[1]
    N = H.shape[0]
    Sigma = Sigma_w + sigma_q2 * np.eye(N)
    Sigma_inv = np.linalg.inv(Sigma + 1e-12 * np.eye(N))
    best_a = None
    best_m = np.inf
    for idxs in itertools.product(range(len(alphabet)), repeat=Ns):
        a = alphabet[list(idxs)]
        r = y_unclipped - H @ a
        m = float(r @ (Sigma_inv @ r))
        if m < best_m:
            best_m = m
            best_a = a.copy()
    assert best_a is not None
    return best_a, best_m


# Re-export Alg. 1 for discoverability next to the exhaustive detector.
from .block_search import block_mahalanobis_detect, build_block_index_sets  # noqa: E402

__all__ = [
    "mahalanobis_metric",
    "wrapcancel_detect",
    "oracle_unclipped_detect",
    "block_mahalanobis_detect",
    "build_block_index_sets",
]

