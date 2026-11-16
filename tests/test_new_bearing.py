"""Synthetic checks for the new-bearing ripple-depth prediction rules
(prereg-2026-11-16-new-bearing.md). No real new-bearing numbers."""

from __future__ import annotations

import math

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

pytest.importorskip("scipy")

SR = 64_000
N = 2 * SR + 1


def _rec(mu_deg: float) -> ps.PhaseRecord:
    return ps.PhaseRecord(
        record=f"r{mu_deg}",
        condition="x",
        meas=1,
        n_spikes=300,
        ref_db=28.0,
        ref_valid=True,
        depth=0.01,
        r=0.9,
        mu=math.radians(mu_deg),
        p=1e-9,
        null_r99=0.05,
    )


LOCK = [_rec(-60.0 + 2 * j) for j in range(10)]
SCAT = [_rec(a) for a in (0, 36, 72, 108, 144, 180, -144, -108, -72, -36)]


def _q(m01, n09=LOCK):
    return ps.k003_phase_verdicts(m01, n09)


def test_new_bearings_pinned_and_never_used_before():
    assert pb.NEW_BEARINGS == ("KA01", "KA05", "KI01")
    for b in pb.NEW_BEARINGS:
        assert b in pb.EXTRA_BEARINGS and b not in pb.BEARINGS
        for c in pb.NEW_BEARING_CONDITIONS:
            for m in pb.NEW_BEARING_MEASUREMENTS:
                assert pb.member(b, c, m) in pb.MAT_SHA256
    for m in ps.NEW_BEARING_PPLUS_MEASUREMENTS:
        for c in pb.NEW_BEARING_CONDITIONS:
            assert pb.member("K001", c, m) in pb.MAT_SHA256


def test_pplus_constants_match_published():
    import json
    from pathlib import Path

    d = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "artifacts/paderborn/ref-snr-phase-metrics.json"
        ).read_text()
    )["exploratory_k001_per_condition"]
    for c, rb in ps.NEW_BEARING_PPLUS_RB.items():
        assert d[c]["r_between"] == rb


@pytest.mark.parametrize(
    ("depths", "label"),
    [([0.012, 0.011, 0.02], "SCATTER"), ([0.005, 0.006, 0.02], "LOCK")],
)
def test_predict_label_uses_median_and_strict_threshold(depths, label):
    v = ps.predict_label(depths)
    assert v["predicted"] == label
    assert v["median"] == sorted(depths)[1]


def test_predict_label_at_threshold_is_lock_and_near():
    v = ps.predict_label([ps.RIPPLE_HELDOUT_T] * 3)
    assert v["predicted"] == "LOCK" and v["near_t"]
    assert not ps.predict_label([0.02])["near_t"]
    assert ps.predict_label([math.nan])["predicted"] == "UNTESTABLE"


def test_phase_label_requires_control_and_clear_q3():
    assert ps.phase_label(_q(LOCK)) == "LOCK"
    assert ps.phase_label(_q(SCAT)) == "SCATTER"
    assert ps.phase_label(_q(LOCK, SCAT)) is None  # C3n FAIL
    assert ps.phase_label(_q(LOCK[:7])) is None  # UNTESTABLE
    assert ps.phase_label({}) is None


def test_verdict_held_falsified_untestable():
    per = {"A": _q(LOCK), "B": _q(SCAT), "C": _q(LOCK[:5])}
    v = ps.new_bearing_verdict({"A": "LOCK", "B": "SCATTER", "C": "LOCK"}, per)
    assert v["N"] == "HELD" and v["n_valid"] == 2 and v["n_match"] == 2
    assert v["per_bearing"]["C"]["match"] is None
    assert v["both_labels_predicted_among_valid"]
    assert v["chance_all_match_p"] == 0.25
    v = ps.new_bearing_verdict({"A": "LOCK", "B": "LOCK", "C": "LOCK"}, per)
    assert v["N"] == "FALSIFIED" and v["n_match"] == 1
    v = ps.new_bearing_verdict(
        {"A": "LOCK", "C": "LOCK"}, {"A": _q(LOCK), "C": _q(LOCK[:5])}
    )
    assert v["N"] == "UNTESTABLE"


def _phase_rec(target: float, k: int) -> ps.PhaseRecord:
    t = np.arange(N) / SR
    p0 = 0.4 * k
    mag = 1.0 + 0.02 * np.cos(2 * np.pi * 100.0 * t + p0)
    i1 = mag * np.cos(2 * np.pi * 60.0 * t)
    i2 = mag * np.cos(2 * np.pi * 60.0 * t - 2 * np.pi / 3)
    cyc = np.arange(15, 185)
    idx = np.unique(
        np.round((2 * np.pi * cyc + target - p0) / (2 * np.pi * 100.0) * SR).astype(int)
    )
    x = 0.05 * np.random.default_rng(k).standard_normal(N)
    x[idx] = 5.0 * np.where(np.arange(len(idx)) % 2 == 0, 1.0, -1.0)
    r = ps.phase_from_signals(f"s{k}", "N15_x", k, x, i1, i2, SR)
    assert r is not None and r.usable
    return r


def test_null_b_r99_low_for_locked_spikes():
    recs = [_phase_rec(0.3, k) for k in range(8)]
    assert ps.between_stats(recs)[0] > 0.99  # the real set locks
    r99 = ps.null_b_r99(recs)
    assert r99 < ps.R_BETWEEN_HELD  # shifted timing does not
    assert math.isnan(ps.null_b_r99([]))
