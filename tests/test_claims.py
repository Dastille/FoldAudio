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
    """v1.4 all-cell figure (101 of 113, all accurate; kept in the v1.5 changelog)."""
    ro = claims.rail_on_recovered("combo-mild")
    assert (
        ro["recovered"],
        ro["rail_on_recovered"],
        ro["rail_on_recovered_and_accurate"],
    ) == (113, 101, 101)


# --- overloaded-only counts (whitepaper v1.5) ------------------------------
# A cell is overloaded iff the input the fold saw reached λ. In-range cells are
# recovered trivially and are excluded from recovery/agreement/accuracy counts.


def test_v1_5_failmap_overloaded_tables_3_4():
    """Table 4: 275 of 280 overloaded; 109 / 166; rule 275/275; seed 7 all 56."""
    fm = claims.failmap_overloaded()
    s7, all5 = fm["seed7"], fm["seeds7_11"]
    assert (s7["cells"], s7["overloaded"], s7["recovered"], s7["failed"]) == (
        56,
        56,
        23,
        33,
    )
    assert s7["rule_agrees"] == 56 and s7["edge_on_recovered"] == 1
    assert (all5["cells"], all5["overloaded"], all5["recovered"], all5["failed"]) == (
        280,
        275,
        109,
        166,
    )
    assert all5["rule_agrees"] == 275 and all5["failed_overloaded"] == 166
    assert (all5["flagged"], all5["slip"], all5["edge"]) == (166, 157, 166)
    assert (all5["slip_false_alarms"], all5["edge_on_recovered"]) == (0, 7)
    assert all5["in_range_recovered"] == 5
    peaks = [pk for *_, pk in fm["in_range_cells"]]
    assert len(peaks) == 5 and all(a == 6.0 for a, *_ in fm["in_range_cells"])
    assert (round(min(peaks), 2), round(max(peaks), 2)) == (4.94, 4.99)


def test_v1_5_quant_overloaded():
    """Table 5 seed 7 all overloaded; failmap.md 5-seed bit-depth check."""
    q = claims.quant_overloaded()
    assert q["seed7_overloaded"] == 56
    got = {
        b: (r["rule_agrees"], r["rule_agrees_overloaded"], r["overloaded"], r["silent"])
        for b, r in q["five_seed"].items()
    }
    assert got == {
        3: (273, 268, 275, 0),
        4: (279, 274, 275, 0),
        6: (279, 274, 275, 0),
        8: (280, 275, 275, 0),
        12: (280, 275, 275, 0),
        16: (280, 275, 275, 0),
        24: (280, 275, 275, 0),
    }


