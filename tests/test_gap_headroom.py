"""prereg-2026-10-31-k001-gap-headroom.md: guarded short tiles (no own-peak censoring)."""

import json
from pathlib import Path

import numpy as np

from foldcrypt import paderborn_spikes as ps

ROOT = Path(__file__).resolve().parents[1]


def _sine(n=20480):
    return np.sin(2 * np.pi * np.arange(n) / 400.0)


def test_own_peak_rule_censors_low_headroom():
    # A tile whose own-peak detector fires must have raw headroom < 6.02 dB.
    x = _sine(1024)
    x[500] += 1.5
    x[501] -= 1.5
    assert len(ps.spike_indices(x)) > 0
    h = ps.headroom_db(float(np.max(np.abs(x))), ps.max_sample_jump(x))
    assert h < 6.03


def test_guarded_tiles_exclude_spike_neighbourhood_only():
    x = _sine()
    x[3000] += 10.0
    st = ps.guarded_tiles(x)
    assert 2048 not in st and 0 in st and len(st) == 19


def test_injected_bursts_do_not_leak_into_guarded_tiles():
    x = _sine(64 * 1024) * (
        1 + 0.1 * np.random.default_rng(0).standard_normal(64 * 1024)
    )
    inj, _ = ps.inject_bursts(x, 40)
    st = ps.guarded_tiles(inj)
    assert len(st) >= ps.STRETCH_MIN_TILES
    assert ps.tile_headroom_db(x, st) == ps.tile_headroom_db(inj, st)


def test_committed_gap_metrics_consistent():
    m = json.loads((ROOT / "artifacts/paderborn/gap-headroom-metrics.json").read_text())
    assert m["tile_len"] == ps.GAP_LEN == 1024
    assert m["G0"]["verdict"] == "FAIL"
    assert {m[k] for k in ("G1", "G2", "G3", "G4")} == {"UNTESTABLE"}
    assert m["k001_explained"] is False
    assert m["counts"]["lp_k001"] == 20 and m["counts"]["lp_ki04"] == 10
