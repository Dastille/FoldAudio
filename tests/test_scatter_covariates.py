"""Synthetic checks for the scatter-vs-lock covariate rules
(prereg-2026-11-10-scatter-covariates.md). No real covariate numbers."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps

ROOT = Path(__file__).resolve().parents[1]
LAB = {b: v[0] for b, v in ps.SCATTER_COV_LABELS.items()}


def test_labels_match_published_metrics():
    d = ROOT / "artifacts" / "paderborn"
    k001 = json.loads((d / "ref-snr-phase-metrics.json").read_text())
    k002 = json.loads((d / "fundamental-phase-metrics.json").read_text())
    k003 = json.loads((d / "k003-phase-metrics.json").read_text())
    hs = json.loads((d / "healthy-set-phase-metrics.json").read_text())
    want = {
        "K001": k001["exploratory_k001_per_condition"]["N15_M01_F10"]["r_between"],
        "K002": k002["verdicts"]["n15_m01_orig_r_between"],
        "K003": k003["verdicts"]["n15_m01_r_between"],
        **{
            b: hs["per_bearing"][b]["n15_m01_r_between"]
            for b in ("K004", "K005", "K006")
        },
    }
    for b, (lab, rb, meas) in ps.SCATTER_COV_LABELS.items():
        assert rb == want[b]
        assert lab == ("SCATTER" if rb < ps.R_BETWEEN_HELD else "LOCK")
        for m in meas:
            assert pb.member(b, ps.SCATTER_COV_CONDITION, m) in pb.MAT_SHA256
    assert len(ps.SCATTER_COVARIATES) <= 4


def test_separates_and_p_floor():
    v = {"K001": 1.0, "K002": 5.0, "K003": 6.0, "K004": 2.0, "K005": 4.0, "K006": 3.0}
    r = ps.covariate_verdict(v, LAB)
    assert r["verdict"] == "SEPARATES" and r["direction"] == "SCATTER < LOCK"
    assert r["perm_p_two_sided"] == pytest.approx(0.1)
    r2 = ps.covariate_verdict({b: -x for b, x in v.items()}, LAB)
    assert r2["direction"] == "SCATTER > LOCK"


def test_overlaps():
    v = {"K001": 1.0, "K002": 2.0, "K003": 6.0, "K004": 3.0, "K005": 4.0, "K006": 5.0}
    r = ps.covariate_verdict(v, LAB)
    assert r["verdict"] == "OVERLAPS"
    assert r["perm_p_two_sided"] > 0.1


def test_untestable_on_nan():
    v = {b: 1.0 for b in LAB} | {"K003": math.nan}
    assert ps.covariate_verdict(v, LAB)["verdict"] == "UNTESTABLE"


def test_shuffled_labels_never_true_or_complement():
    for seed in range(50):
        s = ps.shuffled_labels(LAB, seed)
        assert sorted(s.values()).count("SCATTER") == 3
        assert s != LAB
        assert s != {
            b: ("LOCK" if x == "SCATTER" else "SCATTER") for b, x in LAB.items()
        }
    # with distinct values, a non-true, non-complement split always overlaps
    rbs = {b: v[1] for b, v in ps.SCATTER_COV_LABELS.items()}
    assert ps.covariate_verdict(rbs, ps.shuffled_labels(LAB))["verdict"] == "OVERLAPS"


def test_ranges_disjoint():
    per = {b: [0.0, 1.0] if LAB[b] == "SCATTER" else [2.0, 3.0] for b in LAB}
    assert ps.ranges_disjoint(per, LAB)
    per["K002"] = [0.5, 3.0]
    assert not ps.ranges_disjoint(per, LAB)


def test_covariates_from_synthetic_signals():
    rng = np.random.default_rng(1)
    n = pb.SR * 4
    t = np.arange(n) / pb.SR
    x = 0.01 * rng.standard_normal(n)
    spk = np.arange(10_000, n - 10_000, 5_000)
    x[spk] = 2.0
    x[spk + 1] = -2.0
    i1 = np.sin(2 * np.pi * 100 * t) * (1 + 0.01 * np.cos(2 * np.pi * 100 * t))
    i2 = np.sin(2 * np.pi * 100 * t - 2 * np.pi / 3)
    nm = ps.MECH_SR * 4
    speed = 1500 + 15 * rng.standard_normal(nm)  # CV ≈ 0.01
    torque = 0.1 + 0.001 * rng.standard_normal(nm)
    temp = np.array([46.0, 46.5, 47.0, 47.5, 48.0])
    c = ps.covariates_from_signals(
        {
            "vibration_1": x,
            "phase_current_1": i1,
            "phase_current_2": i2,
            "speed": speed,
            "torque": torque,
            "temp_2_bearing_module": temp,
        }
    )
    assert c["speed_cv"] == pytest.approx(0.01, rel=0.05)
    assert c["torque_mean_nm"] == pytest.approx(0.1, abs=1e-4)
    assert c["temp_mean_c"] == pytest.approx(47.0)
    assert c["spike_amp_median"] == pytest.approx(2.0, abs=0.05)
    assert c["n_spikes_trimmed"] >= 40
