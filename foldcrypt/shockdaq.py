"""ShockDAQ v0 — fold-vs-hard-clip demo for IEPE / vibration DAQ waveforms.

COMPANY BET (2026-10-04 Sunday hard push): fold firmware inside IEPE/vibration
DAQ front-ends. Silent soft-clip corrupts acceptance tests; fold recovers peaks.

ASSUMPTIONS (named — keep honest):
1. IEPE-style soft-sat model: signal in volts. Nominal full-scale λ defaults to
   5.0, representing a ±5 V soft-clip rail while some systems accept / expect
   ±10 V. This is an ASSUMPTION for the demo, not a claim about any specific
   OEM chip, PCB, or DAQ card.
2. Soft-sat without overload flag (v0 math): capture equals hard_clip to [−λ, λ].
   Separately we compute `would_overload_flag` = True if any |x| > λ — the honest
   flag the silent soft-clip path lacks. Folded capture uses fold_capture instead.
3. Synthetic generators only (numpy). Gearbox = rising RPM-like chirp + startup
   transient peaks. Impact = quiet baseline + ringing spikes. Not real field data.
4. Recovery reuses FoldAudio recover_itoh with anchor (demo A/B oracle). A live
   DAQ without the original needs an absolute-level prior — not in v0.
5. Itoh needs consecutive true samples to jump by ≲ λ. At DAQ rates (48 kHz or
   51.2 kHz-style) impact ringing usually satisfies this; pathological single-
   sample glitches do not (same limit as FoldAudio harsh_kick).
6. Spectral bias: simple RMS energy in a high-frequency / transient band
   (fraction of Nyquist) vs original — honest, not a full ISO vibration metric.
7. CPU-only synthetic demo. No Parrot / GPU. Not Sigil / Regen / ChaosLog.

Reuse: foldcrypt.foldaudio.hard_clip, fold_capture, recover_itoh, snr_db,
max_sample_jump, write_wav.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .foldaudio import (
    fold_capture,
    hard_clip,
    max_sample_jump,
    recover_itoh,
    snr_db,
    write_wav,
)

# IEPE-style soft-sat rail (ASSUMPTION — see module docstring).
DEFAULT_LAM_V = 5.0
# Common vibration DAQ rates: 48 kHz phone-adjacent; 51200 = 51.2 kHz-style.
DEFAULT_SR = 51200


# ---------------------------------------------------------------------------
# Synthetic IEPE / vibration generators (volts)
# ---------------------------------------------------------------------------


def gen_gearbox_startup(
    sr: int = DEFAULT_SR,
    duration_s: float = 2.0,
    *,
    lam: float = DEFAULT_LAM_V,
    peak_amp: float = 8.5,
    f_start: float = 20.0,
    f_end: float = 400.0,
    seed: int = 10,
) -> np.ndarray:
    """Rising RPM-like chirp + startup transient peaks that exceed λ.

    Models a gearbox spin-up: fundamental sweeps up in frequency while a few
    early torque-spike / mesh-transient bursts push past the soft-sat rail
    (flat-top under hard clip). Amplitudes in volts.
    """
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    # Linear chirp (instantaneous phase for rising RPM proxy).
    k = (f_end - f_start) / max(duration_s, 1e-9)
    phase = 2 * np.pi * (f_start * t + 0.5 * k * t**2)
    # Envelope grows with speed then levels (startup load).
    env = 0.35 + 0.55 * np.clip(t / (0.6 * duration_s), 0.0, 1.0)
    x = (0.55 * lam) * env * np.sin(phase)
    # Mesh harmonic (weaker).
    x += 0.12 * lam * env * np.sin(2.0 * phase)
    # Startup transient peaks that exceed λ (flat-top under hard clip).
    for center, amp, width in (
        (0.12 * duration_s, peak_amp, 0.018),
        (0.28 * duration_s, 0.92 * peak_amp, 0.022),
        (0.55 * duration_s, 0.75 * peak_amp, 0.025),
    ):
        g = np.exp(-0.5 * ((t - center) / width) ** 2)
        x += amp * g * np.sin(2 * np.pi * 85.0 * t)
        x += 0.35 * amp * g * np.sin(2 * np.pi * 1200.0 * t)
    x += 0.02 * lam * rng.standard_normal(n)
    return x.astype(float)


def gen_impact_transient(
    sr: int = DEFAULT_SR,
    duration_s: float = 1.5,
    *,
    lam: float = DEFAULT_LAM_V,
    peak_amp: float = 9.0,
    n_impacts: int = 2,
    seed: int = 11,
) -> np.ndarray:
    """Quiet baseline + impact spikes (ringing) that exceed λ.

    At high enough sr (48k / 51.2k-style) sample jumps usually stay < λ so
    Itoh unwrap can succeed. Ringing uses a damped sinusoid, not a click.
    """
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    # Quiet structural / bearing hum well below λ.
    x = 0.08 * lam * np.sin(2 * np.pi * 60.0 * t)
    x += 0.04 * lam * np.sin(2 * np.pi * 180.0 * t)
    x += 0.015 * lam * rng.standard_normal(n)

    # Stagger impacts across the record.
    centers = np.linspace(0.25 * duration_s, 0.75 * duration_s, n_impacts)
    for i, tc in enumerate(centers):
        amp = peak_amp * (1.0 - 0.12 * i)
        # Damped ringing — rise ~ few ms so max_dx < λ at DEFAULT_SR.
        tau_rise = 0.0018
        tau_decay = 0.012
        dt = t - tc
        # Causal envelope: 0 before impact, fast rise, exponential decay.
        # Compute only on dt>=0 to avoid exp overflow on large negative dt.
        env = np.zeros_like(t)
        post = dt >= 0
        dtp = dt[post]
        env[post] = (1.0 - np.exp(-dtp / tau_rise)) * np.exp(-dtp / tau_decay)
        f_ring = 850.0 + 120.0 * i
        x += amp * env * np.sin(2 * np.pi * f_ring * t)
        x += 0.4 * amp * env * np.sin(2 * np.pi * (2.1 * f_ring) * t)
    return x.astype(float)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def would_overload_flag(x: np.ndarray, lam: float) -> bool:
    """True if any |sample| exceeds λ — honest flag silent soft-sat lacks."""
    return bool(np.any(np.abs(np.asarray(x, dtype=float)) > lam))


def peak_abs_error(reference: np.ndarray, estimate: np.ndarray) -> float:
    """Absolute error on true peak amplitude: ||peak(ref)| − |peak(est)||."""
    ref = np.asarray(reference, dtype=float)
    est = np.asarray(estimate, dtype=float)
    # Compare peak magnitudes (sign of peak location may flip under bad unwrap).
    return float(abs(np.max(np.abs(ref)) - np.max(np.abs(est))))


def spectral_bias_hf(
    reference: np.ndarray,
    estimate: np.ndarray,
    sr: int,
    *,
    band_lo_frac: float = 0.15,
    band_hi_frac: float = 0.45,
) -> float:
    """Relative RMS bias in a high-frequency / transient band vs original.

    Method (honest / simple): rFFT magnitudes, take bins from band_lo_frac *
    Nyquist to band_hi_frac * Nyquist, compare RMS energy:
        bias = (E_est − E_ref) / (E_ref + eps)
    Negative → estimate lost HF energy (typical of flat-top clip).
    Not an ISO 10816 / order-tracking metric — demo indicator only.
    """
    ref = np.asarray(reference, dtype=float)
    est = np.asarray(estimate, dtype=float)
    if ref.shape != est.shape:
        raise ValueError(f"shape mismatch {ref.shape} vs {est.shape}")
    n = len(ref)
    if n < 8:
        return 0.0
    R = np.abs(np.fft.rfft(ref))
    E = np.abs(np.fft.rfft(est))
    freqs = np.fft.rfftfreq(n, d=1.0 / sr)
    nyq = 0.5 * sr
    lo, hi = band_lo_frac * nyq, band_hi_frac * nyq
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return 0.0
    e_ref = float(np.sqrt(np.mean(R[mask] ** 2)))
    e_est = float(np.sqrt(np.mean(E[mask] ** 2)))
    eps = 1e-12
    return (e_est - e_ref) / (e_ref + eps)


@dataclass
class ShockDAQResult:
    name: str
    lam: float
    sr: int
    peak_orig: float
    max_dx: float
    peak_error_clip: float
    peak_error_fold: float
    snr_clip_db: float
    snr_fold_db: float
    snr_gain_db: float
    spectral_bias_clip: float
    spectral_bias_fold: float
    overload_would_have_flagged: bool
    itoh_ok: bool
    n_samples: int


def run_case(
    name: str,
    x: np.ndarray,
    sr: int,
    lam: float,
    out_dir: Path,
) -> ShockDAQResult:
    """Hard-clip vs fold vs recover for one synthetic vibration case."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    x = np.asarray(x, dtype=float)
    peak = float(np.max(np.abs(x)))
    dx = max_sample_jump(x)
    flagged = would_overload_flag(x, lam)

    # Soft-sat without flag ≡ hard clip for v0 math.
    clipped = hard_clip(x, lam)
    folded = fold_capture(x, lam)
    recovered = recover_itoh(folded, lam, anchor=x)

    pe_c = peak_abs_error(x, clipped)
    pe_f = peak_abs_error(x, recovered)
    snr_c = snr_db(x, clipped)
    snr_f = snr_db(x, recovered)
    sb_c = spectral_bias_hf(x, clipped, sr)
    sb_f = spectral_bias_hf(x, recovered, sr)

    stem = name
    # Persist float arrays for analysis; WAVs peak-normalized for listening.
    np.save(out_dir / f"{stem}_original.npy", x)
    np.save(out_dir / f"{stem}_clipped.npy", clipped)
    np.save(out_dir / f"{stem}_folded.npy", folded)
    np.save(out_dir / f"{stem}_recovered.npy", recovered)
    # Scale volts → roughly unit peak for 16-bit listening (metrics use .npy).
    write_wav(out_dir / f"{stem}_original.wav", x / max(peak, 1e-12), sr)
    write_wav(out_dir / f"{stem}_clipped.wav", clipped / max(peak, 1e-12), sr)
    write_wav(out_dir / f"{stem}_folded.wav", folded / max(lam, 1e-12), sr)
    write_wav(out_dir / f"{stem}_recovered.wav", recovered / max(peak, 1e-12), sr)

    return ShockDAQResult(
        name=stem,
        lam=lam,
        sr=sr,
        peak_orig=peak,
        max_dx=dx,
        peak_error_clip=pe_c,
        peak_error_fold=pe_f,
        snr_clip_db=snr_c,
        snr_fold_db=snr_f,
        snr_gain_db=snr_f - snr_c,
        spectral_bias_clip=sb_c,
        spectral_bias_fold=sb_f,
        overload_would_have_flagged=flagged,
        itoh_ok=dx < lam,
        n_samples=len(x),
    )


