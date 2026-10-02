"""FoldAudio v0 — intentional modulo fold beats hard clip on loud peaks.

PRODUCT TRIAL (2026-10-02): software path for phones / field / music demos.
Problem: hard clipping permanently destroys peaks above the ADC range.
Fix: fold (central modulo) at capture, then unwrap later.

ASSUMPTIONS (named — keep honest):
1. Capture applies *central* modulo M_λ(x)=mod(x+λ,2λ)−λ (same as WrapCancel engine),
   not a hardware ADC we claim to own. This is a *software* simulation of folded capture.
2. Recovery uses classic first-order Itoh unwrap (from unfold_detect.itoh_unwrap).
   Consecutive true samples must usually jump by less than λ. Fast impulsive peaks
   that change by >λ between samples can unwrap wrong — see fail cases / harsh_kick.
3. Absolute 2λ level ambiguity is resolved by trying a small set of global offsets
   and picking the one with best SNR vs a known original (demo / offline A/B).
   A live recorder without the original would need a different absolute-level prior
   (e.g. anchor quiet segments near 0) — not implemented in v0.
4. WrapCancel's constellation Mahalanobis path is for *symbol* detection on folded
   streams. Waveform recovery is 1-D unwrap; we reuse modulo + Itoh only.
5. Analysis runs on float64 arrays in memory. Listening WAVs may be peak-normalized
   for int16 PCM; metrics always use the unscaled floats.
6. Soft freeze: synthetic WAVs only; no Parrot GPU. Public repo: Dastille/FoldAudio.

Not Sigil. Not Regenamatron. Not production audio mastering.
"""

from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .modulo import central_modulo
from .unfold_detect import itoh_unwrap

# Default fold threshold: peaks above this fold; below stay linear.
DEFAULT_LAM = 0.45
# 48 kHz: phone/music rate; keeps music-kick slew under λ for Itoh more often.
DEFAULT_SR = 48000


# ---------------------------------------------------------------------------
# Core capture / recover
# ---------------------------------------------------------------------------


def hard_clip(x: np.ndarray, lam: float) -> np.ndarray:
    """Permanent peak loss: clip to [−λ, λ]."""
    if lam <= 0:
        raise ValueError("lam must be positive")
    return np.clip(np.asarray(x, dtype=float), -lam, lam)


def fold_capture(x: np.ndarray, lam: float) -> np.ndarray:
    """Intentional folded capture: y = M_λ(x) ∈ [−λ, λ)."""
    return np.asarray(central_modulo(np.asarray(x, dtype=float), lam), dtype=float)


def recover_itoh(
    y_folded: np.ndarray,
    lam: float,
    *,
    offset_search: int = 4,
    anchor: np.ndarray | None = None,
) -> np.ndarray:
    """Unwrap folded audio with Itoh, then pick best global 2λ offset.

    If `anchor` is given (the original waveform in demos), choose k ∈ [−K..K]
    minimizing ||ŷ + 2λk − anchor||². Without anchor, keep k=0 (folded[0] level)
    — ASSUMPTION: quiet start near 0, or caller supplies another prior later.
    """
    y_hat = itoh_unwrap(np.asarray(y_folded, dtype=float), lam)
    if anchor is None:
        return y_hat
    anchor = np.asarray(anchor, dtype=float)
    best = y_hat
    best_err = np.inf
    for k in range(-offset_search, offset_search + 1):
        cand = y_hat + 2.0 * lam * k
        err = float(np.mean((cand - anchor) ** 2))
        if err < best_err:
            best_err = err
            best = cand
    return best


def snr_db(reference: np.ndarray, estimate: np.ndarray, eps: float = 1e-12) -> float:
    """SNR in dB: 10 log10(||ref||² / ||ref−est||²)."""
    ref = np.asarray(reference, dtype=float)
    est = np.asarray(estimate, dtype=float)
    if ref.shape != est.shape:
        raise ValueError(f"shape mismatch {ref.shape} vs {est.shape}")
    num = float(np.sum(ref**2))
    den = float(np.sum((ref - est) ** 2))
    if den < eps:
        return 120.0  # effectively perfect
    if num < eps:
        return 0.0
    return 10.0 * np.log10(num / den)


def max_sample_jump(x: np.ndarray) -> float:
    """Max |x[n]−x[n−1]| — Itoh needs this ≲ λ on the true waveform."""
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return 0.0
    return float(np.max(np.abs(np.diff(x))))


# ---------------------------------------------------------------------------
# WAV I/O (stdlib wave — float analysis separate from int16 listening files)
# ---------------------------------------------------------------------------


