"""Checks for the condition-matched headroom bar (prereg-2026-10-29-headroom-bar.md)."""

from __future__ import annotations

import os

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps
from foldcrypt.foldaudio import max_sample_jump
from foldcrypt.realdata import headroom_db

REQUIRE_ENV = "FOLDCRYPT_REQUIRE_PADERBORN"


def test_bar_covers_every_condition():
    assert set(ps.HEADROOM_BAR_DB) == set(pb.CONDITIONS)


def test_fresh_ka04_controls_are_pinned():
    for c in pb.CONDITIONS:
        for m in pb.CONFIRM_MEASUREMENTS:
            assert pb.member("KA04", c, m) in pb.MAT_SHA256


def test_derive_bar_floors_the_minimum():
    assert ps.derive_bar_db([3.318, 3.991]) == 3.31
    assert ps.derive_bar_db([1.6009, 2.0]) == 1.60
    with pytest.raises(ValueError):
        ps.derive_bar_db([])


def test_b1_rules():
    bars = {"a": 2.0, "b": 2.0}
    held = [("a", 3.0)] * 4 + [("a", 1.0)] + [("b", 3.0)] * 5
    assert ps.bar_stability_verdict(held, bars)["B1"] == "HELD"
    one_bad_cond = [("a", 3.0)] * 5 + [("b", 3.0)] * 2 + [("b", 1.0)] * 3
    assert ps.bar_stability_verdict(one_bad_cond, bars)["B1"] == "INCONCLUSIVE"
    half = [("a", 3.0)] * 5 + [("b", 1.0)] * 5
    assert ps.bar_stability_verdict(half, bars)["B1"] == "FALSIFIED"
    assert ps.bar_stability_verdict([], bars)["B1"] == "UNTESTABLE"


def _probe(
    cond: str, lp10_db: float, *, spiky=True, silent=0, line=None
) -> ps.RecordProbe:
    p = ps.RecordProbe(
        record=f"K/{cond}",
        bearing="K001",
        condition=cond,
        n_spikes=20,
        fr_hz=25.0,
        spiky=spiky,
    )
    p.raw = {"headroom_db": 0.0, "kurtosis": 3.0, "line_snr_db": line}
    p.filters["LP10"] = {
        "headroom_db": lp10_db,
        "line_snr_db": None if line is None else line - 4.0,
        "cells": 6,
        "recovered": 1,
        "silent_fail": silent,
        "rule_correct": 6,
    }
    return p


def test_b2_rules():
    bars = {"x": 2.0}
    ok = [_probe("x", 2.5) for _ in range(8)]
    assert ps.bar_lp10_verdict(ok, bars)["B2"] == "HELD"
    seven = ok[:7] + [_probe("x", 1.0)]
    assert ps.bar_lp10_verdict(seven, bars)["B2"] == "HELD"
    six = ok[:6] + [_probe("x", 1.0)] * 2
    assert ps.bar_lp10_verdict(six, bars)["B2"] == "INCONCLUSIVE"
    assert (
        ps.bar_lp10_verdict(ok[:7] + [_probe("x", 2.5, silent=1)], bars)["B2"]
        == "FALSIFIED"
    )
    lost = ok + [_probe("x", 2.5, spiky=False, line=10.0)]
    r = ps.bar_lp10_verdict(lost, bars)
    assert r["B2"] == "FALSIFIED" and r["lines_lost"] == ["K/x"]
    assert ps.bar_lp10_verdict([], bars)["B2"] == "UNTESTABLE"


def test_bar_constants_match_derivation():
    """HEADROOM_BAR_DB must equal the prereg rule recomputed on cached KA04 _1.._5."""
    required = os.environ.get(REQUIRE_ENV) == "1"
    try:
        import scipy  # noqa: F401

        for c in pb.CONDITIONS:
            for m in ps.BAR_DERIVE_MEASUREMENTS:
                pb.fetch("KA04", c, download=False, meas=m)
    except (ImportError, FileNotFoundError) as e:
        if required:
            pytest.fail(f"{REQUIRE_ENV}=1 but KA04 _1.._5 unavailable: {e}")
        pytest.skip("scipy or KA04 _1.._5 not cached")
    for c in pb.CONDITIONS:
        vals = []
        for m in ps.BAR_DERIVE_MEASUREMENTS:
            x = pb.load_vibration(pb.fetch("KA04", c, download=False, meas=m))
            vals.append(headroom_db(float(np.max(np.abs(x))), max_sample_jump(x)))
        assert ps.derive_bar_db(vals) == ps.HEADROOM_BAR_DB[c]


def test_table18_doc_numbers_match_committed_metrics():
    """Table 18 / doc numbers recomputed from the committed metrics (no cache)."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    m = json.loads(
        (root / "artifacts" / "paderborn" / "headroom-bar-metrics.json").read_text()
    )
    b1, b2, recs = m["B1"], m["B2"], m["records"]
    assert m["bars_db"] == ps.HEADROOM_BAR_DB
    assert (b1["B1"], b2["B2"]) == ("HELD", "HELD")
    assert (b1["at_or_above"], b1["n"], b1["excluded_spiky"]) == (16, 20, [])
    assert (b2["lp10_at_or_above_bar"], b2["spiky_records"]) == (35, 40)
    assert b2["lp10_at_or_above_3db_descriptive"] == 39
    assert (b2["lines_testable"], b2["lines_lost"], b2["silent_fail"]) == (40, [], 0)
    assert b2["rule_all_correct"]
    spiky = [r for r in recs if r["spiky"]]
    misses = [r for r in spiky if r["lp10_headroom_db"] < r["bar_db"]]
    assert all(r["record"].startswith("K001/") for r in misses) and len(misses) == 5
    assert sum(r["lp10_recovered"] for r in spiky) == 68
    assert sum(r["lp10_cells"] for r in spiky) == 240
    ka = [r["raw_headroom_db"] for r in recs if r["record"].startswith("KA04/")]
    lp = [r["lp10_headroom_db"] for r in spiky]
    strs = [
        f"{min(ka):.2f}–{max(ka):.2f} dB",
        f"{min(lp):.2f}–{max(lp):.2f} dB",
        "16/20",
        "35/40",
        "39/40",
        "24/32",
    ]
    for name in ("docs/shockdaq-paderborn.md", "docs/foldaudio-whitepaper.md"):
        doc = (root / name).read_text(encoding="utf-8")
        for s in strs:
            assert s in doc, (name, s)


def test_retro_score_on_seen_records():
    """Exploratory 24/32 on measurements _2.._5 against the same bars (committed metrics)."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    h = json.loads(
        (root / "artifacts" / "paderborn" / "heldout-metrics.json").read_text()
    )
    spiky = [r for r in h["records"] if r["spiky"]]
    ok = sum(
        r["lp10_headroom_db"]
        >= ps.HEADROOM_BAR_DB[r["record"].split("/")[1].rsplit("_", 2)[0]]
        for r in spiky
    )
    assert (ok, len(spiky)) == (24, 32)
