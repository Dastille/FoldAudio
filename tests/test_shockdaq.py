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


def test_demo_flags_past_slew_case_and_not_good_cases(tmp_path):
    """shockdaq-demo UNREC column: good captures clear, past-limit capture flagged blind."""
    from foldcrypt.shockdaq import DEFAULT_SR

    lam, sr = DEFAULT_LAM_V, DEFAULT_SR
    good = run_case("impact_ok", gen_impact_transient(sr=sr, duration_s=1.0, lam=lam), sr, lam, tmp_path)
    assert good.snr_blind_db >= 60.0
    assert good.overload_unrecoverable is False
    bad_x = gen_impact_transient(sr=sr, duration_s=1.0, lam=lam, peak_amp=60.0)
    assert max_sample_jump(bad_x) > lam
    bad = run_case("impact_too_fast", bad_x, sr, lam, tmp_path)
    assert bad.snr_blind_db < 60.0
    assert bad.overload_unrecoverable is True
    assert bad.slip_flag is True


def test_failmap_reexports_flags():
    from foldcrypt import blind_level, failmap

    assert failmap.slip_flag is blind_level.slip_flag
    assert failmap.edge_flag is blind_level.edge_flag


def test_rail_column_off_on_good_cases_on_for_long_fold_step(tmp_path):
    """RAIL: ideal fold never sits at the ADC rail; a +1 % long fold step does
    (bounded accuracy), while UNREC stays off because the unwrap still holds."""
    from foldcrypt.failmap import NonIdeal, nonideal_fold
    from foldcrypt.shockdaq import DEFAULT_SR, format_shockdaq_table

    lam, sr = DEFAULT_LAM_V, DEFAULT_SR
    x = gen_gearbox_startup(sr=sr, duration_s=1.0, lam=lam)
    good = run_case("gearbox_ok", x, sr, lam, tmp_path)
    assert good.rail_hits == 0 and good.rail_clipped is False
    assert good.capture_status == "RECOVERED"
    imp = run_case("impact_ok", gen_impact_transient(sr=sr, duration_s=1.0, lam=lam), sr, lam, tmp_path)
    assert imp.rail_clipped is False

    ni = NonIdeal("gain +1.0%", gain_err=0.01)
    bad = run_case("gearbox_fold_long", x, sr, lam, tmp_path,
                   fold_fn=lambda v, l: nonideal_fold(v, l, ni), front_end=ni.name)
    assert bad.rail_hits > 0 and bad.rail_clipped is True
    assert bad.overload_unrecoverable is False          # not an unwrap failure
    assert bad.capture_status == "BOUNDED_ACCURACY"
    assert bad.snr_blind_db < 60.0                       # degraded …
    assert bad.peak_error_fold < 0.03 * bad.peak_orig    # … but bounded (≈ 2λg per wrap)
    assert bad.snr_fold_db > bad.snr_clip_db + 5.0       # still beats the silent clip

    table = format_shockdaq_table([good, bad])
    assert "RAIL" in table.splitlines()[0]
    assert table.splitlines()[2].rstrip().endswith("no")
    assert table.splitlines()[3].rstrip().endswith(str(bad.rail_hits))


def test_rail_hits_helper_matches_mask_and_failmap_reexport():
    from foldcrypt import blind_level, failmap

    lam = DEFAULT_LAM_V
    y = np.array([0.0, lam - 1e-12, -lam, 0.5 * lam, -0.999 * lam])
    assert blind_level.rail_hits(y, lam) == int(blind_level.rail_mask(y, lam).sum()) == 2
    assert failmap.rail_hits is blind_level.rail_hits
    assert blind_level.rail_hits(fold_capture(gen_impact_transient(sr=16000, duration_s=0.3, lam=lam), lam), lam) == 0


def test_demo_rows_include_rail_case(tmp_path):
    from foldcrypt.shockdaq import run_shockdaq_demo

    rows = {r.name: r for r in run_shockdaq_demo(tmp_path)}
    for name in ("gearbox_startup", "impact_transient", "impact_too_fast"):
        assert rows[name].rail_clipped is False
    assert rows["gearbox_fold_long"].rail_clipped is True
    assert rows["gearbox_fold_long"].overload_unrecoverable is False
    assert rows["impact_too_fast"].capture_status == "UNRECOVERABLE"
    import json
    meta = json.loads((tmp_path / "metrics.json").read_text())
    assert {c["name"]: c["capture_status"] for c in meta["cases"]}["gearbox_fold_long"] == "BOUNDED_ACCURACY"
