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


# --- held-out confirmation rules (prereg-2026-10-26-heldout.md) -------------


def _bt(name: str, sig: bool) -> ps.BandTest:
    return ps.BandTest(
        name, 1.0, 2.0, 50, 0.9 if sig else 0.1, 1.5, 1, 1e-9 if sig else 0.5
    )


def _fake(
    cond: str,
    *,
    m100=True,
    pwm=True,
    fe=False,
    mech=False,
    head=5.0,
    line_drop=0.0,
    silent=0,
    bearing="KI04",
) -> ps.RecordProbe:
    p = ps.RecordProbe(
        record=f"{bearing}/{cond}",
        bearing=bearing,
        condition=cond,
        n_spikes=50,
        fr_hz=ps.shaft_hz(cond),
        spiky=True,
    )
    p.bands = {
        k: _bt(k, False)
        for k in (
            "pwm16k",
            "fr",
            "bpfo",
            "bpfi",
            "decoy1",
            "decoy2",
            "decoy3",
            "fe",
            "6fe",
        )
    }
    p.bands["pwm16k"] = _bt("pwm16k", pwm)
    p.bands["fe"] = _bt("fe", fe)
    p.bands["bpfi"] = _bt("bpfi", mech)
    p.exploratory = {"mains100": _bt("mains100", m100)}
    p.current = {"evidence": False}
    p.raw = {"line_snr_db": 20.0}
    p.filters = {
        f: {
            "headroom_db": head,
            "silent_fail": silent,
            "cells": 6,
            "rule_correct": 6,
            "line_snr_db": 20.0 - line_drop,
        }
        for f in ps.FILTERS
    }
    return p


def _set(**kw) -> list[ps.RecordProbe]:
    return [_fake(c, **kw) for c in ("N15_M07_F10", "N09_M07_F10") * 4]


def test_heldout_all_held_on_clean_pattern():
    v = ps.heldout_verdicts(_set())
    assert (v["R1"], v["R1b"], v["R2"], v["R3"], v["R4"]) == ("HELD",) * 5
    assert v["spiky_records"] == 8 and v["n09_spiky"] == 4


def test_heldout_rules_fail_when_the_pattern_breaks():
    v = ps.heldout_verdicts(_set(m100=False, pwm=False, mech=True))
    assert (v["R1"], v["R2"], v["R3"]) == ("FALSIFIED",) * 3
    # motor band locked at 900 rpm -> supply-vs-motor reading falsified
    assert ps.heldout_verdicts(_set(fe=True))["R1b"] == "FALSIFIED"
    # one lost fault line or one silent failure falsifies R4 even with headroom
    lost = _set()
    lost[0].filters["LP10"]["line_snr_db"] = 16.9
    assert ps.heldout_verdicts(lost)["R4"] == "FALSIFIED"
    assert ps.heldout_verdicts(_set(silent=1))["R4"] == "FALSIFIED"
    assert ps.heldout_verdicts(_set(head=2.9))["R4"] == "FALSIFIED"
    # 7 of 8 with headroom is the bar; 6 of 8 is inconclusive
    probes = _set()
    probes[0].filters["LP10"]["headroom_db"] = 1.0
    assert ps.heldout_verdicts(probes)["R4"] == "HELD"
    probes[1].filters["LP10"]["headroom_db"] = 1.0
    assert ps.heldout_verdicts(probes)["R4"] == "INCONCLUSIVE"
    # too few spiky 900 rpm records -> R1b untestable
    few = [_fake("N15_M07_F10") for _ in range(6)] + [_fake("N09_M07_F10")] * 3
    assert ps.heldout_verdicts(few)["R1b"] == "UNTESTABLE"
    assert ps.heldout_verdicts([])["R1"] == "UNTESTABLE"


def test_heldout_members_are_pinned_and_distinct():
    names = [
        pb.member(b, c, m)
        for b in pb.BEARINGS
        for c in pb.CONDITIONS
        for m in pb.HELDOUT_MEASUREMENTS
    ]
    assert len(names) == 48 and pb.member("K001", "N15_M07_F10", 3).endswith(
        "_K001_3.mat"
    )
    assert all(n in pb.MAT_SHA256 for n in names)
    assert len(set(pb.MAT_SHA256.values())) == len(pb.MAT_SHA256) == 60