def write_wav(
    path: Path | str,
    samples: np.ndarray,
    sr: int = DEFAULT_SR,
    *,
    peak_normalize: bool = True,
) -> float:
    """Write mono float samples as 16-bit PCM WAV.

    If peak_normalize and |peak|>1, scale for listening only. Returns the
    scale factor applied (1.0 if none). Analysis must use the float arrays,
    not a re-read of this file, when peaks exceed 1.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(samples, dtype=float).reshape(-1)
    peak = float(np.max(np.abs(x))) if len(x) else 1.0
    scale = peak if (peak_normalize and peak > 1.0) else 1.0
    pcm = np.clip(x / scale, -1.0, 1.0)
    ints = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(ints.tobytes())
    return scale


def read_wav(path: Path | str) -> tuple[np.ndarray, int]:
    """Read mono WAV → (float64 samples in ~[-1,1], sample_rate)."""
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    if sw == 2:
        ints = np.frombuffer(raw, dtype=np.int16)
        x = ints.astype(np.float64) / 32768.0
    elif sw == 1:
        ints = np.frombuffer(raw, dtype=np.uint8)
        x = (ints.astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if nch > 1:
        x = x.reshape(-1, nch).mean(axis=1)
    return x, int(sr)


# ---------------------------------------------------------------------------
# Synthetic test signals
# ---------------------------------------------------------------------------


def gen_tone_burst(
    sr: int = DEFAULT_SR,
    duration_s: float = 1.0,
    f0: float = 440.0,
    peak_amp: float = 1.8,
    seed: int = 0,
) -> np.ndarray:
    """Clean sine with envelope so peaks exceed λ — synthetic roundtrip test."""
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    env = 0.35 + 0.65 * (0.5 - 0.5 * np.cos(2 * np.pi * t / duration_s))
    return (peak_amp * env * np.sin(2 * np.pi * f0 * t)).astype(float)


def gen_speech_like(
    sr: int = DEFAULT_SR,
    duration_s: float = 2.0,
    seed: int = 1,
) -> np.ndarray:
    """Formant-ish tones + occasional shout bursts (loud peaks)."""
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    x = 0.22 * np.sin(2 * np.pi * 180 * t)
    x += 0.12 * np.sin(2 * np.pi * 900 * t + 0.3)
    x += 0.08 * np.sin(2 * np.pi * 2100 * t)
    syll = 0.55 + 0.45 * np.sin(2 * np.pi * 3.5 * t)
    x *= syll
    for center, amp, width in ((0.45, 1.7, 0.04), (1.1, 2.1, 0.05), (1.65, 1.9, 0.035)):
        g = np.exp(-0.5 * ((t - center) / width) ** 2)
        x += amp * g * np.sin(2 * np.pi * 320 * t)
    x += 0.01 * rng.standard_normal(n)
    return x.astype(float)


def gen_music_peaks(
    sr: int = DEFAULT_SR,
    duration_s: float = 2.5,
    seed: int = 2,
    *,
    kick_width: float = 0.014,
) -> np.ndarray:
    """Kick-like impulses + sustained harmony — music-peak stress test.

    At 48 kHz with kick_width≈0.014, max sample jump usually stays under
    DEFAULT_LAM so Itoh can succeed. Narrower kicks / lower sr → fail case.
    """
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    x = 0.18 * np.sin(2 * np.pi * 110 * t)
    x += 0.12 * np.sin(2 * np.pi * 165 * t)
    x += 0.10 * np.sin(2 * np.pi * 220 * t)
    x += 0.06 * np.sin(2 * np.pi * 330 * t)
    hit_times = [0.2, 0.5, 0.8, 1.15, 1.5, 1.85, 2.2]
    for i, tc in enumerate(hit_times):
        width = kick_width if i % 2 == 0 else kick_width * 0.7
        amp = 2.4 if i % 2 == 0 else 1.9
        g = np.exp(-0.5 * ((t - tc) / width) ** 2)
        x += amp * g * np.sin(2 * np.pi * 60 * t)
        x += 0.45 * amp * g * np.sin(2 * np.pi * 1800 * t)
    x += 0.008 * rng.standard_normal(n)
    return x.astype(float)


def gen_harsh_kick(
    sr: int = DEFAULT_SR,
    duration_s: float = 1.0,
    seed: int = 3,
) -> np.ndarray:
    """Deliberate fail case: near-discontinuous spikes so max_dx ≫ λ.

    Models a pathological click / digital glitch — Itoh unwrap latches wrong.
    """
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    x = 0.15 * np.sin(2 * np.pi * 220 * t)
    # Single-sample spikes taller than 2λ — consecutive jump ≫ λ
    for idx in (int(0.2 * sr), int(0.5 * sr), int(0.75 * sr)):
        if 1 <= idx < n - 1:
            x[idx] += 2.5 * (1 if rng.random() > 0.5 else -1)
    x += 0.005 * rng.standard_normal(n)
    return x.astype(float)


def ensure_testdata(testdata_dir: Path | str, sr: int = DEFAULT_SR) -> dict[str, np.ndarray]:
    """Build synthetic float arrays + write listening WAVs; return name→samples."""
    d = Path(testdata_dir)
    d.mkdir(parents=True, exist_ok=True)
    specs = {
        "tone_burst": gen_tone_burst(sr=sr),
        "speech_like": gen_speech_like(sr=sr),
        "music_peaks": gen_music_peaks(sr=sr),
        "harsh_kick": gen_harsh_kick(sr=sr),
    }
    for name, samples in specs.items():
        write_wav(d / f"{name}.wav", samples, sr=sr, peak_normalize=True)
    meta = {
        "sr": sr,
        "files": [f"{n}.wav" for n in specs],
        "note": (
            "Synthetic FoldAudio testdata. Listening WAVs may be peak-normalized; "
            "SNR analysis uses in-memory float arrays with true amplitudes."
        ),
    }
    (d / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n")
    return specs


# ---------------------------------------------------------------------------
# Pipeline + report
# ---------------------------------------------------------------------------


@dataclass
class TrialResult:
    name: str
    lam: float
    peak_orig: float
    max_dx: float
    fold_frac: float
    snr_recovered: float
    snr_clipped: float
    snr_gain_db: float
    n_samples: int
    sr: int
    itoh_safe: bool  # max_dx < lam


def run_trial(
    name: str,
    x: np.ndarray,
    sr: int,
    lam: float,
    out_dir: Path,
) -> TrialResult:
    """original → hard-clip → fold → recover; write A/B WAVs; return metrics."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    x = np.asarray(x, dtype=float)
    peak = float(np.max(np.abs(x)))
    dx = max_sample_jump(x)
    fold_frac = float(np.mean(np.abs(x) > lam))

    clipped = hard_clip(x, lam)
    folded = fold_capture(x, lam)
    recovered = recover_itoh(folded, lam, anchor=x)

    snr_r = snr_db(x, recovered)
    snr_c = snr_db(x, clipped)

    stem = name
    write_wav(out_dir / f"{stem}_original.wav", x, sr)
    write_wav(out_dir / f"{stem}_clipped.wav", clipped, sr)
    write_wav(out_dir / f"{stem}_folded.wav", folded, sr)
    write_wav(out_dir / f"{stem}_recovered.wav", recovered, sr)

    return TrialResult(
        name=stem,
        lam=lam,
        peak_orig=peak,
        max_dx=dx,
        fold_frac=fold_frac,
        snr_recovered=snr_r,
        snr_clipped=snr_c,
        snr_gain_db=snr_r - snr_c,
        n_samples=len(x),
        sr=sr,
        itoh_safe=dx < lam,
    )


