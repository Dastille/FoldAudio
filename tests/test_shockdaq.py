"""ShockDAQ v0 — IEPE fold-vs-clip metrics + overload flag."""

from __future__ import annotations

import numpy as np
import pytest

from foldcrypt.foldaudio import fold_capture, hard_clip, max_sample_jump, recover_itoh, snr_db
from foldcrypt.shockdaq import (
    DEFAULT_LAM_V,
    gen_gearbox_startup,
    gen_impact_transient,
    peak_abs_error,
    run_case,
    would_overload_flag,
)


def test_fold_stays_in_lambda_range():
    lam = DEFAULT_LAM_V
    x = gen_gearbox_startup(sr=16000, duration_s=0.4, lam=lam)
    y = fold_capture(x, lam)
    assert np.all(y >= -lam - 1e-12)
    assert np.all(y < lam + 1e-12)


def test_overload_flag_when_peak_exceeds_lam():
    lam = DEFAULT_LAM_V
    x = gen_impact_transient(sr=16000, duration_s=0.5, lam=lam, peak_amp=8.0)
    assert np.max(np.abs(x)) > lam
    assert would_overload_flag(x, lam) is True
    quiet = 0.1 * lam * np.sin(np.linspace(0, 10, 500))
    assert would_overload_flag(quiet, lam) is False


def test_gearbox_or_impact_fold_beats_clip(tmp_path):
    """At least one case: fold SNR ≥ clip+5 dB and peak_error_fold < peak_error_clip."""
    lam = DEFAULT_LAM_V
    sr = 51200
    cases = [
        ("gearbox_startup", gen_gearbox_startup(sr=sr, duration_s=1.0, lam=lam)),
        ("impact_transient", gen_impact_transient(sr=sr, duration_s=1.0, lam=lam)),
    ]
    wins = []
    for name, x in cases:
        assert max_sample_jump(x) < lam, f"{name}: max_dx should be < λ for Itoh"
        clipped = hard_clip(x, lam)
        folded = fold_capture(x, lam)
        recovered = recover_itoh(folded, lam, anchor=x)
        snr_c = snr_db(x, clipped)
        snr_f = snr_db(x, recovered)
        pe_c = peak_abs_error(x, clipped)
        pe_f = peak_abs_error(x, recovered)
        if snr_f >= snr_c + 5.0 and pe_f < pe_c:
            wins.append(name)
        run_case(name, x, sr, lam, tmp_path)
    assert wins, "expected ≥1 gearbox/impact case where fold beats clip by ≥5 dB"


def test_generators_exceed_lambda():
    lam = DEFAULT_LAM_V
    g = gen_gearbox_startup(sr=16000, duration_s=0.5, lam=lam)
    i = gen_impact_transient(sr=16000, duration_s=0.5, lam=lam)
    assert np.max(np.abs(g)) > lam
    assert np.max(np.abs(i)) > lam
