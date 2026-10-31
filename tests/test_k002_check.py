"""Synthetic checks for the K002 further-check rules (prereg-2026-10-31d-k002.md)."""

from __future__ import annotations

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps


def _bt(name: str, sig: bool) -> ps.BandTest:
    return ps.BandTest(name, 0.0, 1.0, 100, 0.5, 0.5, 1, 1e-9 if sig else 0.5)


def _probe(
    cond: str, spiky: bool, raw_db: float = 4.0, lp10_db: float = 5.0
) -> ps.RecordProbe:
    p = ps.RecordProbe(
        record=f"K002/{cond}",
        bearing="K002",
        condition=cond,
        n_spikes=50 if spiky else 0,
        fr_hz=25.0,
        spiky=spiky,
    )
    p.raw = {"headroom_db": raw_db, "kurtosis": 3.0, "line_snr_db": None}
    p.filters = {
        f: {
            "headroom_db": lp10_db,
            "silent_fail": 0,
            "cells": 12,
            "rule_correct": 12,
            "line_snr_db": None,
        }
        for f in ps.FILTERS
    }
    if spiky:
        p.bands = {k: _bt(k, False) for k in ("fr", "bpfo", "bpfi", "fe")}
        p.bands |= {f"decoy{i + 1}": _bt("d", False) for i in range(len(ps.DECOY_X))}
        p.bands["pwm16k"] = _bt("pwm16k", True)
        p.exploratory = {"mains100": _bt("m100", True)}
        p.current = {"evidence": True}
    return p


def test_k002_pinned_and_not_in_main_sweep():
    assert "K002" not in pb.BEARINGS and "K002" in pb.EXTRA_BEARINGS
    for c in pb.CONDITIONS:
        for m in pb.K002_MEASUREMENTS:
            assert pb.member("K002", c, m) in pb.MAT_SHA256


def test_spiky_electrical_all_held():
    v = ps.k002_verdicts([_probe(c, True) for c in pb.CONDITIONS for _ in range(5)])
    assert (v["K0"], v["K1"], v["K2"], v["K3"], v["K4"], v["K5"]) == (
        "HELD",
        "HELD",
        "HELD",
        "HELD",
        "HELD",
        "UNTESTABLE",
    )


def test_spike_free_bearing_falsifies_k0_and_tests_k5():
    v = ps.k002_verdicts(
        [_probe(c, False, raw_db=4.5) for c in pb.CONDITIONS for _ in range(5)]
    )
    assert v["K0"] == "FALSIFIED"
    assert {v[k] for k in ("K1", "K2", "K3", "K4")} == {"UNTESTABLE"}
    assert v["K5"] == "HELD"


def test_low_lp10_falsifies_k4():
    v = ps.k002_verdicts(
        [_probe(c, True, lp10_db=0.5) for c in pb.CONDITIONS for _ in range(5)]
    )
    assert v["K4"] == "FALSIFIED"
