"""Synthetic checks for the spike-phase probe (prereg-2026-10-27-phase.md)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from foldcrypt import paderborn_spikes as ps

pytest.importorskip("scipy")

SR = 64_000
N = 4 * SR + 1


def _currents(ripple: float = 0.02, phase0: float = 0.3, fe: float = 60.0):
    """Balanced 3-phase currents whose magnitude carries a 100 Hz ripple."""
    t = np.arange(N) / SR
    mag = 1.0 + ripple * np.cos(2 * np.pi * 100.0 * t + phase0)
    i1 = mag * np.cos(2 * np.pi * fe * t)
    i2 = mag * np.cos(2 * np.pi * fe * t - 2 * np.pi / 3)
    return t, i1, i2


def _vib_with_spikes(idx: np.ndarray, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = 0.05 * rng.standard_normal(N)
    x[idx] = 5.0 * np.where(np.arange(len(idx)) % 2 == 0, 1.0, -1.0)
    return x


def _spikes_at_phase(t, phase0, target, jitter=0.0, seed=2):
    """One spike per 100 Hz cycle where the magnitude ripple phase = target."""
    rng = np.random.default_rng(seed)
    cyc = np.arange(20, 380)  # stay clear of the 0.1 s edges
    th = target + jitter * rng.uniform(-1, 1, len(cyc))
    tt = (2 * np.pi * cyc + th - phase0) / (2 * np.pi * 100.0)
    return np.unique(np.round(tt * SR).astype(int))


def test_current_magnitude_of_balanced_set_is_flat():
    t, i1, i2 = _currents(ripple=0.0)
    m = ps.current_magnitude(i1, i2)
    assert np.allclose(m, 1.0, atol=1e-9)


def test_spikes_at_known_phase_are_recovered_there():
    for target in (0.0, math.pi / 2, -2.5):
        t, i1, i2 = _currents(phase0=0.7)
        idx = _spikes_at_phase(t, 0.7, target)
        r = ps.phase_from_signals("syn", "N09_x", 2, _vib_with_spikes(idx), i1, i2, SR)
        assert r is not None and r.ref_valid
        assert r.r > 0.95
        err = abs(np.angle(np.exp(1j * (r.mu - target))))
        assert err < math.radians(5)
        assert r.null_r99 < 0.2


def test_uniform_spikes_give_low_r():
    t, i1, i2 = _currents()
    rng = np.random.default_rng(5)
    idx = np.sort(rng.choice(np.arange(10_000, N - 10_000, 7), 300, replace=False))
    r = ps.phase_from_signals("syn", "N09_x", 2, _vib_with_spikes(idx), i1, i2, SR)
    assert r is not None and r.r < 0.2 and r.p > 1e-3


def test_reference_without_ripple_is_invalid():
    t, i1, i2 = _currents(ripple=0.0)
    rng = np.random.default_rng(3)
    i1 = i1 + 1e-3 * rng.standard_normal(N)
    i2 = i2 + 1e-3 * rng.standard_normal(N)
    idx = _spikes_at_phase(t, 0.0, 0.0)
    r = ps.phase_from_signals("syn", "N09_x", 2, _vib_with_spikes(idx), i1, i2, SR)
    assert r is not None and not r.ref_valid


def test_non_spiky_record_returns_none():
    t, i1, i2 = _currents()
    x = np.sin(2 * np.pi * 157.0 * t)  # smooth: no single-sample spikes
    assert ps.phase_from_signals("syn", "N09_x", 2, x, i1, i2, SR) is None


def _set(targets, phase0s, jitter=0.0):
    out = []
    for k, (tg, p0) in enumerate(zip(targets, phase0s)):
        t, i1, i2 = _currents(phase0=p0)
        idx = _spikes_at_phase(t, p0, tg, jitter=jitter, seed=10 + k)
        out.append(
            ps.phase_from_signals(
                f"s{k}", "N09_x", 2, _vib_with_spikes(idx), i1, i2, SR
            )
        )
    return out


def test_verdicts_fixed_phase_near_peak_hold_and_shift_null_rejects():
    recs = _set(
        [0.1, -0.1, 0.2, 0.0, 0.15, -0.05, 0.05, -0.15],
        [0.0, 1.0, 2.0, 3.0, -1.0, -2.0, 0.5, -0.5],
    )
    v = ps.phase_verdicts(recs)
    assert v["P1"] == "HELD" and v["P2"] == "HELD" and v["P3"] == "HELD"
    assert v["null_b_p"] <= 0.01 and v["null_b_r99"] < v["r_between"]


def test_verdicts_trough_falsifies_p3_and_random_phases_falsify_p2():
    recs = _set(
        [math.pi - 0.1, -math.pi + 0.1] * 4, [0.0, 1.0, 2.0, 3.0, -1.0, -2.0, 0.5, -0.5]
    )
    assert ps.phase_verdicts(recs)["P3"] == "FALSIFIED"
    recs = _set([0.0, 2.1, -2.1, 1.0, -1.0, 3.0], [0.0] * 6)
    v = ps.phase_verdicts(recs)
    assert v["P2"] == "FALSIFIED" and v["P3"] == "UNTESTABLE"


def test_spread_spikes_falsify_p1():
    recs = _set([0.0] * 4, [0.0, 1.0, 2.0, 3.0], jitter=math.pi)
    assert ps.phase_verdicts(recs)["P1"] == "FALSIFIED"


def test_too_few_valid_references_is_untestable():
    recs = _set([0.0] * 3, [0.0, 1.0, 2.0])
    for r in recs[:2]:
        r.ref_valid = False
    assert ps.phase_verdicts(recs)["P1"] == "UNTESTABLE"
