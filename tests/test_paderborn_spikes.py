import json
from pathlib import Path

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps
from tests.test_paderborn import _need_cache

ROOT = Path(__file__).resolve().parents[1]
SR = 64_000


def test_bearing_multipliers_match_6203_geometry():
    # Lessmeier et al. 2016 Table 1: 8 balls, d 6.75 mm, D 28.55 mm, 0 deg;
    # Schaeffler 6203-2Z catalogue lists 3.0531 / 4.9469 (within 0.1 %).
    assert ps.BPFO_X == pytest.approx(3.0543, abs=1e-4)
    assert ps.BPFI_X == pytest.approx(4.9457, abs=1e-4)
    assert ps.BPFO_X + ps.BPFI_X == pytest.approx(ps.N_BALLS)
    assert ps.shaft_hz("N15_M07_F10") == pytest.approx(25.0)
    assert ps.shaft_hz("N09_M07_F10") == pytest.approx(15.0)
    with pytest.raises(ValueError):
        ps.shaft_hz("X15_M07_F10")


def test_spike_indices_agree_with_isolated_spikes():
    rng = np.random.default_rng(1)
    x = 0.1 * rng.standard_normal(20_000)
    at = rng.choice(np.arange(5, 19_995), size=37, replace=False)
    x[at] += rng.choice([-3.0, 3.0], size=37)
    idx = ps.spike_indices(x)
    assert len(idx) == pb.isolated_spikes(x)
    assert set(idx) <= set(at) and len(idx) >= 30
    assert len(ps.spike_indices(np.zeros(2))) == 0


def test_band_test_detects_locking_and_not_uniform_times():
    rng = np.random.default_rng(2)
    n = 256_000
    # spikes locked to 100 Hz (every 640 samples, ±1 sample jitter) vs uniform
    locked = np.arange(300, n - 640, 640)[::3] + rng.integers(-1, 2, size=133)
    uniform = np.sort(rng.choice(n, size=133, replace=False))
    b_lock = ps.band_test("x", locked, SR, 97.0, 103.0, n / SR)
    b_unif = ps.band_test("x", uniform, SR, 97.0, 103.0, n / SR)
    assert b_lock.significant and b_lock.f_at_max == pytest.approx(100.0, abs=0.05)
    assert b_lock.r_max > 0.95
    assert not b_unif.significant and b_unif.p > 0.01
    assert b_lock.m_eff == 24  # ceil(6 Hz · 4 s)
    assert ps.band_test("x", np.zeros(0, int), SR, 1, 2, 4.0).p == 1.0


def test_current_coincidence_and_null():
    rng = np.random.default_rng(3)
    n = 50_000
    cur = [0.01 * rng.standard_normal(n), 0.01 * rng.standard_normal(n)]
    idx = np.sort(rng.choice(np.arange(10, n - 10), size=100, replace=False))
    cur[0][idx[:80] + 1] += 1.0  # 80 % of spikes have a current step next to them
    c = ps.current_coincidence(idx, cur, seed=5)
    assert c["frac"] >= 0.8 and c["null_frac"] < 0.15 and c["evidence"]
    c0 = ps.current_coincidence(idx, [0.01 * rng.standard_normal(n)] * 2, seed=5)
    assert not c0["evidence"]


def test_filters_remove_a_spike_and_reject_unknown_names():
    pytest.importorskip("scipy")
    t = np.arange(32_000) / SR
    x = np.sin(2 * np.pi * 200 * t)
    x[10_000] += 4.0
    assert len(ps.spike_indices(x)) == 1
    for name in ps.FILTERS:
        assert len(ps.spike_indices(ps.apply_filter(x, name))) == 0
    with pytest.raises(ValueError):
        ps.apply_filter(x, "LP99")


def test_envelope_line_snr_sees_periodic_impacts():
    pytest.importorskip("scipy")
    rng = np.random.default_rng(4)
    n = 4 * SR
    x = 0.05 * rng.standard_normal(n)
    ring = np.exp(-np.arange(200) / 30) * np.sin(
        2 * np.pi * 4_000 * np.arange(200) / SR
    )
    period = SR / 123.6
    for k in range(int(n / period) - 1):
        s = int(k * period)
        x[s : s + 200] += ring
    assert ps.envelope_line_snr_db(x, SR, 123.6) > 20
    assert ps.envelope_line_snr_db(0.05 * rng.standard_normal(n), SR, 123.6) < 12