def test_heldout_doc_numbers_match_committed_metrics():
    """Table 15 / held-out section numbers are recomputed from the committed
    heldout-metrics.json (no data cache)."""
    m = json.loads((ROOT / "artifacts/paderborn/heldout-metrics.json").read_text())
    v = m["verdicts"]
    assert (v["R1"], v["R1b"], v["R2"], v["R3"], v["R4"]) == (
        "HELD",
        "HELD",
        "HELD",
        "HELD",
        "INCONCLUSIVE",
    )
    assert (v["spiky_records"], v["mains100_locked"], v["pwm16k_locked"]) == (
        32,
        32,
        30,
    )
    assert (
        v["h2_evidence"],
        v["n09_spiky"],
        v["n09_mains100_locked"],
        v["n09_fe_locked"],
    ) == (3, 8, 8, 1)
    f = v["filters"]
    assert (
        f["LP10"]["headroom_ok"],
        f["LP10"]["lines_lost"],
        f["LP10"]["silent_fail"],
    ) == (27, [], 0)
    assert f["LP5"]["lines_lost"] == [
        "KI04/N15_M07_F04_KI04_2.mat",
        "KI04/N15_M07_F04_KI04_3.mat",
    ]
    recs = m["records"]
    spiky = [r for r in recs if r["spiky"]]
    lined = [r for r in recs if r["raw_line_snr_db"] is not None]
    ka = [r for r in recs if r["record"].startswith("KA04")]

    def rng(vals, sign=False):
        if sign:
            return f"{min(vals):+.2f} to {max(vals):+.2f} dB".replace("-", "−")
        return f"{min(vals):.2f}–{max(vals):.2f} dB"

    lp10 = rng([r["lp10_headroom_db"] for r in spiky])
    lines = rng([r["lp10_line_snr_db"] - r["raw_line_snr_db"] for r in lined], True)
    ka_raw = rng([r["raw_headroom_db"] for r in ka])
    cells = f"{sum(r['lp10_recovered'] for r in spiky)}/{sum(r['lp10_cells'] for r in spiky)}"
    r100 = [r["mains100_r"] for r in spiky]
    for name in ("docs/shockdaq-paderborn.md", "docs/foldaudio-whitepaper.md"):
        doc = (ROOT / name).read_text(encoding="utf-8")
        for s in (lp10, lines, ka_raw, cells, f"{min(r100):.2f}–{max(r100):.2f}"):
            assert s in doc, (name, s)
    assert sum(r["raw_headroom_db"] < 3.0 for r in ka) == 5
    assert rng([r["raw_headroom_db"] for r in spiky], True) in (
        ROOT / "docs/shockdaq-paderborn.md"
    ).read_text(encoding="utf-8")


def test_cached_heldout_records_match_committed_metrics():
    """Re-probe two held-out records (one R2 miss, one R3 hit) and compare with
    the committed JSON. Needs the held-out files in the Paderborn cache."""
    _need_cache()
    import os

    try:
        for b, c, k in (("KI04", "N15_M01_F10", 2), ("K001", "N09_M07_F10", 3)):
            pb.fetch(b, c, download=False, meas=k)
    except FileNotFoundError:
        if os.environ.get("FOLDCRYPT_REQUIRE_PADERBORN") == "1":
            pytest.fail("held-out Paderborn files not cached")
        pytest.skip("held-out Paderborn files not cached")
    m = json.loads((ROOT / "artifacts/paderborn/heldout-metrics.json").read_text())
    by = {r["record"]: r for r in m["records"]}
    for b, c, k in (("KI04", "N15_M01_F10", 2), ("K001", "N09_M07_F10", 3)):
        p = ps.probe_record(b, c, meas=k)
        r = by[p.record]
        assert r["spikes"] == p.n_spikes
        assert r["pwm16k_p"] == pytest.approx(p.bands["pwm16k"].p, rel=1e-9)
        assert r["h2_evidence"] == p.h2_evidence
        assert r["lp10_headroom_db"] == pytest.approx(
            p.filters["LP10"]["headroom_db"], abs=1e-9
        )
    assert by["KI04/N15_M01_F10_KI04_2.mat"]["pwm16k_p"] > 1e-3
    assert by["K001/N09_M07_F10_K001_3.mat"]["h2_evidence"] is True
