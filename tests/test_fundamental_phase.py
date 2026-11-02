"""Synthetic checks for the motor-fundamental reference split
(prereg-2026-11-02-n15m01-fundamental.md, NOTES #8k)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

pytest.importorskip("scipy")

ROOT = Path(__file__).resolve().parents[1]
SR = pb.SR
DUR_S = 4.0


def _signals(f_el: float, el0: float, rng, *, fund: float, n_spk: int = 200):
    """Phase currents whose amplitude carries a 1 % 100 Hz supply modulation and
    a ``fund`` modulation locked to the electrical angle (an f_el line in
    |i_s|; a DC sensor offset would not do, ``current_magnitude`` removes the
    mean), plus vibration spikes placed at supply phase −60° ± 20°."""
    t = np.arange(int(DUR_S * SR)) / SR
    sup = 2 * math.pi * 100.0 * t
    th = 2 * math.pi * f_el * t + el0
    amp = 1.0 + 0.01 * np.cos(sup) + fund * np.cos(th)
    i1 = amp * np.cos(th) + 1e-3 * rng.standard_normal(len(t))
    i2 = amp * np.cos(th - 2 * math.pi / 3) + 1e-3 * rng.standard_normal(len(t))
    x = 0.01 * rng.standard_normal(len(t))
    cycles = rng.choice(int(DUR_S * 100) - 40, size=n_spk, replace=False) + 20
    ph = math.radians(-60.0) + math.radians(20.0) * rng.standard_normal(n_spk)
    idx = np.round((cycles + ph / (2 * math.pi)) / 100.0 * SR).astype(int)
    x[idx] = 1.0
    return x, i1, i2


def test_fund_members_pinned_and_fresh():
    used = set(pb.K002_MEASUREMENTS)
    assert set(pb.FUND_MEASUREMENTS).isdisjoint(used)
    assert len(pb.FUND_MEASUREMENTS) == 15
    for c in pb.FUND_CONDITIONS:
        assert c in pb.CONDITIONS
        for m in pb.FUND_MEASUREMENTS:
            assert pb.member("K002", c, m) in pb.MAT_SHA256


def test_electrical_angle_frequency():
    rng = np.random.default_rng(1)
    _x, i1, i2 = _signals(99.97, 0.3, rng, fund=0.0, n_spk=20)
    _th, f_el = ps.electrical_angle(i1, i2)
    assert f_el == pytest.approx(99.97, abs=0.01)


def test_fundamental_split_share():
    th = np.linspace(0, 400 * math.pi, 64_000)
    r = 2 * np.cos(th + 0.4)
    _fit, res, share = ps.fundamental_split(r, th)
    assert share == pytest.approx(1.0, abs=1e-9)
    assert np.max(np.abs(res)) < 1e-9
    _fit, _res, share0 = ps.fundamental_split(np.zeros_like(th), th)
    assert share0 == 0.0


def test_offset_fundamental_scatters_original_residual_recovers():
    """The case H_fund describes: an f_el line from a current offset dominates
    the band; the original reference scatters across records, the residual
    reference recovers the supply phase."""
    rng = np.random.default_rng(7)
    recs = []
    for j in range(8):
        x, i1, i2 = _signals(99.97, 2 * math.pi * j / 8, rng, fund=0.03)
        f = ps.fund_from_signals(f"s{j}", "N15_M01_F10", 6 + j, x, i1, i2, rng=rng)
        assert f is not None
        recs.append(f)
    assert min(f.share for f in recs) > 0.5
    rb_o = ps.between_stats([f.orig for f in recs])[0]
    rb_r, mu_r, _ = ps.between_stats([f.resid for f in recs])
    assert rb_o < 0.5
    assert rb_r > 0.9
    assert ps.circ_dist_deg(math.degrees(mu_r), -60.0) < 25.0


def test_supply_only_collinearity_named_limit():
    """Named limit (prereg amendment A): with no f_el component at all, the
    share is still high at 1500 rpm because cos/sin θ_el at 99.97 Hz and the
    100 Hz supply line drift only ~0.12 cycle in 4 s. The residual still
    carries the supply phase."""
    rng = np.random.default_rng(11)
    x, i1, i2 = _signals(99.97, 1.0, rng, fund=0.0)
    f = ps.fund_from_signals("sup", "N15_M01_F10", 6, x, i1, i2, rng=rng)
    assert f is not None
    assert f.share > 0.5
    assert ps.circ_dist_deg(math.degrees(f.resid.mu), -60.0) < 30.0
    assert ps.circ_dist_deg(math.degrees(f.orig.mu), -60.0) < 10.0


def test_out_of_band_fundamental_leaves_reference_alone():
    rng = np.random.default_rng(3)
    x, i1, i2 = _signals(59.98, 0.5, rng, fund=0.03)
    f = ps.fund_from_signals("n09", "N09_M07_F10", 6, x, i1, i2, rng=rng)
    assert f is not None
    assert f.share < 0.05
    assert ps.circ_dist_deg(math.degrees(f.resid.mu), math.degrees(f.orig.mu)) < 5.0


def _fr(mu_o: float, mu_r: float, share: float, n: int = 300) -> ps.FundRecord:
    def pr(mu: float) -> ps.PhaseRecord:
        rec = ps.PhaseRecord(
            record=f"r{mu}",
            condition="x",
            meas=6,
            n_spikes=n,
            ref_db=30.0,
            ref_valid=True,
            depth=0.0,
            r=0.8,
            mu=math.radians(mu),
            null_r99=0.1,
        )
        lo, hi = 0, 10_000
        rec._phase = np.full(hi, math.radians(mu))
        rec._idx = np.arange(0, hi, hi // n)[:n]
        rec._lo, rec._hi = lo, hi
        return rec

    return ps.FundRecord(orig=pr(mu_o), resid=pr(mu_r), share=share, f_el=99.97)


def test_verdicts_supported_and_rejected():
    n09 = [_fr(-63 + j, -63 + j, 0.0) for j in range(8)]
    scatter = (-150, -100, -40, 0, 30, 90, 150, -10)
    good = [_fr(a, -55 + 2 * j, 0.9) for j, a in enumerate(scatter)]
    v = ps.fund_verdicts(good, n09)
    assert (v["F0"], v["Q"], v["F1"], v["F5"]) == ("PASS", "replicated", "HELD", "PASS")
    assert v["F3"] == "HELD" and v["F4"] == "HELD"
    # constant-phase fake references: every circular shift reproduces the observed
    # R_between, so null B is not significant and F2 cannot be HELD
    assert v["F2"] == "INCONCLUSIVE" and v["n15_m01_resid_null_b_p"] > 0.5
    bad = [_fr(a, a, 0.1) for a in scatter]
    v = ps.fund_verdicts(bad, n09)
    assert v["F1"] == "FALSIFIED" and v["F2"] == "FALSIFIED"


def test_verdicts_untestable_and_control_fail():
    n09 = [_fr(-63, -63, 0.0) for _ in range(8)]
    v = ps.fund_verdicts([_fr(0, 0, 0.9) for _ in range(5)], n09)
    assert {v[k] for k in ("F0", "Q", "F1", "F2", "F3", "F4", "F5")} == {"UNTESTABLE"}
    leaky = [_fr(-63, -63, 0.3) for _ in range(8)]
    v = ps.fund_verdicts([_fr(0, -60, 0.9) for _ in range(8)], leaky)
    assert v["F0"] == "FAIL"
    assert {v[k] for k in ("F1", "F2", "F3", "F4")} == {"UNTESTABLE"}


def test_committed_metrics_match_doc():
    """Whitepaper Table 21 numbers come from the committed metrics file."""
    p = ROOT / "artifacts" / "paderborn" / "fundamental-phase-metrics.json"
    if not p.exists():
        pytest.skip("metrics not yet generated")
    v = json.loads(p.read_text())["verdicts"]
    doc = (ROOT / "docs" / "foldaudio-whitepaper.md").read_text()
    assert "**Table 21.**" in doc
    for key in ("n15_m01_orig_r_between", "n15_m01_resid_r_between"):
        assert f"{v[key]:.3f}" in doc
