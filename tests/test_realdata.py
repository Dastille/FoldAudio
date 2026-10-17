import numpy as np
import pytest

from foldcrypt import realdata as rd


def _ring(sr, f=3000.0, n=24000, seed=0):
    """Bearing-like impact train: decaying 3 kHz rings + sensor noise (g)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / sr
    x = 0.01 * rng.standard_normal(n)
    for t0 in np.arange(0.01, n / sr, 0.01):
        m = t >= t0
        x[m] += 2.0 * np.exp(-(t[m] - t0) * 800.0) * np.sin(2 * np.pi * f * (t[m] - t0))
    return x - x.mean()


def test_file_table_is_well_formed():
    for _fid, (sr, label, digest) in rd.CWRU_FILES.items():
        assert sr in (12000, 48000) and label and len(digest) == 64
    assert sum(sr == 48000 for sr, _, _ in rd.CWRU_FILES.values()) == 7


def test_offline_fetch_without_cache_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        rd.fetch(97, tmp_path, download=False)


def test_kurtosis_and_crest_basics():
    g = np.random.default_rng(1).standard_normal(200_000)
    assert abs(rd.kurtosis(g) - 3.0) < 0.1
    assert rd.crest_factor(
        np.sin(np.linspace(0, 200 * np.pi, 100_000))
    ) == pytest.approx(np.sqrt(2), rel=1e-3)


def test_fast_sampling_recovers_exactly_and_keeps_kurtosis():
    x = _ring(96000)
    cells = rd.eval_record("ring@96k", "synthetic", x, 96000, ratios=(0.5,))
    c = cells[0]
    assert c.rule_ok and c.recovered and not c.slip
    assert c.kurt_fold == pytest.approx(c.kurt_true, rel=1e-9)
    assert c.kurt_clip < c.kurt_true


def test_same_event_subsampled_fails_and_is_flagged():
    x = _ring(96000)[::8]  # 12 kHz: 3 kHz ring now steps > peak per sample
    assert rd.headroom_db(np.max(np.abs(x)), np.max(np.abs(np.diff(x)))) <= 0
    for c in rd.eval_record("ring@12k", "synthetic", x, 12000, ratios=(0.8, 0.5)):
        assert not c.rule_ok and not c.recovered and c.flagged and not c.silent_fail


def test_cached_cwru_sweep_has_no_silent_failures():
    pytest.importorskip("scipy")
    try:
        for fid in rd.CWRU_FILES:
            rd.fetch(fid, download=False)
    except FileNotFoundError:
        pytest.skip(
            "CWRU files not cached (run python -m foldcrypt shockdaq-real once)"
        )
    s = rd.run_real_sweep(download=False)["summary"]
    assert s["cells"] == 120
    assert s["rule_correct"] == 120
    assert s["silent_fail"] == 0 and s["slip_false_alarm"] == 0
