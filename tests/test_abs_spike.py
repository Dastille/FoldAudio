"""prereg-2026-10-31c-k001-abs-spike.md: absolute small-spike guard + same-tile control."""

import json
from pathlib import Path

import numpy as np

from foldcrypt import paderborn_spikes as ps

ROOT = Path(__file__).resolve().parents[1]


def _sine(n=64 * 1024):
    return np.sin(2 * np.pi * np.arange(n) / 400.0)


def test_burst_score_is_one_times_amplitude():
    # Amendment A: the v1 0.75*T control was undetectable by design.
    b = np.array(ps.K001_BURST) / np.max(np.abs(ps.K001_BURST))
    assert 1.0 < ps.spike_score(b).max() < 1.01


def test_abs_detector_sees_small_bursts_and_v1_amp_misses():
    x, t = _sine(), 0.5
    big, pos = ps.inject_bursts(x, 40, amp_x_peak=ps.A0S_AMP_X_T * t)
    assert ps.burst_detect_frac(big, pos, t) >= ps.A0S_MIN_FRAC
    small, pos = ps.inject_bursts(x, 40, amp_x_peak=0.75 * t)
    assert ps.burst_detect_frac(small, pos, t) == 0.0


def test_abs_tiles_guard_window():
    x = _sine()
    x[5000] += 0.3  # score ~0.3: above t = 0.2, below record bar 0.5*peak
    good, flagged = ps.abs_tiles(x, 0.2)
    assert 4096 in flagged and 4096 not in good and 0 in good
    # post guard 128: tile ending < 128 before a flag is excluded
    y = _sine()
    y[1024 * 3 + 100] += 0.3
    g, _ = ps.abs_tiles(y, 0.2)
    assert 2048 not in g and 1024 in g


def test_committed_metrics_close_d():
    m = json.loads((ROOT / "artifacts/paderborn/abs-spike-metrics.json").read_text())
    assert m["A0"]["verdict"] == "PASS" and m["A0s"]["verdict"] == "PASS"
    assert m["counts"]["k001_untestable"] == 20 and m["counts"]["lp_ki04"] == 10
    assert m["outcome"] == "CLOSED: not separable on this rig"
    v1 = json.loads(
        (ROOT / "artifacts/paderborn/abs-spike-v1-metrics.json").read_text()
    )
    assert v1["A0s"]["verdict"] == "FAIL"
