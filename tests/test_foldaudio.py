"""FoldAudio v0 — synthetic tone roundtrips + clip-vs-fold SNR."""

from __future__ import annotations

import numpy as np
import pytest

from foldcrypt.foldaudio import (
    DEFAULT_LAM,
    fold_capture,
    gen_harsh_kick,
    gen_music_peaks,
    gen_speech_like,
    gen_tone_burst,
    hard_clip,
    max_sample_jump,
    recover_itoh,
    snr_db,
    write_wav,
    read_wav,
)


def test_fold_stays_in_range():
    x = np.linspace(-3.0, 3.0, 1000)
    y = fold_capture(x, 0.5)
    assert np.all(y >= -0.5 - 1e-12)
    assert np.all(y < 0.5 + 1e-12)


def test_hard_clip_destroys_peaks():
    x = np.array([-2.0, -0.2, 0.0, 0.2, 2.0])
    c = hard_clip(x, 0.5)
    assert c[0] == pytest.approx(-0.5)
    assert c[-1] == pytest.approx(0.5)
    assert c[2] == pytest.approx(0.0)


def test_tone_burst_roundtrip_beats_clip():
    lam = DEFAULT_LAM
    # sr=16000 → max_dx < λ for 440 Hz @ peak 1.6
    x = gen_tone_burst(sr=16000, duration_s=0.5, peak_amp=1.6)
    assert max_sample_jump(x) < lam
    folded = fold_capture(x, lam)
    recovered = recover_itoh(folded, lam, anchor=x)
    clipped = hard_clip(x, lam)
    snr_r = snr_db(x, recovered)
    snr_c = snr_db(x, clipped)
    assert snr_r > snr_c + 5.0
    assert snr_r > 20.0


def test_music_peaks_at_48k_beats_clip():
    lam = DEFAULT_LAM
    x = gen_music_peaks(sr=48000, duration_s=1.5)
    assert max_sample_jump(x) < lam
    folded = fold_capture(x, lam)
    recovered = recover_itoh(folded, lam, anchor=x)
    clipped = hard_clip(x, lam)
    assert snr_db(x, recovered) > snr_db(x, clipped) + 5.0


def test_harsh_kick_is_honest_fail():
    """Documented fail: single-sample spikes → max_dx > λ → recover loses to clip."""
    lam = DEFAULT_LAM
    x = gen_harsh_kick(sr=16000, duration_s=0.8)
    assert max_sample_jump(x) > lam
    folded = fold_capture(x, lam)
    recovered = recover_itoh(folded, lam, anchor=x)
    clipped = hard_clip(x, lam)
    snr_r = snr_db(x, recovered)
    snr_c = snr_db(x, clipped)
    # Honest: pathological clicks make fold+Itoh worse than (or not clearly better than) clip
    assert snr_r < snr_c + 3.0


def test_perfect_below_lambda():
    lam = 1.0
    t = np.linspace(0, 1, 2000)
    x = 0.3 * np.sin(2 * np.pi * 50 * t)
    y = fold_capture(x, lam)
    np.testing.assert_allclose(y, x, atol=1e-12)
    rec = recover_itoh(y, lam, anchor=x)
    assert snr_db(x, rec) > 80.0


def test_wav_roundtrip(tmp_path):
    x = gen_tone_burst(sr=8000, duration_s=0.25, peak_amp=0.9)
    path = tmp_path / "t.wav"
    write_wav(path, x, sr=8000)
    y, sr = read_wav(path)
    assert sr == 8000
    assert len(y) == len(x)
    assert snr_db(x, y) > 40.0


def test_speech_and_music_generators_have_peaks():
    speech = gen_speech_like(sr=16000, duration_s=1.0)
    music = gen_music_peaks(sr=16000, duration_s=1.0)
    assert np.max(np.abs(speech)) > DEFAULT_LAM
    assert np.max(np.abs(music)) > DEFAULT_LAM
