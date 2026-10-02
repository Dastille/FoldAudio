"""WrapCancel / unfold / oracle tests."""

from __future__ import annotations

import numpy as np
from foldcrypt.channel import build_H, noise_covariance, sample_noise, transmit_with_OF
from foldcrypt.constellation import injective_8pam
from foldcrypt.modulo import central_modulo
from foldcrypt.simulate import run_ser_point
from foldcrypt.wrapcancel import wrapcancel_detect


def test_central_modulo_range_and_kernel():
    lam = 1.5
    x = np.array([-3.2, -1.5, 0.0, 1.4, 4.7, 10.0])
    y = central_modulo(x, lam)
    assert np.all(y >= -lam - 1e-12)
    assert np.all(y < lam + 1e-12)
    # Kernel: adding 2λz does not change residue
    z = np.array([2, -1, 0, 3, -2, 1])
    y2 = central_modulo(x + 2 * lam * z, lam)
    np.testing.assert_allclose(y, y2, atol=1e-10)


def test_injective_8pam_distinct_residues():
    lam = 1.0
    S = injective_8pam(lam)
    assert len(S) == 8
    folded = central_modulo(S, lam)
    uniq = np.unique(np.round(folded, decimals=8))
    assert len(uniq) == 8
    # Peak compression near paper's ~10.4
    c_over_lam = float(np.max(np.abs(S)) / lam)
    assert 8.0 < c_over_lam < 12.0


def test_wrap_cancellation_identity():
    """r(a_true) ≈ w when no quantization and |w|<λ (paper eq. 8)."""
    lam = 1.0
    OF = 4
    Ns = 2
    sigma = lam / 5.0  # comfortable λ/σ
    rng = np.random.default_rng(1)
    alphabet = injective_8pam(lam)
    H = build_H(Ns, OF)
    a = alphabet[[0, 3]]
    # Build y_λ = M_λ(Ha + w) without quant
    N = H.shape[0]
    Sigma = noise_covariance(N, OF, sigma)
    w = sample_noise(Sigma, rng)
    # Clamp rare outliers for this unit test of the identity
    w = np.clip(w, -lam * 0.99, lam * 0.99)
    y = central_modulo(H @ a + w, lam)
    r = central_modulo(y - H @ a, lam)
    np.testing.assert_allclose(r, w, atol=1e-9)


def test_roundtrip_wrapcancel_cleanish():
    lam = 1.0
    OF = 4
    ratio = 3.0
    Ns = 2
    bits = 5
    rng = np.random.default_rng(7)
    alphabet = injective_8pam(lam)
    H = build_H(Ns, OF)
    a = alphabet[[1, 6]]
    y_q, Sigma_w, sigma_q2, _y_unc = transmit_with_OF(
        a, H, OF, lam, lam / ratio, bits, rng
    )
    a_hat, _ = wrapcancel_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)
    np.testing.assert_array_equal(a_hat, a)


def test_ser_wrapcancel_beats_or_ties_unfold_at_high_oversample():
    """At OF=8, λ/σ=3, WrapCancel should not be worse than naive unfold (soft)."""
    row = run_ser_point(OF=8, lam_over_sigma=3.0, Ns=2, bits=4, n_trials=40, seed=99)
    # Allow statistical wobble but WrapCancel should be competitive
    assert row.ser_wrapcancel <= row.ser_unfold + 0.15


def test_oracle_ser_le_wrapcancel_at_comfortable_point():
    """Unclipped oracle should not be worse than WrapCancel (soft tolerance)."""
    row = run_ser_point(OF=4, lam_over_sigma=3.0, Ns=2, bits=4, n_trials=50, seed=77)
    # Oracle is a lower bound; allow small Monte Carlo wobble
    assert row.ser_oracle <= row.ser_wrapcancel + 0.05


def test_deterministic_with_fixed_seed():
    r1 = run_ser_point(OF=2, lam_over_sigma=3.0, Ns=2, bits=4, n_trials=15, seed=123)
    r2 = run_ser_point(OF=2, lam_over_sigma=3.0, Ns=2, bits=4, n_trials=15, seed=123)
    assert r1.ser_wrapcancel == r2.ser_wrapcancel
    assert r1.ser_unfold == r2.ser_unfold
    assert r1.ser_oracle == r2.ser_oracle