def format_snr_table(rows: list[TrialResult]) -> str:
    hdr = (
        f"{'name':<12} {'λ':>5} {'peak':>5} {'maxΔ':>5} {'fold%':>6} "
        f"{'SNR_rec':>8} {'SNR_clip':>9} {'gain_dB':>8} {'ItohOK':>6}"
    )
    lines = [hdr, "-" * len(hdr)]
    for r in rows:
        lines.append(
            f"{r.name:<12} {r.lam:5.2f} {r.peak_orig:5.2f} {r.max_dx:5.2f} "
            f"{100 * r.fold_frac:5.1f}% "
            f"{r.snr_recovered:8.2f} {r.snr_clipped:9.2f} {r.snr_gain_db:8.2f} "
            f"{'yes' if r.itoh_safe else 'NO':>6}"
        )
    return "\n".join(lines)


def run_audio_demo(
    *,
    repo_root: Path | str | None = None,
    lam: float = DEFAULT_LAM,
    sr: int = DEFAULT_SR,
) -> list[TrialResult]:
    """Generate testdata in memory, run trials, write metrics JSON, return rows."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[1]
    testdata = root / "testdata"
    artifacts = root / "artifacts" / "foldaudio"
    signals = ensure_testdata(testdata, sr=sr)
    rows: list[TrialResult] = []
    for name, x in signals.items():
        rows.append(run_trial(name, x, sr, lam, artifacts))
    report = {
        "lam": lam,
        "sr": sr,
        "trials": [
            {
                "name": r.name,
                "peak_orig": r.peak_orig,
                "max_sample_jump": r.max_dx,
                "fold_frac": r.fold_frac,
                "snr_recovered_db": r.snr_recovered,
                "snr_clipped_db": r.snr_clipped,
                "snr_gain_db": r.snr_gain_db,
                "itoh_safe_max_dx_lt_lam": r.itoh_safe,
                "n_samples": r.n_samples,
            }
            for r in rows
        ],
        "assumptions": [
            "Software central-modulo capture, not a real folded ADC.",
            "Itoh unwrap + 2λ offset search vs original (demo oracle).",
            "Fails when consecutive sample jumps exceed λ (see harsh_kick).",
            "Listening WAVs may be peak-normalized; metrics use true floats.",
        ],
    }
    (artifacts / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return rows
