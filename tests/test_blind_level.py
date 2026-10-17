"""Blind absolute-level recovery (no original) — ShockDAQ slice 2026-10-06."""

from __future__ import annotations

import numpy as np
import pytest

from foldcrypt.blind_level import (
    estimate_noise_sigma,
    naive_k0,
    quietest_window_mean,
    quietest_window_std,
    recover_blind,
)
from foldcrypt.foldaudio import fold_capture, snr_db
from foldcrypt.shockdaq import DEFAULT_LAM_V, gen_gearbox_startup, gen_impact_transient

LAM = DEFAULT_LAM_V


def _start_at_peak(x):
    """Record that begins mid-overload (pre-trigger missed): folded[0] is wrapped."""
    return x[int(np.argmax(np.abs(x))) :]


@pytest.mark.parametrize("gen", [gen_gearbox_startup, gen_impact_transient])
@pytest.mark.parametrize("prior", ["zero_mean", "quiet_window"])
def test_blind_recovers_when_record_starts_mid_overload(gen, prior):
    x = _start_at_peak(gen(lam=LAM))
    assert abs(x[0]) > LAM
    y = fold_capture(x, LAM)
    rec, k = recover_blind(y, LAM, prior=prior)
    assert k != 0
    assert snr_db(x, rec) >= 100.0
    # The old no-anchor path (trust folded[0]) is badly wrong here.
    assert snr_db(x, naive_k0(y, LAM)) < 0.0


@pytest.mark.parametrize("gen", [gen_gearbox_startup, gen_impact_transient])
def test_blind_matches_oracle_on_quiet_start(gen):
    x = gen(lam=LAM)
    rec, k = recover_blind(fold_capture(x, LAM), LAM)
    assert k == 0
    assert snr_db(x, rec) >= 100.0


def test_blind_fails_honestly_on_dc_shift():
    """Not AC-coupled (mean ≳ λ) breaks the prior — documented limit."""
    x = gen_gearbox_startup(lam=LAM) + 1.2 * LAM
    rec, _ = recover_blind(fold_capture(x, LAM), LAM)
    assert snr_db(x, rec) < 0.0


def test_quietest_window_mean_finds_baseline():
    y = np.concatenate([np.full(500, 7.0) + np.sin(np.arange(500)), np.zeros(300)])
    assert abs(quietest_window_mean(y, 200)) < 1e-9


def test_unknown_prior_raises():
    with pytest.raises(ValueError):
        recover_blind(np.zeros(10), LAM, prior="nope")


# --- blind σ from quiet window (2026-10-16, NOTES #8b) ---------------------


def test_quietest_window_std_matches_mean_window():
    """std helper must pick the same quiet window the mean helper uses."""
    rng = np.random.default_rng(0)
    quiet = 0.05 * rng.standard_normal(800)
    loud = 3.0 + rng.standard_normal(800)
    y = np.concatenate([loud, quiet, loud])
    assert abs(quietest_window_mean(y, 200)) < 0.05
    # Quiet-window std should be near the injected 0.05, not the loud ~1
    s = quietest_window_std(y, 200)
    assert 0.03 < s < 0.08


def test_estimate_noise_sigma_tracks_injected_sigma():
    """On synthetic quiet baseline + white noise, blind σ tracks injected σ."""
    rng = np.random.default_rng(42)
    n = 20_000
    win = 2048
    for sigma in (0.01, 0.05, 0.2, 1.0):
        # Quiet AC-coupled baseline + a mid-record burst (does not pollute quiet window)
        y = sigma * rng.standard_normal(n)
        burst = np.zeros(n)
        burst[n // 2 : n // 2 + 500] = 4.0 * np.sin(np.linspace(0, 20 * np.pi, 500))
        y = y + burst
        hat = estimate_noise_sigma(y, win=win)
        # Population std of N(0,σ) over 2048 samples: relative error ~ few %
        assert abs(hat - sigma) / sigma < 0.08, (sigma, hat)


def test_estimate_noise_sigma_on_folded_capture():
    """Folded quiet samples stay inside (−λ, λ); estimate still tracks σ."""
    rng = np.random.default_rng(7)
    n = 16_384
    sigma = 0.08 * LAM
    x = sigma * rng.standard_normal(n)
    # Mid-record overload that will wrap under fold
    t = np.arange(800) / 800.0
    x[6000:6800] += 3.0 * LAM * np.exp(-3 * t) * np.sin(2 * np.pi * 12 * t)
    y = fold_capture(x, LAM)
    hat = estimate_noise_sigma(y, win=2048)
    assert abs(hat - sigma) / sigma < 0.10, (sigma, hat)
