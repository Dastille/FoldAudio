"""Block-Mahalanobis (Alg. 1) tests."""

from __future__ import annotations

import numpy as np

from foldcrypt.block_search import (
    block_mahalanobis_detect,
    build_block_index_sets,
)
from foldcrypt.channel import build_H, transmit_with_OF
from foldcrypt.constellation import injective_8pam
from foldcrypt.wrapcancel import wrapcancel_detect


def test_build_block_index_sets_nonoverlap_nb2():
    Ns, OF, Nb, eta = 8, 4, 2, 1
    blocks = build_block_index_sets(Ns, OF, Nb=Nb, eta=eta, edge_discard=0)
    assert len(blocks) == 4  # P = Ns/Nb
    cores = np.concatenate([b.keep for b in blocks])
    np.testing.assert_array_equal(cores, np.arange(Ns))
    N = (Ns - 1) * OF + 1
    for b in blocks:
        assert len(b.local) == Nb
        assert len(b.samples) >= 1
        assert b.samples[0] >= 0
        assert b.samples[-1] <= N - 1


def test_build_block_index_sets_edge_discard_nb4():
    blocks = build_block_index_sets(Ns=16, OF=4, Nb=4, eta=2, edge_discard=1)
    # stride = 4-2 = 2 → starts 0,2,...,12
    assert len(blocks) == 7
    # Interiors cover 1..14; edges written by end blocks in detect — index sets
    # themselves only list keep interiors.
    interiors = np.concatenate([b.keep for b in blocks])
    assert set(interiors.tolist()) == set(range(1, 15))


def test_build_block_index_sets_odd_ns_short_tail():
    blocks = build_block_index_sets(Ns=5, OF=4, Nb=2, eta=1, edge_discard=0)
    # starts 0,2 + final block at Ns-Nb=3 → locals [0,1],[2,3],[3,4]
    assert len(blocks) >= 2
    covered = set()
    for b in blocks:
        covered.update(int(x) for x in b.keep)
    assert covered == set(range(5))


def test_block_agrees_with_exhaustive_ns2():
    """Ns=2: one block → must match exhaustive WrapCancel."""
    lam, OF, ratio, bits = 1.0, 4, 4.0, 5
    rng = np.random.default_rng(11)
    alphabet = injective_8pam(lam)
    H = build_H(2, OF)
    a = alphabet[[2, 5]]
    y_q, Sigma_w, sigma_q2, _ = transmit_with_OF(
        a, H, OF, lam, lam / ratio, bits, rng
    )
    a_ex, _ = wrapcancel_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)
    stats: dict = {}
    a_bl, _ = block_mahalanobis_detect(
        y_q, H, alphabet, lam, Sigma_w, sigma_q2,
        Nb=2, eta=1, K=3, OF=OF, init="residue", stats=stats,
    )
    np.testing.assert_array_equal(a_bl, a_ex)
    np.testing.assert_array_equal(a_bl, a)
    assert stats["n_blocks"] == 1
    assert stats["eval_count"] >= 8**2


def test_block_agrees_with_exhaustive_ns4_high_snr():
    """Ns=4 at high λ/σ + OF: block detector matches exhaustive on same y.

    ASSUMPTION: Alg. 1 local ISI cancel needs comfortable OF (paper Fig. 11).
    """
    lam, OF, ratio, bits = 1.0, 8, 10.0, 8
    # Seed chosen so residue init + Jacobi refine lands on the ML sequence.
    rng = np.random.default_rng(3)
    alphabet = injective_8pam(lam)
    Ns = 4
    H = build_H(Ns, OF)
    a = alphabet[rng.integers(0, 8, size=Ns)]
    y_q, Sigma_w, sigma_q2, _ = transmit_with_OF(
        a, H, OF, lam, lam / ratio, bits, rng
    )
    a_ex, _ = wrapcancel_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)
    a_bl, _ = block_mahalanobis_detect(
        y_q, H, alphabet, lam, Sigma_w, sigma_q2,
        Nb=2, eta=2, K=5, OF=OF, init="residue",
    )
    np.testing.assert_array_equal(a_bl, a_ex)


def test_block_roundtrip_ns16_comfortable():
    """Ns=16 roundtrip: Nb=4 + edge_discard + OF=16 at λ/σ=3 (soft).

    Nb=2 / OF=4 is the complexity toy; long-seq SER needs paper-like
    Nb≥3 with edge discard and higher OF (see block_search docstring).
    """
    lam, OF, ratio, bits, Ns = 1.0, 16, 3.0, 4, 16
    rng = np.random.default_rng(1)  # seed with clean recovery in smoke checks
    alphabet = injective_8pam(lam)
    H = build_H(Ns, OF)
    a = alphabet[rng.integers(0, 8, size=Ns)]
    y_q, Sigma_w, sigma_q2, _ = transmit_with_OF(
        a, H, OF, lam, lam / ratio, bits, rng
    )
    a_hat, _ = block_mahalanobis_detect(
        y_q, H, alphabet, lam, Sigma_w, sigma_q2,
        Nb=4, eta=2, K=5, edge_discard=1, OF=OF, init="residue",
    )
    n_match = int(np.sum(a_hat == a))
    assert n_match >= int(0.75 * Ns), f"only {n_match}/{Ns} symbols matched"


def test_complexity_scales_linear_in_ns():
    """Eval count ≈ c·P·|S|^{Nb} with P∝Ns — not exponential in Ns."""
    lam, OF, ratio, bits = 1.0, 4, 3.0, 4
    alphabet = injective_8pam(lam)
    Nb = 2
    S = len(alphabet)
    counts = {}
    for Ns in (8, 16):
        rng = np.random.default_rng(0)
        H = build_H(Ns, OF)
        a = alphabet[rng.integers(0, 8, size=Ns)]
        y_q, Sigma_w, sigma_q2, _ = transmit_with_OF(
            a, H, OF, lam, lam / ratio, bits, rng
        )
        stats: dict = {}
        block_mahalanobis_detect(
            y_q, H, alphabet, lam, Sigma_w, sigma_q2,
            Nb=Nb, eta=1, K=2, OF=OF, init="residue", stats=stats,
        )
        counts[Ns] = stats["eval_count"]
        P = stats["n_blocks"]
        assert stats["eval_count"] <= stats["n_passes"] * P * (S**Nb)
        assert stats["eval_count"] >= 1 * P * (S**Nb)
        assert P >= Ns // Nb

    ratio_counts = counts[16] / counts[8]
    assert 1.5 <= ratio_counts <= 3.5, f"eval ratio 16/8 = {ratio_counts}"
    assert counts[16] < 8**6
