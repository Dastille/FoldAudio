"""Synthetic checks for the ripple-depth held-out rules
(prereg-2026-11-11-ripple-heldout.md). No real depth numbers."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

ROOT = Path(__file__).resolve().parents[1]
LAB = {b: v[0] for b, v in ps.SCATTER_COV_LABELS.items()}


def test_heldout_records_pinned_and_disjoint_from_labels():
    for b, meas in pb.RIPPLE_HELDOUT_MEASUREMENTS.items():
        assert not set(meas) & set(ps.SCATTER_COV_LABELS[b][2])
        for m in meas:
            assert pb.member(b, ps.SCATTER_COV_CONDITION, m) in pb.MAT_SHA256
    assert sum(len(m) for m in pb.RIPPLE_HELDOUT_MEASUREMENTS.values()) == 55


def test_train_medians_match_published():
    d = json.loads(
        (
            ROOT / "artifacts" / "paderborn" / "scatter-covariates-metrics.json"
        ).read_text()
    )
    assert d["bearing_medians"]["ripple_depth"] == ps.RIPPLE_TRAIN_MEDIANS
    lock = max(v for b, v in ps.RIPPLE_TRAIN_MEDIANS.items() if LAB[b] == "LOCK")
    scat = min(v for b, v in ps.RIPPLE_TRAIN_MEDIANS.items() if LAB[b] == "SCATTER")
    assert float(f"{(lock + scat) / 2:.2g}") == ps.RIPPLE_HELDOUT_T


@pytest.mark.parametrize("depth", [0.005, 0.0125])
def test_ripple_depth_recovers_known_modulation(depth):
    pytest.importorskip("scipy")
    sr, n = pb.SR, int(pb.SR)
    t = np.arange(n) / sr
    env = 1.0 + depth * np.cos(2 * math.pi * 100.0 * t)
    th = 2 * math.pi * 50.0 * t
    i1 = env * np.cos(th)
    i2 = env * np.cos(th - 2 * math.pi / 3)
    got = ps.ripple_depth_from_signals({"phase_current_1": i1, "phase_current_2": i2})
    assert got == pytest.approx(depth, rel=0.02)


def test_one_sided_verdict_held_and_falsified():
    pytest.importorskip("scipy")
    up = {"K001": 6.0, "K002": 1.0, "K003": 2.0, "K004": 5.0, "K005": 3.0, "K006": 4.0}
    v = ps.one_sided_verdict(up, LAB)
    assert v["verdict"] == "HELD" and v["perm_p_one_sided"] == pytest.approx(0.05)
    down = {b: -x for b, x in up.items()}
    w = ps.one_sided_verdict(down, LAB)
    assert w["verdict"] == "FALSIFIED" and w["perm_p_one_sided"] == pytest.approx(1.0)
    five = {b: x for b, x in up.items() if b != "K001"}
    assert ps.one_sided_verdict(five, LAB)["perm_p_one_sided"] == pytest.approx(0.1)
    assert (
        ps.one_sided_verdict({**up, "K001": math.nan}, LAB)["verdict"] == "UNTESTABLE"
    )


def test_threshold_verdict():
    vals = {
        "K001": 0.012,
        "K002": 0.006,
        "K003": 0.007,
        "K004": 0.013,
        "K005": 0.005,
        "K006": 0.015,
    }
    assert ps.threshold_verdict(vals, LAB)["verdict"] == "HELD"
    bad = {**vals, "K003": 0.010}
    v = ps.threshold_verdict(bad, LAB)
    assert v["verdict"] == "FALSIFIED" and v["correct"] == 5
