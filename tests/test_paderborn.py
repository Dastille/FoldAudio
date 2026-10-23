import json
import os
from pathlib import Path

import numpy as np
import pytest

from foldcrypt import paderborn as pb

REQUIRE_ENV = "FOLDCRYPT_REQUIRE_PADERBORN"
ROOT = Path(__file__).resolve().parents[1]


def _need_cache():
    """Skip unless SciPy and the 12 pinned Paderborn files are cached;
    FOLDCRYPT_REQUIRE_PADERBORN=1 (set by scripts/local_check.sh --full)
    turns a skip into a failure."""
    required = os.environ.get(REQUIRE_ENV) == "1"
    try:
        import scipy  # noqa: F401
    except ImportError:
        if required:
            pytest.fail(f"{REQUIRE_ENV}=1 but scipy is not installed")
        pytest.skip("scipy not installed")
    try:
        for b in pb.BEARINGS:
            for c in pb.CONDITIONS:
                pb.fetch(b, c, download=False)
    except FileNotFoundError as e:
        if required:
            pytest.fail(f"{REQUIRE_ENV}=1 but Paderborn cache incomplete: {e}")
        pytest.skip("Paderborn files not cached (python scripts/run_paderborn.py)")


def test_every_member_is_pinned():
    names = {pb.member(b, c) for b in pb.BEARINGS for c in pb.CONDITIONS}
    assert names == set(pb.MAT_SHA256)
    assert all(len(h) == 64 for h in pb.MAT_SHA256.values())


def test_cache_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(pb.CACHE_ENV, str(tmp_path))
    assert pb.default_cache() == tmp_path
    monkeypatch.setenv(pb.CACHE_ENV, " ")
    assert pb.default_cache().parts[-3:] == (".cache", "foldcrypt", "paderborn")


def test_offline_fetch_without_cache_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        pb.fetch("K001", pb.CONDITIONS[0], tmp_path, download=False)


def test_isolated_spikes_counts_single_sample_excursions_only():
    t = np.arange(4096) / 64_000
    x = np.sin(2 * np.pi * 300 * t)  # smooth: no spikes
    assert pb.isolated_spikes(x) == 0
    x[1000] += 3.0
    x[2000] -= 3.0
    assert pb.isolated_spikes(x) == 2
    # a spike sets the largest step close to its own height: fold headroom gone
    row = pb.record_row("synthetic", "test", x, 64_000)
    assert row["dx_over_peak"] > 0.7
    assert pb.isolated_spikes(np.zeros(2)) == 0


def test_cached_paderborn_sweep_matches_committed_metrics():
    _need_cache()
    sweep = pb.run_sweep(download=False)
    s = sweep["summary"]
    # Pre-registered P1, P2, P4 held; P3 (median 64 kHz headroom >= 7.5 dB) falsified.
    assert (s["cells"], s["rule_correct"], s["silent_fail"]) == (144, 144, 0)
    assert (s["recovered"], s["failed_flagged"], s["slip_false_alarm"]) == (4, 140, 0)
    h64 = [r["headroom_db"] for r in sweep["records"] if r["sr"] == pb.SR]
    h16 = [r["headroom_db"] for r in sweep["records"] if r["sr"] == pb.SR // 4]
    assert sum(h > 0 for h in h64) == 9 and not any(h > 0 for h in h16)
    assert max(h64) == pytest.approx(4.17, abs=0.01)
    committed = json.loads((ROOT / "artifacts/paderborn/metrics.json").read_text())
    assert committed["summary"] == s
    assert len(committed["records"]) == len(sweep["records"])
    for a, b in zip(committed["records"], sweep["records"]):
        assert (
            a["record"] == b["record"] and a["isolated_spikes"] == b["isolated_spikes"]
        )
        assert a["headroom_db"] == pytest.approx(b["headroom_db"], abs=1e-9)
    # Outer-ring records carry (almost) no isolated spikes and keep 3.2–4.2 dB;
    # every record with no 64 kHz headroom is spike-dominated.
    for r in sweep["records"]:
        if r["sr"] != pb.SR:
            continue
        if r["record"].startswith("KA04"):
            assert r["isolated_spikes"] <= 2 and r["headroom_db"] > 3.2 - 0.01
        if r["headroom_db"] <= 0:
            assert r["isolated_spikes"] > 100


def test_doc_table_matches_committed_metrics():
    """Every per-bearing range in docs/shockdaq-paderborn.md is recomputed from
    the committed metrics.json (runs without the data cache)."""
    m = json.loads((ROOT / "artifacts/paderborn/metrics.json").read_text())
    doc = (ROOT / "docs/shockdaq-paderborn.md").read_text(encoding="utf-8")
    s = m["summary"]
    assert f"{s['rule_correct']}/{s['cells']}" in doc and s["silent_fail"] == 0

    def rng(vals, fmt):
        return f"{fmt(min(vals))}–{fmt(max(vals))}"

    for b in pb.BEARINGS:
        rows = [
            r for r in m["records"] if r["record"].startswith(b) and r["sr"] == pb.SR
        ]
        assert len(rows) == 4
        ratio = rng([r["dx_over_peak"] for r in rows], lambda v: f"{v:.3f}")
        spikes = rng([r["isolated_spikes"] for r in rows], str)
        lo = min(r["headroom_db"] for r in rows)
        hi = max(r["headroom_db"] for r in rows)
        sign = lambda v: f"{v:+.2f}".replace("-", "−")  # noqa: E731
        head = f"{sign(lo)} to {sign(hi)} dB"
        line = next(ln for ln in doc.splitlines() if ln.startswith(f"| {b} "))
        assert ratio in line and spikes in line and head in line, (
            line,
            ratio,
            spikes,
            head,
        )
    h64 = sorted(r["headroom_db"] for r in m["records"] if r["sr"] == pb.SR)
    assert f"median +{(h64[5] + h64[6]) / 2:.2f} dB" in doc
    assert f"max +{h64[-1]:.2f} dB" in doc