def format_shockdaq_table(rows: list[ShockDAQResult]) -> str:
    hdr = (
        f"{'name':<18} {'λ':>4} {'peak':>5} {'maxΔ':>5} "
        f"{'pkErrC':>7} {'pkErrF':>7} "
        f"{'SNR_c':>7} {'SNR_f':>7} {'gain':>7} "
        f"{'biasC':>7} {'biasF':>7} "
        f"{'OLflg':>5} {'Itoh':>4}"
    )
    lines = [hdr, "-" * len(hdr)]
    for r in rows:
        lines.append(
            f"{r.name:<18} {r.lam:4.1f} {r.peak_orig:5.2f} {r.max_dx:5.2f} "
            f"{r.peak_error_clip:7.3f} {r.peak_error_fold:7.3f} "
            f"{r.snr_clip_db:7.2f} {r.snr_fold_db:7.2f} {r.snr_gain_db:7.2f} "
            f"{r.spectral_bias_clip:7.3f} {r.spectral_bias_fold:7.3f} "
            f"{'yes' if r.overload_would_have_flagged else 'no':>5} "
            f"{'yes' if r.itoh_ok else 'NO':>4}"
        )
    return "\n".join(lines)


def run_shockdaq_demo(
    out_dir: Path | str | None = None,
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
) -> list[ShockDAQResult]:
    """Run gearbox + impact cases; write artifacts + metrics.json; return rows."""
    root = Path(__file__).resolve().parents[1]
    artifacts = Path(out_dir) if out_dir else root / "artifacts" / "shockdaq"
    artifacts.mkdir(parents=True, exist_ok=True)

    cases = {
        "gearbox_startup": gen_gearbox_startup(sr=sr, lam=lam),
        "impact_transient": gen_impact_transient(sr=sr, lam=lam),
    }
    rows: list[ShockDAQResult] = []
    for name, x in cases.items():
        rows.append(run_case(name, x, sr, lam, artifacts))

    report = {
        "product": "ShockDAQ v0",
        "lam_V": lam,
        "sr": sr,
        "assumptions": [
            "λ≈5.0 V models ±5 V IEPE soft-sat rail (ASSUMPTION, not a specific OEM chip).",
            "Soft-sat without overload flag ≡ hard_clip for v0; would_overload_flag is the honest missing flag.",
            "Synthetic numpy generators only — not real field IEPE captures.",
            "Itoh + 2λ offset search vs original (demo oracle).",
            "spectral_bias = relative RMS in HF band (0.15–0.45 Nyquist); not ISO vibration metrics.",
        ],
        "cases": [
            {
                "name": r.name,
                "peak_orig_V": r.peak_orig,
                "max_sample_jump_V": r.max_dx,
                "peak_error_clip_V": r.peak_error_clip,
                "peak_error_fold_V": r.peak_error_fold,
                "snr_clip_db": r.snr_clip_db,
                "snr_fold_db": r.snr_fold_db,
                "snr_gain_db": r.snr_gain_db,
                "spectral_bias_clip": r.spectral_bias_clip,
                "spectral_bias_fold": r.spectral_bias_fold,
                "overload_would_have_flagged": r.overload_would_have_flagged,
                "itoh_ok_max_dx_lt_lam": r.itoh_ok,
                "n_samples": r.n_samples,
            }
            for r in rows
        ],
    }
    (artifacts / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return rows
