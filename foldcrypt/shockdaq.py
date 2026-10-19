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
4. Recovery reuses FoldAudio recover_itoh with anchor (demo A/B oracle). Since
   2026-10-06 a blind column (blind_level.recover_blind, AC-coupling zero-mean
   prior) recovers WITHOUT the original — what a live DAQ would actually run.
5. Itoh needs consecutive true samples to jump by ≲ λ. At DAQ rates (48 kHz or
   51.2 kHz-style) impact ringing usually satisfies this; pathological single-
   sample glitches do not (same limit as FoldAudio harsh_kick).
6. Spectral bias: simple RMS energy in a high-frequency / transient band
   (fraction of Nyquist) vs original — honest, not a full ISO vibration metric.
7. CPU-only synthetic demo. No Parrot / GPU. Not Sigil / Regen / ChaosLog.
8. RAIL column (2026-10-13): count of folded samples sitting at the ADC rails
   (blind_level.rail_hits). An ideal fold never lands there; a fold step that is
   slightly LONG (gain g>0), or a wrap-threshold / offset error, pushes samples
   past the rail where they clip. Demo case gearbox_fold_long uses g=+1 % via
   failmap.nonideal_fold (synthetic front-end error, not a measured part).

FIRMWARE FLAG SKETCH (per capture, blind — uses only the folded samples and the
blind recovery, never the original; see capture_status()):

    if UNREC (slip or edge):  status = "UNRECOVERABLE"     # don't trust the
        # unwrap at all; fall back to the clipped value / mark the record bad.
    elif RAIL (rail_hits>0):  status = "BOUNDED_ACCURACY"  # overload peak:
        # the unwrap is fine (no slip), but some folded samples were clipped at
        # the ADC rail, so peaks near them carry a small bounded error (≈ g of
        # peak, e·λ, o·λ). Report the peak, tagged "bounded accuracy".
    elif overload (|x|>λ):    status = "RECOVERED"         # folded + unwrapped
    else:                     status = "IN_RANGE"