# Whitepaper Table 6 (overloaded cells): ovl, rec, fail, rule, clean, derated,
# flagged, silent, slipFA, edge-on-ok, accurate, unflagged>1 %.
TABLE6 = {
    "ideal": (275, 109, 166, 275, 275, 275, 166, 0, 0, 7, 109, 0),
    "noise 60 dB": (275, 109, 166, 275, 275, 275, 166, 0, 0, 7, 109, 0),
    "noise 40 dB": (276, 109, 167, 276, 275, 276, 167, 0, 0, 6, 109, 0),
    "noise 30 dB": (276, 109, 167, 276, 275, 276, 167, 0, 0, 6, 109, 0),
    "noise 20 dB": (278, 111, 167, 278, 277, 278, 167, 0, 0, 11, 111, 0),
    "noise 15 dB": (278, 109, 169, 278, 275, 278, 169, 0, 0, 15, 109, 0),
    "noise 10 dB": (279, 99, 180, 279, 265, 279, 180, 0, 0, 13, 99, 0),
    "noise 5 dB": (280, 76, 204, 280, 242, 280, 204, 0, 0, 4, 76, 0),
    "noise 0 dB": (280, 53, 227, 280, 219, 280, 227, 0, 0, 11, 53, 0),
    "gain -5.0%": (275, 109, 166, 275, 275, 268, 166, 0, 0, 14, 0, 95),
    "gain -1.0%": (275, 109, 166, 275, 275, 272, 166, 0, 0, 7, 16, 86),
    "gain +0.1%": (275, 109, 166, 275, 275, 274, 166, 0, 0, 7, 109, 0),
    "gain +1.0%": (275, 109, 166, 275, 275, 272, 166, 0, 0, 7, 22, 80),
    "gain +5.0%": (275, 109, 166, 275, 275, 268, 166, 0, 0, 7, 2, 100),
    "thresh -10%": (275, 109, 166, 275, 275, 268, 166, 0, 0, 12, 1, 96),
    "thresh -2%": (275, 109, 166, 275, 275, 272, 166, 0, 0, 7, 59, 47),
    "thresh +2%": (275, 109, 166, 275, 275, 272, 166, 0, 0, 7, 69, 35),
    "thresh +10%": (275, 109, 166, 275, 275, 268, 166, 0, 0, 8, 0, 101),
    "offset +2%": (275, 109, 166, 275, 275, 272, 166, 0, 0, 7, 59, 46),
    "offset +10%": (275, 109, 166, 275, 275, 268, 166, 0, 0, 7, 0, 102),
    "inl 1%": (275, 106, 169, 272, 272, 275, 169, 0, 0, 6, 106, 0),
    "inl 2%": (275, 106, 169, 272, 272, 274, 169, 0, 0, 7, 40, 59),
    "inl 5%": (275, 105, 170, 271, 271, 261, 170, 0, 0, 13, 15, 79),
    "combo-mild": (275, 108, 167, 274, 274, 274, 167, 0, 0, 6, 108, 0),
    "combo-bad": (276, 108, 168, 275, 274, 274, 168, 0, 0, 7, 40, 61),
}
T6_KEYS = (
    "overloaded",
    "recovered",
    "failed",
    "rule",
    "clean",
    "derated",
    "flagged",
    "silent",
    "slip_fa",
    "edge_on_ok",
    "accurate",
    "unflagged",
)


def test_v1_5_table6_overloaded():
    nio = claims.nonideal_overloaded()
    assert list(nio) == list(TABLE6)
    for name, want in TABLE6.items():
        assert tuple(nio[name][k] for k in T6_KEYS) == want, name
        assert (
            nio[name]["failed"] == nio[name]["failed_all"]
        )  # failures always overload


def test_v1_5_section_6_5_totals_and_in_range_notes():
    nio = claims.nonideal_overloaded()
    non = [r for n, r in nio.items() if n != "ideal"]
    assert sum(r["overloaded"] for r in non) == 6623
    assert sum(r["cells"] for r in non) == 6720
    assert sum(r["plain_false_ok"] for r in non) == 12
    assert sum(r["derated_false_ok"] for r in non) == 0
    assert sum(r["derated_false_no"] for r in non) == 69
    inl_combo = [r for n, r in nio.items() if n.startswith(("inl", "combo"))]
    assert sum(r["overloaded"] for r in inl_combo) == 1376
    assert sum(r["n_aware_false_ok"] for r in inl_combo) == 12
    assert sum(r["combined_false_ok"] for r in inl_combo) == 0
    assert sum(r["combined_false_no"] - r["n_aware_false_no"] for r in inl_combo) == 19
    # Table 6 note: unflagged >1 % in-range cells
    for n in ("inl 1%", "inl 2%", "inl 5%", "thresh +10%"):
        assert nio[n]["in_range"] == 5 and nio[n]["in_range_unflagged"] == 5, n


