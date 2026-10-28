"""Synthetic checks for the confirmatory phase rules (prereg-2026-10-28-phase-confirm.md)."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

pytest.importorskip("scipy")

SR = 64_000
N = 4 * SR + 1


def _record(target_deg: float, seed: int, phase0: float = 0.4) -> ps.PhaseRecord:
    t = np.arange(N) / SR
    mag = 1.0 + 0.02 * np.cos(2 * np.pi * 100.0 * t + phase0)
    i1 = mag * np.cos(2 * np.pi * 60.0 * t)
    i2 = mag * np.cos(2 * np.pi * 60.0 * t - 2 * np.pi / 3)
    rng = np.random.default_rng(seed)
    cyc = np.arange(20, 380, 3)
    th = math.radians(target_deg) + 0.3 * rng.uniform(-1, 1, len(cyc))
    idx = np.unique(np.round((2 * np.pi * cyc + th - phase0) / (2 * np.pi * 100.0) * SR).astype(int))
    x = 0.05 * rng.standard_normal(N)
    x[idx] = 5.0 * np.where(np.arange(len(idx)) % 2 == 0, 1.0, -1.0)
    rec = ps.phase_from_signals(f"syn{seed}", "N09_x", 6, x, i1, i2, SR, rng=np.random.default_rng(seed))
    assert rec is not None
    return rec


def test_null_a_bar_scales_with_n():
    assert ps.null_a_bar(0) == math.inf
    assert ps.null_a_bar(100) == pytest.approx(1.2 * math.sqrt(math.log(100) / 100))
    # the fixed 10-27 bar (0.2) is only reached near N = 1.44 * 116
    assert ps.null_a_bar(166) == pytest.approx(0.2, abs=0.002)


def test_circ_dist_wraps():
    assert ps.circ_dist_deg(170.0, -170.0) == pytest.approx(20.0)
    assert ps.circ_dist_deg(-65.7, -65.7) == pytest.approx(0.0)


def test_confirm_measurements_are_pinned_and_disjoint():
    assert set(pb.CONFIRM_MEASUREMENTS).isdisjoint({1, *pb.HELDOUT_MEASUREMENTS})
    for b in ("K001", "KI04"):
        for c in pb.CONDITIONS:
            for m in pb.CONFIRM_MEASUREMENTS:
                assert pb.member(b, c, m) in pb.MAT_SHA256


def test_all_held_at_target_phase():
    # J = 8 records: p_between = exp(-J R^2) < 1e-3 needs J >= 7
    recs = [_record(ps.C3_TARGET_DEG, s) for s in range(8)]
    v = ps.confirm_verdicts(recs)
    assert v["null_a_ok"]
    assert (v["C1"], v["C2"], v["C3"]) == ("HELD", "HELD", "HELD")
    assert v["c3_distance_deg"] < 10


def test_c3_falsified_at_opposite_phase():
    recs = [_record(ps.C3_TARGET_DEG + 180.0, s) for s in range(8)]
    v = ps.confirm_verdicts(recs)
    assert (v["C2"], v["C3"]) == ("HELD", "FALSIFIED")


def test_failed_null_gate_makes_all_untestable():
    recs = [_record(ps.C3_TARGET_DEG, s) for s in range(8)]
    recs[0] = replace(recs[0], null_r99=1.0)
    v = ps.confirm_verdicts(recs)
    assert not v["null_a_ok"]
    assert (v["C1"], v["C2"], v["C3"]) == ("UNTESTABLE",) * 3


def test_invalid_references_make_all_untestable():
    recs = [replace(_record(ps.C3_TARGET_DEG, s), ref_valid=False) for s in range(3)]
    v = ps.confirm_verdicts(recs)
    assert v["valid_reference"] == 0
    assert v["C1"] == "UNTESTABLE"