def test_verdict_rules():
    def fake(h1, h2, spiky=True, line=None):
        p = ps.RecordProbe("r", "KI04", "N15_M07_F10", 50, 25.0, spiky)
        sig = ps.BandTest("s", 0, 1, 50, 0.9, 0.5, 1, 1e-9)
        no = ps.BandTest("n", 0, 1, 50, 0.01, 0.5, 1, 0.9)
        p.bands = {
            k: no
            for k in ("pwm16k", "fr", "bpfo", "bpfi", "decoy1", "decoy2", "decoy3")
        }
        p.bands["pwm16k"] = sig if h1 else no
        p.bands["bpfi"] = sig if h2 else no
        p.current = {"evidence": False}
        p.raw = {"line_snr_db": line}
        row = {
            "headroom_db": 4.0,
            "silent_fail": 0,
            "rule_correct": 6,
            "cells": 6,
            "line_snr_db": line,
        }
        p.filters = {k: dict(row) for k in ps.FILTERS}
        return p

    v = ps.verdicts([fake(True, False) for _ in range(8)])
    assert (v["H1"], v["H2"], v["H3"]) == ("HELD", "FALSIFIED", "HELD")
    v = ps.verdicts([fake(i < 4, i >= 4) for i in range(8)])
    assert (v["H1"], v["H2"]) == ("INCONCLUSIVE", "INCONCLUSIVE")
    probes = [fake(True, False, line=20.0) for _ in range(8)]
    probes[0].filters["LP10"]["line_snr_db"] = 16.9  # > 3 dB loss
    v = ps.verdicts(probes)
    assert (
        v["filters"]["LP10"]["verdict"] == "FALSIFIED" and v["H3"] == "HELD"
    )  # LP5 holds


def test_cached_spike_probe_matches_committed_metrics():
    _need_cache()
    probes = ps.run_probe()
    v = ps.verdicts(probes)
    committed = json.loads(
        (ROOT / "artifacts/paderborn/spike-probe-metrics.json").read_text()
    )
    assert committed["verdicts"] == json.loads(json.dumps(v))
    # Pre-registered verdicts (prereg-2026-10-25.md) as run on 2026-10-25.
    assert (v["H1"], v["H2"], v["H3"]) == ("HELD", "FALSIFIED", "HELD")
    assert (v["spiky_records"], v["h1_evidence"], v["h2_evidence"]) == (8, 8, 1)
    assert (v["h1a_pwm_band"], v["h1b_current"], v["h2_ignoring_decoys"]) == (8, 1, 2)
    f = v["filters"]
    assert [f[k]["verdict"] for k in ps.FILTERS] == ["HELD", "FALSIFIED", "FALSIFIED"]
    assert f["LP5"]["lines_lost"] == ["KI04/N15_M07_F04_KI04_1.mat"]
    for a, p in zip(committed["records"], probes):
        assert a["record"] == p.record and a["n_spikes"] == p.n_spikes
        if p.spiky:
            assert a["exploratory_post_hoc"]["mains100"]["significant"]
            assert a["exploratory_post_hoc"]["mod4"] == p.exploratory["mod4"]
        for name in ps.FILTERS:
            assert a["filters"][name]["headroom_db"] == pytest.approx(
                p.filters[name]["headroom_db"], abs=1e-9
            )
    # Exploratory (post hoc): every spiky record is locked to 100 Hz, no
    # equal-width HF control band is significant.
    spiky = [p for p in probes if p.spiky]
    assert all(p.exploratory["mains100"].significant for p in spiky)
    assert not any(
        p.exploratory[k].significant
        for p in spiky
        for k in ("ctl8k", "ctl12k", "ctl20k", "ctl24k")
    )


def test_doc_numbers_match_committed_probe():
    """Key ranges quoted in docs/shockdaq-paderborn.md and the whitepaper are
    recomputed from the committed spike-probe-metrics.json (no data cache)."""
    m = json.loads((ROOT / "artifacts/paderborn/spike-probe-metrics.json").read_text())
    recs = m["records"]
    spiky = [r for r in recs if r["spiky"]]
    lined = [r for r in recs if r["raw"]["line_snr_db"] is not None]
    docs = [
        (ROOT / "docs/shockdaq-paderborn.md").read_text(encoding="utf-8"),
        (ROOT / "docs/foldaudio-whitepaper.md").read_text(encoding="utf-8"),
    ]

    def sgn(v):
        return f"{v:+.2f}".replace("-", "−")

    def head(name):
        v = [r["filters"][name]["headroom_db"] for r in spiky]
        return f"{min(v):.2f}–{max(v):.2f} dB"

    def line_change(name):
        d = [r["filters"][name]["line_snr_db"] - r["raw"]["line_snr_db"] for r in lined]
        return f"{sgn(min(d))} to {sgn(max(d))} dB"

    def rec(name):
        return f"{sum(r['filters'][name]['recovered'] for r in spiky)}/48"

    m100 = [r["exploratory_post_hoc"]["mains100"]["r_max"] for r in spiky]
    pwm = [r["bands"]["pwm16k"]["r_max"] for r in spiky]
    for doc in docs:
        assert head("LP10") in doc and head("LP5") in doc
        assert rec("LP10") in doc and rec("LP5") in doc
        assert f"{min(m100):.2f}–{max(m100):.2f}" in doc
        assert line_change("LP10") in doc, line_change("LP10")
    paderborn_doc = docs[0]
    assert f"R 0.296–{max(pwm):.3f}" in paderborn_doc and min(pwm) == pytest.approx(
        0.296, abs=5e-4
    )
    v = m["verdicts"]
    assert (v["H1"], v["H2"], v["H3"]) == ("HELD", "FALSIFIED", "HELD")
