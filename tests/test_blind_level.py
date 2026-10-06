"""Blind absolute-level recovery (no original) — ShockDAQ slice 2026-10-06."""

from __future__ import annotations

import numpy as np
import pytest

from foldcrypt.blind_level import naive_k0, quietest_window_mean, recover_blind
from foldcrypt.foldaudio import fold_capture, snr_db
from foldcrypt.shockdaq import DEFAULT_LAM_V, gen_gearbox_startup, gen_impact_transient

LAM = DEFAULT_LAM_V


def _start_at_peak(x):
    """Record that begins mid-overload (pre-trigger missed): folded[0] is wrapped."""
    return x[int(np.argmax(np.abs(x))):]


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
