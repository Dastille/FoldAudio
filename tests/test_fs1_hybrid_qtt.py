"""Synthetic checks for the FS-1 coder (prereg-2026-11-04-fs1.md)."""

from __future__ import annotations

import numpy as np
import pytest

from foldcrypt import fs1

pytest.importorskip("zstandard")

D = 10
N = 2**D


def _tones(n: int = N) -> np.ndarray:
    t = np.arange(n) / 48000.0
    return np.sin(2 * np.pi * 157 * t) + 0.5 * np.sin(2 * np.pi * 1630 * t + 0.3)


@pytest.mark.parametrize("t", fs1.TRANSFORMS)
def test_int_stream_roundtrip(t: str) -> None:
    rng = np.random.default_rng(1)
    k = np.cumsum(rng.integers(-300, 300, size=500))
    blob = fs1.encode_ints(k, (t,))
    assert fs1.int_stream_choice(blob).startswith(t)
    np.testing.assert_array_equal(fs1.decode_ints(blob, k.size), k)


def test_int_stream_wrong_length_rejected() -> None:
    blob = fs1.encode_ints(np.arange(10))
    with pytest.raises(ValueError):
        fs1.decode_ints(blob, 11)


def test_lpc2_beats_raw_on_smooth_signal() -> None:
    k = np.round(1000 * _tones(4096)).astype(np.int64)
    assert len(fs1.encode_ints(k, ("lpc2",))) < len(fs1.encode_ints(k, ("raw",)))


def test_tt_svd_full_rank_is_exact() -> None:
    x = np.random.default_rng(2).standard_normal(N)
    np.testing.assert_allclose(fs1.tt_full(fs1.tt_svd_rank(x, D, 64)), x, atol=1e-9)


def test_tones_have_low_qtt_rank() -> None:
    cores = fs1.tt_svd_rank(_tones(), D, 4)
    np.testing.assert_allclose(fs1.tt_full(cores), _tones(), atol=1e-9)


def test_baseline_hits_error_window_and_counts_whole_stream() -> None:
    x = _tones() + 0.01 * np.random.default_rng(3).standard_normal(N)
    b = fs1.encode_baseline(x, 3e-3)
    assert b is not None
    assert abs(b.rel - 3e-3) <= 0.01 * 3e-3
    y = fs1.decode(b.stream)
    assert fs1.rel_err(x, y) == pytest.approx(b.rel)
    assert b.nbytes == len(b.stream) > 24  # header is inside the count


def test_hybrid_roundtrip_and_error_window() -> None:
    x = _tones() + 1e-4 * np.random.default_rng(4).standard_normal(N)
    b = fs1.encode_baseline(x, 3e-3)
    assert b is not None
    h = fs1.encode_hybrid(x, D, b.rel)
    assert h is not None
    assert abs(h.rel - b.rel) <= 0.02 * b.rel
    assert fs1.rel_err(x, fs1.decode(h.stream)) == pytest.approx(h.rel)


def test_hybrid_wins_on_clean_tones_positive_control() -> None:
    # 2**12 samples: at 2**10 the fixed core cost (~600 B) still exceeds the
    # whole LPC2 baseline, so the control only makes sense at larger n.
    x = _tones(2**12)
    b = fs1.encode_baseline(x, 3e-3)
    assert b is not None
    h = fs1.encode_hybrid(x, 12, b.rel)
    assert h is not None
    assert h.nbytes < b.nbytes


def test_hybrid_does_not_win_on_white_noise_negative_control() -> None:
    x = np.random.default_rng(5).standard_normal(N)
    b = fs1.encode_baseline(x, 3e-3)
    assert b is not None
    h = fs1.encode_hybrid(x, D, b.rel)
    assert h is not None
    assert h.nbytes >= 0.95 * b.nbytes


def test_hybrid_kept_when_structure_alone_beats_target() -> None:
    # Amendment A regression: three tones at 2**14 need rank 6; R = 8 float32
    # structure is ~1e-7 accurate, which the residual bisection cannot raise
    # into the window. That configuration must survive and win.
    n = 2**14
    t = np.arange(n) / 48000.0
    x = _tones(n) + 0.25 * np.sin(2 * np.pi * 4100 * t + 1.1)
    h = fs1.encode_hybrid(x, 14, 3e-3, ranks=(8,), precs=(4,))
    assert h is not None
    assert h.rel < 3e-3
    assert h.choice.startswith("R8/f32")
    assert fs1.rel_err(x, fs1.decode(h.stream)) == pytest.approx(h.rel)


def test_decode_rejects_foreign_stream() -> None:
    with pytest.raises(ValueError):
        fs1.decode(b"XXXX" + bytes(20))
