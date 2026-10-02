"""Block-Mahalanobis WrapCancel search (arXiv:2609.11298 §3.2 Alg. 1).

Plain language
--------------
Exhaustive WrapCancel costs |S|^{Ns} — fine for Ns=2, impossible for Ns=64.
Alg. 1 chops the long sequence into P short blocks of Nb symbols each,
subtracts estimated external ISI from neighboring symbols, then runs a tiny
exhaustive search (|S|^{Nb}) inside each block. A few parallel passes refine
the neighbors. Complexity is O(K · P · |S|^{Nb} · …) — **linear in Ns** when
P ∝ Ns, not 8^{Ns}.

Toy defaults (documented)
-------------------------
- Nb=2  (cheap |S|^{Nb}=64; good for complexity checks)
- η=1   (one-symbol sample margin on each side of the block)
- K=3   (max passes; early-stop when â stabilizes)
- edge_discard=0 when Nb=2 (keep both); use edge_discard=1 when Nb≥3
  so only interior cores are merged (paper spirit)
- stride = max(1, Nb − 2·edge_discard) so discarded edges are covered
  as interiors of neighboring blocks
- Init â⁽⁰⁾: **Nyquist residue decode** (nearest injective residue at
  sample n=m·OF). Mid-alphabet / zeros also available via `init=`.

ASSUMPTION / known limit
------------------------
Local ISI cancel is approximate at low OF: the toy needs comfortable
oversampling for long-Ns SER (paper Fig. 11). Nb=2 at OF=4 is fine for
complexity demos; for roundtrip on Ns≳16 prefer Nb≥3 with edge_discard=1
and OF≳8–16. Soft-freeze: no Ns=64 Monte Carlo SER table.

Jacobi updates (paper: blocks in parallel) — each pass reads â⁽ᵏ⁻¹⁾ only.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .modulo import central_modulo


InitKind = Literal["residue", "mid", "zeros"]


@dataclass(frozen=True)
class BlockSpec:
    """One Alg. 1 block: local symbol indices C_j, retained cores, sample window I_j."""

    local: np.ndarray  # shape (Nb_eff,), symbols searched in this block
    keep: np.ndarray  # subset of local merged into the global estimate
    samples: np.ndarray  # shape (n_j,), sample indices I_j


def build_block_index_sets(
    Ns: int,
    OF: int,
    Nb: int = 2,
    eta: int = 1,
    edge_discard: int = 0,
) -> list[BlockSpec]:
    """Partition into overlapping/non-overlapping blocks with η-sample margins.

    Sample window for local symbols C = {c0..c_end}:
        I = {n : max(0, (c0−η)·OF) ≤ n ≤ min(N−1, (c_end+η)·OF)}
    with N = (Ns−1)·OF + 1.

    Stride = max(1, Nb − 2·edge_discard). When edge_discard>0, only the
    interior keep = local[edge_discard : −edge_discard] is merged (first/last
    blocks also write their outer edges so the sequence is fully covered).

    When Ns % stride leaves a tail, a final block ending at Ns−1 is appended.
    """
    if Ns < 1 or OF < 1 or Nb < 1 or eta < 0 or edge_discard < 0:
        raise ValueError("Ns, OF, Nb >= 1; eta, edge_discard >= 0")
    if edge_discard > 0 and Nb <= 2 * edge_discard:
        raise ValueError("Nb must be > 2*edge_discard when discarding edges")

    N = (Ns - 1) * OF + 1
    stride = max(1, Nb - 2 * edge_discard)
    starts: list[int] = []
    c = 0
    while c + Nb <= Ns:
        starts.append(c)
        c += stride
    if not starts:
        starts = [0]
    elif starts[-1] + Nb < Ns:
        starts.append(max(0, Ns - Nb))
    starts = sorted(set(starts))

    blocks: list[BlockSpec] = []
    for c0 in starts:
        c_end = min(c0 + Nb, Ns)
        local = np.arange(c0, c_end, dtype=int)
        nb_eff = len(local)
        if edge_discard > 0 and nb_eff > 2 * edge_discard:
            keep = local[edge_discard : nb_eff - edge_discard].copy()
        else:
            keep = local.copy()
        n_lo = max(0, (int(local[0]) - eta) * OF)
        n_hi = min(N - 1, (int(local[-1]) + eta) * OF)
        samples = np.arange(n_lo, n_hi + 1, dtype=int)
        blocks.append(BlockSpec(local=local, keep=keep, samples=samples))
    return blocks


def _residue_init(
    y_lam: np.ndarray,
    alphabet: np.ndarray,
    lam: float,
    OF: int,
    Ns: int,
) -> np.ndarray:
    """Nearest injective residue at Nyquist sample n = m·OF for each symbol."""
    residues = np.asarray(central_modulo(alphabet, lam), dtype=float)
    a0 = np.zeros(Ns, dtype=float)
    for m in range(Ns):
        n = min(m * OF, len(y_lam) - 1)
        d = np.abs(central_modulo(y_lam[n] - residues, lam))
        a0[m] = float(alphabet[int(np.argmin(d))])
    return a0


def _mid_alphabet_init(alphabet: np.ndarray, Ns: int) -> np.ndarray:
    mid = alphabet[len(alphabet) // 2]
    return np.full(Ns, mid, dtype=float)


def _local_mahalanobis_search(
    y_eff: np.ndarray,
    H_local: np.ndarray,
    alphabet: np.ndarray,
    lam: float,
    Sigma_Tj_inv: np.ndarray,
    Nb_eff: int,
) -> tuple[np.ndarray, float, int]:
    """Exhaustive ML over S^{Nb_eff}; returns (â_j, metric, n_evals)."""
    best_a = None
    best_m = np.inf
    n_evals = 0
    for idxs in itertools.product(range(len(alphabet)), repeat=Nb_eff):
        a = alphabet[list(idxs)]
        r = central_modulo(y_eff - H_local @ a, lam)
        m = float(r @ (Sigma_Tj_inv @ r))
        n_evals += 1
        if m < best_m:
            best_m = m
            best_a = a.copy()
    assert best_a is not None
    return best_a, best_m, n_evals


def block_mahalanobis_detect(
    y_lam: np.ndarray,
    H: np.ndarray,
    alphabet: np.ndarray,
    lam: float,
    Sigma_w: np.ndarray,
    sigma_q2: float,
    *,
    Nb: int = 2,
    eta: int = 1,
    K: int = 3,
    edge_discard: int = 0,
    OF: int | None = None,
    init: InitKind = "residue",
    stats: dict[str, Any] | None = None,
) -> tuple[np.ndarray, float]:
    """Paper Algorithm 1 — block-decomposed WrapCancel for long sequences.

    Parameters
    ----------
    Nb, eta, K :
        Block size, sample-side margin (symbol units), max passes.
    edge_discard :
        Drop this many symbols from each end of a block when merging.
        0 for Nb=2 (keep both). Use 1 when Nb≥3 (paper spirit).
    OF :
        Oversampling factor. If None, inferred from H as (N−1)//(Ns−1).
    init :
        ``residue`` (default) — Nyquist nearest-residue decode;
        ``mid`` — mid-alphabet constant; ``zeros`` — all-zero start.
    stats :
        Optional dict filled with eval_count, n_passes, n_blocks, early_stop.

    Returns
    -------
    (â, metric) — global Mahalanobis length of the final estimate.
    """
    Ns = int(H.shape[1])
    N = int(H.shape[0])
    if OF is None:
        OF = 1 if Ns <= 1 else max(1, (N - 1) // (Ns - 1))

    # Auto edge_discard for Nb≥3 if caller left default 0? Keep explicit —
    # callers who want paper edge discard pass edge_discard=1.

    Sigma_T = Sigma_w + sigma_q2 * np.eye(N)
    Sigma_T_inv = np.linalg.inv(Sigma_T + 1e-12 * np.eye(N))

    blocks = build_block_index_sets(Ns, OF, Nb=Nb, eta=eta, edge_discard=edge_discard)

    if init == "residue":
        a_hat = _residue_init(y_lam, alphabet, lam, OF, Ns)
    elif init == "mid":
        a_hat = _mid_alphabet_init(alphabet, Ns)
    elif init == "zeros":
        a_hat = np.zeros(Ns, dtype=float)
    else:
        raise ValueError(f"unknown init={init!r}")

    local_inv: list[np.ndarray] = []
    local_H: list[np.ndarray] = []
    for blk in blocks:
        I = blk.samples
        Cj = blk.local
        Sig_j = Sigma_T[np.ix_(I, I)]
        local_inv.append(np.linalg.inv(Sig_j + 1e-12 * np.eye(len(I))))
        local_H.append(H[np.ix_(I, Cj)])

    eval_count = 0
    n_passes = 0
    early_stop = False

    for _k in range(1, K + 1):
        a_prev = a_hat.copy()
        a_new = a_hat.copy()
        # Jacobi: all blocks read â^(k-1) only (paper: "in parallel")
        for j, blk in enumerate(blocks):
            I = blk.samples
            Cj = blk.local
            keep = blk.keep
            Nb_eff = len(Cj)
            d_j = H[I, :] @ a_prev - local_H[j] @ a_prev[Cj]
            y_eff = y_lam[I] - d_j
            a_j, _m_j, n_ev = _local_mahalanobis_search(
                y_eff, local_H[j], alphabet, lam, local_inv[j], Nb_eff
            )
            eval_count += n_ev
            # Merge keep cores; first/last blocks also write outer edges
            keep_set = set(int(x) for x in keep)
            for i, sidx in enumerate(Cj):
                s = int(sidx)
                write = s in keep_set
                if edge_discard > 0:
                    if Cj[0] == 0 and i < edge_discard:
                        write = True
                    if Cj[-1] == Ns - 1 and i >= Nb_eff - edge_discard:
                        write = True
                if write:
                    a_new[s] = a_j[i]
        a_hat = a_new
        n_passes += 1
        if np.array_equal(a_hat, a_prev):
            early_stop = True
            break

    r = central_modulo(y_lam - H @ a_hat, lam)
    metric = float(r @ (Sigma_T_inv @ r))

    if stats is not None:
        stats.clear()
        stats.update(
            {
                "eval_count": eval_count,
                "n_passes": n_passes,
                "n_blocks": len(blocks),
                "early_stop": early_stop,
                "Nb": Nb,
                "eta": eta,
                "K": K,
                "edge_discard": edge_discard,
                "Ns": Ns,
                "OF": OF,
                "init": init,
            }
        )
    return a_hat, metric
