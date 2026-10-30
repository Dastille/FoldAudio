"""Checks for the K001 own spike-free level test (prereg-2026-10-30-k001-spike-free.md)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

ROOT = Path(__file__).resolve().parents[1]
REQUIRE_ENV = "FOLDCRYPT_REQUIRE_PADERBORN"


def _tone(n: int = 20_000) -> np.ndarray:
    t = np.arange(n) / pb.SR
    return np.sin(2 * np.pi * 500.0 * t) + 0.3 * np.sin(2 * np.pi * 1300.0 * t)


def test_despike_removes_isolated_spikes_and_keeps_input():
    x = _tone()
    y, pos = ps.inject_spikes(x, 50, seed=1)
    before = y.copy()
    d = ps.despike(y)
    assert np.array_equal(y, before)
    assert d.converged and d.n_modified == 50 and d.passes == 1
    assert len(ps.spike_indices(d.y)) == 0
    assert np.max(np.abs(d.y - x)) < 0.05


def test_despike_is_noop_without_spikes():
    x = _tone()
    d = ps.despike(x)
    assert (d.n_modified, d.passes, d.converged) == (0, 0, True)
    assert np.array_equal(d.y, x)


def test_despike_cannot_fix_alternating_burst():
    """The failure seen on real K001 records (documented, not fixed): while a larger
    feature elsewhere holds the peak up, the relative bar flags the quiet sample
    inside a +/- burst but not its neighbour, and neighbour-averaging leaves a
    two-sample plateau that is no longer an isolated spike, so a ~2-unit step stays."""
    x = 0.1 * _tone(2000)
    x[500] = 4.611  # isolated spike, removed on pass 1
    x[699:701] = [1.5, 3.3]  # two-sample feature, flagged only on pass 2
    # Seven samples copied from K001/N09_M07_F10_K001_6.mat around index 142768.
    x[1000:1007] = [0.104, 2.255, 0.134, -2.286, 0.012, -1.712, -0.089]
    d = ps.despike(x)
    assert d.converged and ps.max_sample_jump(d.y) > 1.5


def test_inject_spikes_spacing_and_amplitude():
    x = _tone()
    y, pos = ps.inject_spikes(x, 300, seed=ps.D0_SEED)
    assert len(pos) == 300 and len(set(pos.tolist())) == 300
    assert np.min(np.diff(pos)) >= ps.D0_MIN_GAP
    assert pos.min() >= ps.D0_MIN_GAP and pos.max() <= len(x) - ps.D0_MIN_GAP - 1
    pk = np.max(np.abs(x))
    assert np.allclose(np.abs(y[pos]), ps.D0_AMP_X_PEAK * pk)
    with pytest.raises(ValueError):
        ps.inject_spikes(x[:100], 300)


def test_d0_row_on_synthetic_control():
    r = ps.d0_row(_tone(64_000))
    assert r["converged"] and r["abs_err_db"] <= ps.D0_TOL_DB
    assert ps.d0_verdict([r]) == "PASS"
    assert ps.d0_verdict([r | {"abs_err_db": 1.0}]) == "FAIL"
    assert ps.d0_verdict([]) == "UNTESTABLE"


def test_d1_and_d2_rules():
    bars = {r: 3.0 for r in ps.D1_MISSES}
    assert ps.d1_verdict({r: 1.0 for r in ps.D1_MISSES}, bars)["D1"] == "HELD"
    four = dict.fromkeys(ps.D1_MISSES, 1.0) | {ps.D1_MISSES[0]: 4.0}
    assert ps.d1_verdict(four, bars)["D1"] == "HELD"
    three = four | {ps.D1_MISSES[1]: 4.0}
    assert ps.d1_verdict(three, bars)["D1"] == "INCONCLUSIVE"
    two = three | {ps.D1_MISSES[2]: 4.0}
    assert ps.d1_verdict(two, bars)["D1"] == "FALSIFIED"
    assert ps.d2_verdict([(3.0, 1.0)] * 8)["D2"] == "HELD"
    assert ps.d2_verdict([(3.0, 1.0)] * 6 + [(1.0, 3.0)] * 2)["D2"] == "INCONCLUSIVE"
    assert ps.d2_verdict([(1.0, 3.0)] * 4 + [(3.0, 1.0)] * 4)["D2"] == "FALSIFIED"
    assert ps.d2_verdict([])["D2"] == "UNTESTABLE"


def test_d0_on_cached_ka04_record():
    required = os.environ.get(REQUIRE_ENV) == "1"
    try:
        import scipy  # noqa: F401

        path = pb.fetch("KA04", "N09_M07_F10", download=False, meas=9)
    except (ImportError, FileNotFoundError) as e:
        if required:
            pytest.fail(f"{REQUIRE_ENV}=1 but KA04 _9 unavailable: {e}")
        pytest.skip("scipy or KA04 _9 not cached")
    r = ps.d0_row(pb.load_vibration(path))
    assert r["converged"] and r["abs_err_db"] <= ps.D0_TOL_DB
    assert r["modified_frac"] <= ps.D0_MAX_MODIFIED_FRAC


def test_doc_numbers_match_committed_metrics():
    m = json.loads(
        (ROOT / "artifacts" / "paderborn" / "k001-spike-free-metrics.json").read_text()
    )
    d0, d1, d2, d3 = m["D0"], m["D1"], m["D2"], m["D3"]
    assert m["bars_db"] == ps.HEADROOM_BAR_DB
    assert (d0["D0"], d0["n"], d0["all_converged"]) == ("PASS", 20, True)
    assert d0["max_abs_err_db"] <= ps.D0_TOL_DB
    assert (d1["D1"], d1["ds_below_bar"]) == ("HELD", 5)
    assert (d2["D2"], d2["lp10_at_or_above_ds"], d2["n"]) == ("HELD", 40, 40)
    assert (d3["k001_ds_at_or_above_bar"], d3["k001_n"]) == (0, 20)
    assert (d3["ki04_ds_below_bar_exploratory"], d3["ki04_n"]) == (18, 20)
    lo, hi = d3["ds_range_spiky_db"]
    mod = d3["max_modified_frac_all"] * 100
    strs = [
        f"{lo:.2f} to {hi:.2f} dB".replace("-", "\u2212"),
        "18/20",
        "0/20",
        f"{mod:.1f} %",
    ]
    for name in ("docs/shockdaq-paderborn.md", "docs/foldaudio-whitepaper.md"):
        doc = (ROOT / name).read_text(encoding="utf-8")
        for s in strs:
            assert s in doc, (name, s)


# --- Burst-shaped fakes: the gate for claiming a despike method works -----------


def test_k001_burst_matches_cached_record():
    """The burst constant is a verbatim copy of real K001 samples (when cached)."""
    rec, start = ps.K001_BURST_SRC
    path = pb.default_cache() / rec
    if not path.exists():
        pytest.skip("K001 _6 not cached")
    x = pb.load_vibration(path)
    got = x[start : start + len(ps.K001_BURST)]
    assert np.allclose(got, ps.K001_BURST, atol=5e-4)


def test_k001_burst_flips_sign():
    b = np.asarray(ps.K001_BURST)
    big = b[np.abs(b) > 0.5 * np.max(np.abs(b))]
    assert len(big) >= 3 and np.any(np.diff(np.sign(big)) != 0)


def test_inject_bursts_spacing_and_shape():
    x = _tone()
    y, pos = ps.inject_bursts(x, 300, seed=ps.D0_SEED)
    w = len(ps.K001_BURST) + ps.BURST_MIN_GAP
    assert len(pos) == 300 and np.min(np.diff(pos)) >= w
    assert pos.min() >= w and pos.max() + w <= len(x)
    d = (
        y[pos[0] : pos[0] + len(ps.K001_BURST)]
        - x[pos[0] : pos[0] + len(ps.K001_BURST)]
    )
    assert np.isclose(np.max(np.abs(d)), ps.D0_AMP_X_PEAK * np.max(np.abs(x)))
    with pytest.raises(ValueError):
        ps.inject_bursts(x[:500], 300)


def test_single_sample_fakes_are_insufficient_negative_control():
    """Negative control: neighbour-average despike PASSES clean single-sample fakes
    but FAILS real K001 burst-shaped fakes on the same record. So passing
    single-sample fakes says nothing about real spikes."""
    x = _tone(64_000)
    clean = ps.d0_row(x)
    burst = ps.d0_burst_row(x, n=100)
    assert ps.d0_verdict([clean]) == "PASS"
    assert ps.d0_verdict([burst]) == "FAIL"
    assert burst["abs_err_db"] > 10 * ps.D0_TOL_DB


def test_neighbour_average_despike_fails_burst_gate_on_ka04():
    required = os.environ.get(REQUIRE_ENV) == "1"
    try:
        import scipy  # noqa: F401

        path = pb.fetch("KA04", "N09_M07_F10", download=False, meas=9)
    except (ImportError, FileNotFoundError) as e:
        if required:
            pytest.fail(f"{REQUIRE_ENV}=1 but KA04 _9 unavailable: {e}")
        pytest.skip("scipy or KA04 _9 not cached")
    x = pb.load_vibration(path)
    assert ps.d0_verdict([ps.d0_row(x)]) == "PASS"
    burst = ps.d0_burst_row(x)
    assert ps.d0_verdict([burst]) == "FAIL"
    assert burst["abs_err_db"] > 10 * ps.D0_TOL_DB