recover_or_clip() (2026-10-15, NOTES #8) is that sketch as a callable: blind
recovery in, (waveform, status, untrusted-sample mask, peak) out. On UNREC it
does NOT emit the unwrap; it falls back to the raw folded ADC samples, which
equal the true signal wherever |x| < λ, marks the overload event(s) untrusted
and reports the peak as "≥ λ" — exactly what a clipping ADC can honestly say.

RAIL ≠ UNREC: UNREC means the unwrap itself may have slipped (whole-record level
can be off by 2λ); RAIL means the unwrap held but some peak samples were clipped
at the rail — a visible, bounded accuracy limit, not a silent unwrap failure.

Reuse: foldcrypt.foldaudio.hard_clip, fold_capture, recover_itoh, snr_db,
max_sample_jump, write_wav.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .blind_level import edge_flag, rail_hits, rail_mask, recover_blind, slip_flag
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
    snr_blind_db: float = 0.0
    peak_error_blind: float = 0.0
    blind_matches_oracle: bool = False
    slip_flag: bool = False
    edge_flag: bool = False
    rail_hits: int = 0
    front_end: str = "ideal"
    fw_status: str = ""  # recover_or_clip(folded).status (blind; 2026-10-15)
    fw_fallback: bool = (
        False  # recover_or_clip discarded the unwrap (UNREC → folded/clip view)
    )
    fw_untrusted: int = 0  # samples recover_or_clip marked untrusted
    snr_fw_db: float = 0.0  # SNR of recover_or_clip's output vs the original

    @property
    def rail_clipped(self) -> bool:
        """RAIL: some folded samples sit at the ADC rail → overload peak, bounded accuracy."""
        return self.rail_hits > 0

    @property
    def overload_unrecoverable(self) -> bool:
        """Blind firmware verdict: this capture's fold recovery can't be trusted.

        slip = baseline before/after event disagree by > λ (an unwrap slip);
        edge = some folded step sat within 10 % of λ (recovery at its limit).
        Both use only the folded capture / blind output — no original.
        """
        return self.slip_flag or self.edge_flag

    @property
    def capture_status(self) -> str:
        """Firmware flag sketch (module docstring): UNREC > RAIL > overload > in range."""
        if self.overload_unrecoverable:
            return "UNRECOVERABLE"
        if self.rail_clipped:
            return "BOUNDED_ACCURACY"
        return "RECOVERED" if self.overload_would_have_flagged else "IN_RANGE"


# ---------------------------------------------------------------------------
# Real-time flag logic sketch (NOTES #8, 2026-10-15): UNREC → fall back to clip
# ---------------------------------------------------------------------------

CAPTURE_STATUSES = ("UNRECOVERABLE", "BOUNDED_ACCURACY", "RECOVERED", "IN_RANGE")


def overload_event_mask(
    y_folded: np.ndarray,
    lam: float,
    *,
    step_frac: float = 0.5,
    gap: int = 1024,
    pad: int = 32,
) -> np.ndarray:
    """Blind mask of overload event(s) in a folded capture — no original needed.

    A step is suspicious if it is an Itoh wrap (|Δy| > λ) or its wrapped size is
    ≥ step_frac·λ. Suspicious steps closer than `gap` samples merge into one
    event; each event is padded by `pad` samples. Outside the mask the folded
    sample is not adjacent to any wrap or big step.

    Measured 2026-10-15 (λ = 5 V, 51.2 kHz): the mask covered every |x| ≥ λ
    sample of the 168 ring-burst cells (56 × seeds 7–9) and the 3 shockdaq-demo
    signals, masking a median 4 % of the record (gearbox 8.6 %). Blind spot:
    an isolated single-sample impulse whose folded step happens to look small
    (FoldAudio harsh_kick class) — the same limit slip/edge already have.
    """
    y = np.asarray(y_folded, dtype=float)
    m = np.zeros(len(y), dtype=bool)
    if len(y) < 2:
        return m
    d = np.diff(y)
    dw = d - 2.0 * lam * np.round(d / (2.0 * lam))
    idx = np.flatnonzero((np.abs(d) > lam) | (np.abs(dw) >= step_frac * lam))
    if not len(idx):
        return m
    brk = np.flatnonzero(np.diff(idx) > gap)
    starts = np.r_[idx[0], idx[brk + 1]]
    ends = np.r_[idx[brk], idx[-1]]
    for a, b in zip(starts, ends):
        m[max(a - pad, 0) : b + 2 + pad] = True
    return m


@dataclass
class CaptureOutput:
    """What firmware would hand downstream for one capture (recover_or_clip)."""

    signal: np.ndarray  # waveform to use (recovered, or folded fallback)
    status: str  # one of CAPTURE_STATUSES
    fallback: bool  # True → unwrap discarded, signal = folded ADC samples
    untrusted: np.ndarray  # bool mask: samples whose value is NOT the true input
    peak_V: float  # reported peak |x|
    peak_is_lower_bound: bool  # True → "peak ≥ peak_V" (saturated, like a clip)
    slip_flag: bool
    edge_flag: bool
    rail_hits: int
    k: int  # blind 2λ level offset used by recover_blind

    @property
    def n_untrusted(self) -> int:
        return int(np.count_nonzero(self.untrusted))


def recover_or_clip(
    y_folded: np.ndarray,
    lam: float,
    *,
    prior: str = "quiet_window",
    fold_gain: float = 0.0,
    bits: int | None = None,
) -> CaptureOutput:
    """Firmware flag logic: blind recover, and if UNREC fall back to the clipped view.

    1. recover_blind (no original); slip/edge self-checks; rail_hits.
    2. UNRECOVERABLE (slip or edge): DISCARD the unwrap. Output the raw folded
       samples y — exact wherever |x| < λ (an ideal fold is the identity there),
       bounded in [−λ, λ) inside the event — with overload_event_mask marking
       the event untrusted (together with any rail-clipped sample, see below)
       and the peak reported as "≥ λ". That is the honest
       content of a clipped capture: in-range samples exact, overload saturated.
       (Rejected: clipping the naive unwrap at ±λ. After a slip the unwrap's
       baseline sits 2λ off, so clip(unwrap) parks the whole tail at the rail —
       measured 2026-10-15: −11 to −16 dB SNR vs a true hard clip on seven
       failing captures, vs −0.9…+1.9 dB for the folded samples, whose
       baseline is exact.)
       Rail-clipped samples are always marked untrusted, also in the fallback
       (2026-10-19, NOTES #8c): with a wrap-threshold error the front end can
       leave a slow excursion just past λ unwrapped and clipped at the ADC rail,
       with steps too small for overload_event_mask. On the CWRU records under
       the non-ideal front end that left 117 overloaded samples in 21 fallback
       cells outside the event mask; event mask OR rail mask covers all of them
       (realdata.run_real_nonideal_sweep).
    3. BOUNDED_ACCURACY (rail_hits > 0): recovered waveform; rail-clipped
       samples marked untrusted (bounded error, see module docstring).
    4. RECOVERED if the unwrap applied any wrap, else IN_RANGE (blind: no
       knowledge of the original).

    Same priority order as ShockDAQResult.capture_status; `bits` only widens the
    rail tolerance by one LSB (blind_level.rail_mask).
    """
    y = np.asarray(y_folded, dtype=float)
    rec, k = recover_blind(y, lam, prior=prior, fold_gain=fold_gain)
    slip = slip_flag(rec, lam)
    edge = edge_flag(y, lam)
    rmask = rail_mask(y, lam, bits=bits)
    nrail = int(np.count_nonzero(rmask))
    if slip or edge:
        return CaptureOutput(
            signal=y.copy(),
            status="UNRECOVERABLE",
            fallback=True,
            untrusted=overload_event_mask(y, lam) | rmask,
            peak_V=float(lam),
            peak_is_lower_bound=True,
            slip_flag=slip,
            edge_flag=edge,
            rail_hits=nrail,
            k=k,
        )
    wrapped = bool(np.any(np.abs(rec - y) > 1e-9 * lam))
    if nrail:
        status = "BOUNDED_ACCURACY"
    else:
        status = "RECOVERED" if wrapped else "IN_RANGE"
    return CaptureOutput(
        signal=rec,
        status=status,
        fallback=False,
        untrusted=rmask,
        peak_V=float(np.max(np.abs(rec))) if len(rec) else 0.0,
        peak_is_lower_bound=False,
        slip_flag=slip,
        edge_flag=edge,
        rail_hits=nrail,
        k=k,
    )


def run_case(
    name: str,
    x: np.ndarray,
    sr: int,
    lam: float,
    out_dir: Path,
    *,
    fold_fn=None,
    front_end: str = "ideal",
) -> ShockDAQResult:
    """Hard-clip vs fold vs recover for one synthetic vibration case.

    fold_fn(x, lam) → folded capture; default = ideal fold_capture. Pass e.g.
    ``lambda x, lam: failmap.nonideal_fold(x, lam, NonIdeal(gain_err=0.01))`` to
    model a front-end error; `front_end` is just the label stored on the row.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    x = np.asarray(x, dtype=float)
    peak = float(np.max(np.abs(x)))
    dx = max_sample_jump(x)
    flagged = would_overload_flag(x, lam)

    # Soft-sat without flag ≡ hard clip for v0 math.
    clipped = hard_clip(x, lam)
    folded = (
        fold_capture(x, lam)
        if fold_fn is None
        else np.asarray(fold_fn(x, lam), dtype=float)
    )
    recovered = recover_itoh(folded, lam, anchor=x)
    blind, _k = recover_blind(folded, lam)
    fw = recover_or_clip(
        folded, lam, prior="zero_mean"
    )  # same prior as the blind column

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
        snr_blind_db=snr_db(x, blind),
        peak_error_blind=peak_abs_error(x, blind),
        blind_matches_oracle=bool(np.allclose(blind, recovered, atol=1e-9)),
        slip_flag=slip_flag(blind, lam),
        edge_flag=edge_flag(folded, lam),
        rail_hits=rail_hits(folded, lam),
        front_end=front_end,
        fw_status=fw.status,
        fw_fallback=fw.fallback,
        fw_untrusted=fw.n_untrusted,
        snr_fw_db=snr_db(x, fw.signal),
    )


def _unrec_tag(r: ShockDAQResult) -> str:
    if not r.overload_unrecoverable:
        return "no"
    return "+".join(
        t for t, on in (("slip", r.slip_flag), ("edge", r.edge_flag)) if on
    ).upper()


def format_shockdaq_table(rows: list[ShockDAQResult]) -> str:
    hdr = (
        f"{'name':<18} {'λ':>4} {'peak':>5} {'maxΔ':>5} "
        f"{'pkErrC':>7} {'pkErrF':>7} "
        f"{'SNR_c':>7} {'SNR_f':>7} {'gain':>7} "
        f"{'biasC':>7} {'biasF':>7} "
        f"{'OLflg':>5} {'Itoh':>4} {'SNR_bl':>7} {'bl=or':>5} {'UNREC':>9} {'RAIL':>4}"
    )
    lines = [hdr, "-" * len(hdr)]
    for r in rows:
        lines.append(
            f"{r.name:<18} {r.lam:4.1f} {r.peak_orig:5.2f} {r.max_dx:5.2f} "
            f"{r.peak_error_clip:7.3f} {r.peak_error_fold:7.3f} "
            f"{r.snr_clip_db:7.2f} {r.snr_fold_db:7.2f} {r.snr_gain_db:7.2f} "
            f"{r.spectral_bias_clip:7.3f} {r.spectral_bias_fold:7.3f} "
            f"{'yes' if r.overload_would_have_flagged else 'no':>5} "
            f"{'yes' if r.itoh_ok else 'NO':>4} "
            f"{r.snr_blind_db:7.2f} {'yes' if r.blind_matches_oracle else 'NO':>5} "
            f"{_unrec_tag(r):>9} {(str(r.rail_hits) if r.rail_clipped else 'no'):>4}"
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

    # Lazy import: failmap imports this module at load time.
    from .failmap import NonIdeal, nonideal_fold

    long_step = NonIdeal("gain +1.0%", gain_err=0.01)
    gearbox = gen_gearbox_startup(sr=sr, lam=lam)
    # name → (signal, fold_fn, front-end label)
    cases = {
        "gearbox_startup": (gearbox, None, "ideal"),
        "impact_transient": (gen_impact_transient(sr=sr, lam=lam), None, "ideal"),
        # Deliberately past the slew limit (max|Δx| > λ): fold can't recover
        # this one — the point is that firmware SAYS so instead of going silent.
        "impact_too_fast": (
            gen_impact_transient(sr=sr, lam=lam, peak_amp=60.0),
            None,
            "ideal",
        ),
        # Same gearbox through a fold step 1 % LONG (g=+0.01, synthetic): the
        # unwrap holds, but samples just past each wrap clip at the ADC rail →
        # RAIL lights up ("overload peak, bounded accuracy"), UNREC stays off.
        "gearbox_fold_long": (
            gearbox,
            lambda v, lam_: nonideal_fold(v, lam_, long_step),
            long_step.name,
        ),
    }
    rows: list[ShockDAQResult] = []
    for name, (x, fn, fe) in cases.items():
        rows.append(run_case(name, x, sr, lam, artifacts, fold_fn=fn, front_end=fe))

    report = {
        "product": "ShockDAQ v0",
        "lam_V": lam,
        "sr": sr,
        "assumptions": [
            "λ≈5.0 V models ±5 V IEPE soft-sat rail (ASSUMPTION, not a specific OEM chip).",
            "Soft-sat without overload flag ≡ hard_clip for v0; would_overload_flag is the honest missing flag.",
            "Synthetic numpy generators only — not real field IEPE captures.",
            "Itoh + 2λ offset search vs original (demo oracle); blind column uses AC-coupling zero-mean prior, no original.",
            "overload_unrecoverable = blind slip OR edge self-check (failmap.py rule); impact_too_fast is a deliberate past-limit case.",
            "rail_hits = folded samples at the ADC rails (blind_level.rail_mask); >0 → RAIL / 'bounded accuracy'. gearbox_fold_long models a +1 % long fold step (synthetic front-end error, not a measured part).",
            "fw_* = recover_or_clip (blind firmware sketch): on UNREC the unwrap is discarded and the raw folded samples are output (exact where |x|<λ), event samples marked untrusted, peak reported as ≥ λ.",
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
                "snr_blind_db": r.snr_blind_db,
                "peak_error_blind_V": r.peak_error_blind,
                "blind_matches_oracle": r.blind_matches_oracle,
                "slip_flag": r.slip_flag,
                "edge_flag": r.edge_flag,
                "overload_unrecoverable": r.overload_unrecoverable,
                "front_end": r.front_end,
                "rail_hits": r.rail_hits,
                "rail_clipped": r.rail_clipped,
                "capture_status": r.capture_status,
                "fw_status": r.fw_status,
                "fw_fallback": r.fw_fallback,
                "fw_untrusted_samples": r.fw_untrusted,
                "snr_fw_db": r.snr_fw_db,
            }
            for r in rows
        ],
    }
    (artifacts / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return rows
