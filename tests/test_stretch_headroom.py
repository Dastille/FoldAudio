"""prereg-2026-10-31-stretch-headroom.md: despike adjacent-pair fix (Part B) and stretch tiles (Part A)."""

import json
from pathlib import Path

import numpy as np

from foldcrypt import paderborn_spikes as ps

ROOT = Path(__file__).resolve().parents[1]


def _sine(n=20000):
    t = np.arange(n)
    return np.sin(2 * np.pi * t / 400.0)


def _old_despike(x, frac=0.5, max_passes=50):
    y = x.copy()
    for _ in range(max_passes):
        idx = ps.spike_indices(y, frac)
        if len(idx) == 0:
            break
        y[idx] = 0.5 * (y[idx - 1] + y[idx + 1])
    return y


def test_k001_burst_middle_sample_is_the_mechanism():
    """Locks the PR #9 explanation: with the peak held up elsewhere, the burst's
    quiet sample between its two same-sign lobes is flagged in the same pass as
    a lobe; simultaneous repair leaves a two-sample plateau. The fix removes it."""
    t = np.arange(2000) / 64000.0
    x = 0.1 * (np.sin(2 * np.pi * 500 * t) + 0.3 * np.sin(2 * np.pi * 1300 * t))
    x[500] = 4.611
    x[699:701] = [1.5, 3.3]
    x[1000:1007] = ps.K001_BURST
    assert ps.max_sample_jump(_old_despike(x)[995:1012]) > 1.5
    assert ps.max_sample_jump(ps.despike(x).y[995:1012]) < 0.5


def test_zero_error_needs_residue_below_native_step():
    """Second condition for an exact 0 dB row: the burst's low-level samples
    left after despiking must sit below the record's own max step. On KA04
    (max step 1.0-2.9) they do; on a smooth tone they do not."""
    t = np.arange(64000) / 64000.0
    x = np.sin(2 * np.pi * 500 * t) + 0.3 * np.sin(2 * np.pi * 1300 * t)
    assert ps.d0_burst_row(x, n=100)["abs_err_db"] > 1.0


def test_committed_results_match_prereg_reading():
    m = json.loads(
        (ROOT / "artifacts/paderborn/stretch-headroom-metrics.json").read_text()
    )
    assert m["stretch_len"] == 6400 and m["guard"] == 32
    b = m["part_b"]
    assert (b["burst_pass"], b["single_pass"], b["n"], b["B1"]) == (39, 40, 40, "HELD")
    # 22 zero rows were complete removals: zero rows stay zero after the fix.
    assert sum(r["burst"]["abs_err_db"] == 0.0 for r in m["part_b_rows"].values()) >= 22
    assert m["S0"]["verdict"] == "FAIL"
    assert m["S1"]["S1"] == m["S2"]["S2"] == "UNTESTABLE"
    assert all(
        r["tiles"] == 0 for k, r in m["records"].items() if r["bearing"] != "KA04"
    )
    for name in ("docs/foldaudio-whitepaper.md", "docs/shockdaq-paderborn.md"):
        doc = (ROOT / name).read_text(encoding="utf-8")
        assert (
            "39/40" in doc
            and "UNTESTABLE" in doc
            and "4.46 / 5.32 / 4.02 / 2.92" in doc
        )


def test_non_adjacent_keeps_larger_deviation():
    y = np.array([0.0, 5.0, -1.0, 0.0, 0.0])
    idx = np.array([1, 2])
    assert ps._non_adjacent(y, idx).tolist() == [1]


def test_single_sample_spikes_unchanged_by_fix():
    x = _sine(40000)
    inj, _ = ps.inject_spikes(x, 100)
    assert np.allclose(ps.despike(inj).y, _old_despike(inj))


def test_stretch_tiles_and_untestable():
    x = _sine(64000)
    assert ps.spike_free_tiles(x) == list(range(0, 64000 - 6400 + 1, 6400))
    sh, n = ps.stretch_headroom_db(x)
    assert n == 10 and sh is not None
    y = x.copy()
    y[::3000] += 10.0  # spike every 3000 samples: no 6400-sample tile is clean
    assert ps.stretch_headroom_db(y) == (None, 0)


def test_count_verdict():
    assert ps.count_verdict(4, 4, 2) == "HELD"
    assert ps.count_verdict(2, 4, 2) == "FALSIFIED"
    assert ps.count_verdict(3, 4, 2) == "INCONCLUSIVE"
