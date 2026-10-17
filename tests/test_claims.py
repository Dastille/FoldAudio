"""Whitepaper spot claims, asserted at the precision the report states them.

Each test names the section and sentence it backs. If one fails, the doc and
the code disagree: fix the doc to the real number (never tune the code to an
old number). Reproduce interactively with `python -m foldcrypt claims`.
"""

from __future__ import annotations

import pytest

from foldcrypt import claims


def r1(v: float) -> float:
    return round(float(v), 1)


@pytest.fixture(scope="module")
def noise_fit():
    return claims.noise_k_fit()  # 2,520-cell sweep, ~10 s


def test_s3_6_fallback_vs_clip_seven_captures():
    """§3.6: clip(unwrap) −11 to −16 dB vs −0.9 to +1.9 dB for the folded samples."""
    rows = claims.fallback_vs_clip()
    assert len(rows) == 7 and all(r["fallback"] for r in rows)
    cu = [r["clip_unwrap_db"] for r in rows]
    fo = [r["folded_db"] for r in rows]
    assert (round(min(cu)), round(max(cu))) == (-16, -11)
    assert (r1(min(fo)), r1(max(fo))) == (-0.9, 1.9)


def test_s3_6_fallback_vs_clip_full_seed7_grid():
    """§3.6: over all 33 failing seed-7 cells, −18 to −11 dB vs −1.0 to +8.7 dB."""
    g = claims.fallback_vs_clip_grid()
    assert g["cells"] == 33
    assert (round(g["clip_unwrap_min"]), round(g["clip_unwrap_max"])) == (-18, -11)
    assert (r1(g["folded_min"]), r1(g["folded_max"])) == (-1.0, 8.7)


def test_s3_6_event_mask_covers_168_cells():
    """§3.6: the event mask covered every |x| ≥ λ sample in 168 burst cells."""
    assert claims.mask_coverage() == {"cells": 168, "missed": 0}


def test_s4_4_noise_k_fit(noise_fit):
    """§4.4: 2,520 cells; k_min 4.75 → 5; 119 → 0 false-ok; 2,401 → 2,435 agree;
    85 conservative, all ≤ 30 dB; 3-seed fit k = 4 leaves 4 held-out false-ok."""
    nk = noise_fit
    assert nk["cells"] == 2520 and nk["k_min_safe"] == 4.75
    assert (nk["k0"]["false_ok"], nk["k0"]["agrees"]) == (119, 2401)
    assert (nk["k5"]["false_ok"], nk["k5"]["agrees"], nk["k5"]["false_no"]) == (
        0,
        2435,
        85,
    )
    assert nk["false_no_max_snr_db"] <= 30.0
    assert nk["k_three_seeds"] == 4.0 and nk["held_out_false_ok"] == 4


def test_s4_5_sigma_estimate_within_3_6_percent():
    """§4.5: quiet-window σ estimate within 3.6 % (median 2.8 %) on five records."""
    errs = claims.sigma_estimate_errors()
    assert len(errs) == 5 and r1(100 * max(errs)) == 3.6
    # docs/shockdaq-failmap.md also states the median
    assert r1(100 * sorted(errs)[2]) == 2.8


def test_s5_3_burst_peak_ratio_and_6v_row():
    """§5.3: peak |x| is 0.82–0.98 A over 280 cells; 6 V row 4.94–5.87 V, 5/40 < λ."""
    bp = claims.burst_peaks()
    assert bp["cells"] == 280
    assert (round(bp["ratio_min"], 2), round(bp["ratio_max"], 2)) == (0.82, 0.98)
    assert (round(bp["six_v_min"], 2), round(bp["six_v_max"], 2)) == (4.94, 5.87)
    assert (bp["six_v_below_lam"], bp["six_v_cells"]) == (5, 40)


def test_s6_2_mid_overload_and_dc_shift():
    """§6.2: k=0 gives −13.8 / −24.4 dB; priors pick k = +1 / −1 and hit 120 dB;
    DC shift 1.2λ with the zero-mean prior gives −4.0 dB."""
    mo = claims.mid_overload_and_dc()
    assert r1(mo["gearbox"]["naive_db"]) == -13.8
    assert r1(mo["impact"]["naive_db"]) == -24.4
    for name, k in (("gearbox", 1), ("impact", -1)):
        for prior in ("zero_mean", "quiet_window"):
            assert mo[name][prior]["k"] == k
            assert mo[name][prior]["snr_db"] == 120.0
    assert r1(mo["dc_shift_zero_mean_db"]) == -4.0


def test_s7_1_inl_leaks_4_7_percent_into_gain():
    """§7.1: without INL terms a 5 % bow appears as ĝ ≈ +4.7 %."""
    assert r1(100 * claims.inl_leak_into_gain()) == 4.7


def test_s7_4_rail_check_on_combo_mild():
    """§7.4: rail check fires on 101 of the 113 recovered combo-mild cells, all accurate."""
    assert claims.rail_on_recovered("combo-mild") == {
        "recovered": 113,
        "rail_on_recovered": 101,
        "rail_on_recovered_and_accurate": 101,
    }