def test_v1_5_table7_max_error_on_overloaded():
    nio = claims.nonideal_overloaded()

    def pct(n):
        return r1(100 * nio[n]["max_err_frac"])

    def volts(n):
        return round(nio[n]["max_err_V"], 2)

    assert (volts("gain -5.0%"), pct("gain -5.0%")) == (2.00, 9.9)
    assert (volts("gain -1.0%"), pct("gain -1.0%")) == (0.40, 2.0)
    assert (volts("gain +1.0%"), pct("gain +1.0%")) == (0.30, 1.8)
    assert (volts("gain +5.0%"), pct("gain +5.0%")) == (1.50, 9.1)
    assert sorted((pct("thresh -2%"), pct("thresh +2%"))) == [1.7, 1.8]
    assert sorted((pct("thresh -10%"), pct("thresh +10%"))) == [9.8, 9.9]
    assert volts("thresh +2%") == 0.10 and volts("thresh +10%") == 0.50
    assert (pct("offset +2%"), pct("offset +10%")) == (1.8, 9.7)
    assert (pct("inl 1%"), pct("inl 2%"), pct("inl 5%")) == (1.0, 2.0, 5.0)
    assert (volts("inl 1%"), volts("inl 2%"), volts("inl 5%")) == (0.05, 0.10, 0.25)
    assert (volts("combo-mild"), pct("combo-mild")) == (0.05, 0.9)
    assert (volts("combo-bad"), pct("combo-bad")) == (0.20, 1.9)


def test_v1_5_noise_k_table_overloaded():
    """§4.4 / failmap.md k table: agreement over the 2,497 overloaded noise cells."""
    nf = claims.noise_fit_overloaded()
    assert nf["cells"] == 2497
    got = {
        k: (r["agrees"], r["false_ok"], r["false_no"]) for k, r in nf["rows"].items()
    }
    assert got == {
        0.0: (2378, 119, 0),
        3.0: (2458, 12, 27),
        4.0: (2449, 4, 44),
        4.75: (2416, 0, 81),
        5.0: (2412, 0, 85),
    }


TABLE9 = {  # overloaded, accurate b→a, unflagged b→a, invisible b→a
    "ideal": (275, (109, 109), (0, 0), (0, 0)),
    "gain -5.0%": (275, (0, 84), (95, 20), (75, 0)),
    "gain -1.0%": (275, (16, 109), (86, 0), (68, 0)),
    "gain +0.1%": (275, (109, 109), (0, 0), (0, 0)),
    "gain +1.0%": (275, (22, 58), (80, 47), (5, 0)),
    "gain +5.0%": (275, (2, 0), (100, 102), (0, 0)),
    "inl 1%": (275, (106, 109), (0, 0), (0, 0)),
    "inl 2%": (275, (40, 109), (59, 0), (59, 0)),
    "inl 5%": (275, (15, 109), (79, 0), (79, 0)),
    "combo-mild": (275, (108, 109), (0, 0), (0, 0)),
    "combo-bad": (276, (40, 35), (61, 67), (2, 0)),
}


def test_v1_5_table9_calibration_overloaded():
    rows = claims.calibration_overloaded()
    assert list(rows) == list(TABLE9)
    for name, (ovl, acc, unfl, inv) in TABLE9.items():
        r = rows[name]
        assert (r["overloaded"], r["accurate"], r["unflagged"], r["invisible"]) == (
            ovl,
            acc,
            unfl,
            inv,
        ), name
        assert r["silent_after"] == 0 and r["slip_fa_after"] == 0
    assert sum(r["invisible"][0] for r in rows.values()) == 288
    assert sum(r["in_range_invisible_before"] for r in rows.values()) == 16


def test_v1_5_rail_check_overloaded():
    """§7.4: 99 of 108 recovered overloaded combo-mild cells, all accurate."""
    ro = claims.rail_on_recovered("combo-mild")
    assert ro["recovered_overloaded"] == 108
    assert ro["rail_on_recovered_overloaded"] == 99
    assert ro["rail_on_recovered_overloaded_and_accurate"] == 99


def test_v1_5_cwru_cells_all_overloaded():
    """Table 10: λ = r · record peak with every r < 1 → 120/120 overloaded."""
    from foldcrypt.realdata import RATIOS

    assert claims.cwru_all_overloaded() and len(RATIOS) == 6
