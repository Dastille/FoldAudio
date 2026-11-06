"""Synthetic checks for the K003 N15_M01 phase scatter rules
(prereg-2026-11-06-k003-phase.md, NOTES #8k). No real K003 numbers."""

from __future__ import annotations

import math

import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

pytest.importorskip("scipy")


def _rec(mu_deg: float, *, ref_db: float = 28.0, r: float = 0.9) -> ps.PhaseRecord:
    return ps.PhaseRecord(
        record=f"r{mu_deg}",
        condition="x",
        meas=1,
        n_spikes=300,
        ref_db=ref_db,
        ref_valid=ref_db >= ps.REF_MIN_DB,
        depth=0.01,
        r=r,
        mu=math.radians(mu_deg),
        p=1e-9,
        null_r99=0.05,
    )


def test_k003_members_pinned():
    assert "K003" in pb.EXTRA_BEARINGS
    assert pb.EXTRA_BEARINGS["K003"][1] == "08b61792e1058dc47dd21071666bca2c"
    assert pb.K003_PHASE_MEASUREMENTS == tuple(range(1, 11))
    assert pb.K003_PHASE_CONDITIONS == ("N15_M01_F10", "N09_M07_F10")
    for c in pb.K003_PHASE_CONDITIONS:
        for m in pb.K003_PHASE_MEASUREMENTS:
            assert pb.member("K003", c, m) in pb.MAT_SHA256


def test_q3_locks_c3n_pass():
    m01 = [_rec(-65.0 + 2 * j) for j in range(8)]
    n09 = [_rec(-62.0 + j) for j in range(8)]
    v = ps.k003_phase_verdicts(m01, n09)
    assert v["Q3"] == "LOCKS"
    assert v["C3n"] == "PASS"
    assert "K001-record-specific" in v["reading"]
    assert v["n15_m01_r_between"] >= 0.8
    assert v["n09_r_between"] >= 0.8


def test_q3_scatters_c3n_pass():
    m01 = [_rec(a) for a in (0, 45, 90, 135, 180, -135, -90, -45)]
    n09 = [_rec(-62.0 + j) for j in range(8)]
    v = ps.k003_phase_verdicts(m01, n09)
    assert v["Q3"] == "SCATTERS"
    assert v["C3n"] == "PASS"
    assert "not unique to K001" in v["reading"]
    assert v["n15_m01_r_between"] < 0.8


def test_c3n_fail_marks_control():
    m01 = [_rec(-65.0 + 2 * j) for j in range(8)]
    n09 = [_rec(a) for a in (0, 45, 90, 135, 180, -135, -90, -45)]
    v = ps.k003_phase_verdicts(m01, n09)
    assert v["C3n"] == "FAIL"
    assert v["reading"] == "control failed"


def test_untestable_below_min_usable():
    m01 = [_rec(-65.0) for _ in range(7)]
    n09 = [_rec(-62.0) for _ in range(8)]
    v = ps.k003_phase_verdicts(m01, n09)
    assert v["Q3"] == "UNTESTABLE"
    assert v["C3n"] == "UNTESTABLE"
    assert v["reading"] == "UNTESTABLE"


def test_invalid_reference_not_usable():
    m01 = [_rec(-65.0, ref_db=5.0) for _ in range(8)]
    n09 = [_rec(-62.0) for _ in range(8)]
    v = ps.k003_phase_verdicts(m01, n09)
    assert v["n15_m01_usable"] == 0
    assert v["Q3"] == "UNTESTABLE"
