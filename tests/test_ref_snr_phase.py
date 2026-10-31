"""Synthetic checks for the reference-SNR split rules (prereg-2026-10-31d-k001-ref-snr.md)."""

from __future__ import annotations

import math

import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

pytest.importorskip("scipy")


def _rec(
    ref_db: float, mu_deg: float, r: float = 0.8, null_r99: float = 0.1
) -> ps.PhaseRecord:
    return ps.PhaseRecord(
        record=f"r{ref_db}_{mu_deg}",
        condition="N15_x",
        meas=11,
        n_spikes=300,
        ref_db=ref_db,
        ref_valid=ref_db >= ps.REF_MIN_DB,
        depth=0.01,
        r=r,
        mu=math.radians(mu_deg),
        null_r99=null_r99,
    )


def _tight(n: int = 8) -> list[ps.PhaseRecord]:
    return [_rec(29.0, -65.0 + 3 * j, r=0.92) for j in range(n)]


def test_ref_snr_measurements_pinned_and_disjoint():
    used = {1, *pb.HELDOUT_MEASUREMENTS, *pb.CONFIRM_MEASUREMENTS}
    assert set(pb.REF_SNR_MEASUREMENTS).isdisjoint(used)
    for b in ("K001", "KI04"):
        for c in pb.CONDITIONS:
            for m in pb.REF_SNR_MEASUREMENTS:
                assert pb.member(b, c, m) in pb.MAT_SHA256


def test_weak_reference_effect_held():
    hi = [_rec(30.0 + j, -70.0 + 4 * j, r=0.85) for j in range(6)]
    lo = [
        _rec(18.0 + j, a, r=0.4 + 0.05 * j)
        for j, a in enumerate((100, -150, 20, 140, 170))
    ]
    v = ps.ref_snr_verdicts(hi + lo, _tight())
    assert v["split_rule"] == "fixed"
    assert (v["A1"], v["A1b"], v["A2"], v["A3"]) == ("HELD", "HELD", "HELD", "HELD")


def test_scatter_independent_of_snr_falsified():
    hi = [_rec(30.0, a) for a in (100, -150, -70, 140, -60, 20)]
    lo = [_rec(20.0, a) for a in (-65, -72, -60, -68, -70)]
    v = ps.ref_snr_verdicts(hi + lo, _tight())
    assert v["A1"] == "FALSIFIED"
    assert v["A3"] == "FALSIFIED"


def test_median_fallback_then_untestable():
    k = [_rec(30.0 + j, -65.0) for j in range(8)]
    v = ps.ref_snr_verdicts(k, _tight())
    assert v["split_rule"] == "median" and v["n_low"] >= 4
    v = ps.ref_snr_verdicts(k[:5], _tight())
    assert v["A1"] == "UNTESTABLE" and v["A3"] == "UNTESTABLE"


def test_null_a_failure_blocks_everything():
    k = [_rec(30.0, -65.0) for _ in range(5)] + [
        _rec(20.0, 90.0, null_r99=0.9) for _ in range(5)
    ]
    v = ps.ref_snr_verdicts(k, _tight())
    assert not v["A0_null_a_ok"]
    assert {v[x] for x in ("A1", "A1b", "A2", "A3")} == {"UNTESTABLE"}


def test_ki04_spread_falsifies_a2():
    ki = [_rec(29.0, a) for a in (0, 90, 180, -90, 45, -135)]
    v = ps.ref_snr_verdicts(_tight(), ki)
    assert v["A2"] == "FALSIFIED"
