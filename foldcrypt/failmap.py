"""ShockDAQ fail-case map — where fold recovery breaks, and whether it says so.

NOTES slice #1 (2026-10-07 weekday slice). Fold + Itoh unwrap has one hard
limit: consecutive true samples must differ by less than λ. In OEM terms:

    max slew rate (V/s)  <  λ · sample_rate

For a pure sine of peak A and frequency f that is  A · f < λ · sr / (2π)
(λ = 5 V, sr = 51.2 kHz → A·f < ~40.7 kV·Hz, e.g. 10 V at ~4 kHz).

This module sweeps a ringing-impact burst over (peak V, ring Hz), recovers
BLIND (blind_level.recover_blind, no original), and records:
  * predicted_ok  — max|Δx| < λ (the rule above)
  * recovered_ok  — blind SNR ≥ OK_SNR_DB
  * slip_flag     — blind self-check: baseline level before vs after the
                    event disagree by > λ (an unwrap slip left a 2λ step)
  * edge_flag     — blind risk check: some folded step sat within 10 % of λ
                    (recovery ran right at its limit)
Both flags use only the folded capture / recovered output — what live firmware
would have. The point for a DAQ buyer: when fold fails, does it fail LOUDLY
(flagged) instead of silently like a soft-clip?

Quantization (NOTES #5, 2026-10-09): run_quant_sweep re-runs the grid through an
N-bit modulo-ADC (modulo.quantize_folded) — see docs/shockdaq-failmap.md.

Non-ideal front end (NOTES #6, 2026-10-11): run_nonideal_sweep adds sensor noise
and fold/ADC non-idealities (wrap gain mismatch, wrap-threshold error, offset, INL
bow) — see docs/shockdaq-failmap.md.

Noise-aware slew rule (NOTES #8, 2026-10-15): noise_aware_slew_ok — spec-sheet
rule with a k·σ margin, max|Δx_signal| < λ − k·σ, k = NOISE_K fitted on the
noise rows of the non-ideal sweep (docs/shockdaq-failmap.md).

Combined derate + noise rule (NOTES #8b, 2026-10-16): combined_slew_ok —
max|Δx_signal| < λ·(1 − 2|g| − |e| − |o| − π·|a|) − k·σ (derate clamped ≥ 0,
threshold clamped ≥ 0). Clears residual INL/combo false-ok that noise margin
alone leaves; blind σ from blind_level.estimate_noise_sigma (quiet window).

ASSUMPTIONS (named): synthetic ringing burst (same shape family as
shockdaq.gen_impact_transient: fundamental + 0.4× at 2.1 f, noise 1.5 % λ);
quantization only in run_quant_sweep (default grid is ideal); λ is a demo rail, not an OEM part. CPU only, numpy only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .blind_level import (  # noqa: F401 (re-export)
    EDGE_FRAC,
    edge_flag,
    estimate_noise_sigma,
    inl_inverse,
    rail_hits,
    rail_mask,
    recover_blind,
    slip_flag,
)
from .foldaudio import fold_capture, max_sample_jump, snr_db
from .modulo import quantize_folded
from .shockdaq import DEFAULT_LAM_V, DEFAULT_SR

OK_SNR_DB = 60.0

# ---------------------------------------------------------------------------
# Noise-aware slew rule (NOTES #8, 2026-10-15 weekday slice)
# ---------------------------------------------------------------------------
#
# The plain rule max|Δx| < λ is exact on the samples the fold actually sees —
# but nobody knows those in advance. A spec sheet / test plan knows the SIGNAL's
# slew (noiseless) and the front end's noise σ (V rms). White noise adds a
# per-step term with std √2·σ, so near the signal's steepest step the realised
# jump can exceed the signal's by a few σ. Noise-aware rule:
#
#     recovers  iff  max|Δx_signal| < λ − k·σ        (margin clamped to [0, λ])
#
# k fitted 2026-10-15 on the 9 noise rows of run_nonideal_sweep (ideal + 60…0 dB
# SNR, 56 cells × seeds 7–11 = 2,520 cells; per-cell σ): smallest k on a 0.25
# grid with ZERO "rule says ok but the unwrap slipped" cells is 4.75; NOISE_K =
# 5.0 rounds up for margin. Plain spec-sheet rule (k = 0): 119 false-ok, 0
# false-no, 2401/2520 agree. k = 5: 0 false-ok, 85 false-no, 2435/2520 agree;
# ideal/60/40 dB rows unchanged at 280/280. Fitting on seeds 7–9 alone gives
# k = 4.0, which still leaves 4 false-ok on held-out seeds 10–11 — hence the
# all-seed fit plus round-up. Synthetic burst + white noise only.
NOISE_K = 5.0


def slew_threshold(lam: float, sigma: float, *, k: float = NOISE_K) -> float:
    """Allowed per-sample signal step under noise σ: λ − k·σ, clamped to [0, λ].

    A threshold of 0 means the noise has used up the whole slew budget (nothing
    passes) — the honest answer at σ ≥ λ/k, not an error.
    """
    if lam <= 0:
        raise ValueError("lam must be positive")
    margin = min(max(k * float(sigma), 0.0), lam)
    return lam - margin


def noise_aware_slew_ok(
    max_dx: float, lam: float, sigma: float, *, k: float = NOISE_K
) -> bool:
    """Noise-aware slew rule: max_dx < λ − k·σ (slew_threshold).

    max_dx = max |Δ| of the SIGNAL (noiseless / spec-sheet slew, volts per
    sample); sigma = front-end noise rms (V). Applying it to an already-noisy
    max_dx double-counts the noise (the plain rule is already exact there).
    σ = 0 reduces to the plain rule max_dx < λ.
    """
    return bool(max_dx < slew_threshold(lam, sigma, k=k))


# ---------------------------------------------------------------------------
# Combined derate + noise-aware slew rule (NOTES #8b, 2026-10-16 weekday slice)
# ---------------------------------------------------------------------------
#
# Noise margin alone (NOTES #8) clears noisy-row false-ok but leaves 3–4 cells
# per INL row (and a few combo cells) where the unwrap slips because the fold
# non-ideality narrowed the effective slew budget. The derated rule of §4.5
# accounts for g/e/o/INL but ignores σ. Combined:
#
#     recovers  iff  max|Δx_signal| < λ·D − k·σ
#     D = max(0, 1 − 2|g| − |e| − |o| − π·|a|)
#     threshold clamped to ≥ 0
#
# max_dx is the noiseless / spec-sheet slew (same convention as
# noise_aware_slew_ok). σ = 0 → derate-only; no front-end errors (D = 1) →
# noise-aware; both apply together. Blind σ for live firmware:
# blind_level.estimate_noise_sigma on the quiet window of the folded capture.


def combined_slew_threshold(
    lam: float,
    sigma: float,
    *,
    gain_err: float = 0.0,
    thresh_err: float = 0.0,
    offset: float = 0.0,
    inl: float = 0.0,
    k: float = NOISE_K,
) -> float:
    """Allowed per-sample signal step under front-end errors and noise.

    λ · max(0, 1 − 2|g| − |e| − |o| − π·|a|) − k·σ, clamped to ≥ 0.
    A threshold of 0 means the derate and/or noise has used up the slew budget.
    """
    if lam <= 0:
        raise ValueError("lam must be positive")
    derate = (
        1.0
        - 2.0 * abs(float(gain_err))
        - abs(float(thresh_err))
        - abs(float(offset))
        - np.pi * abs(float(inl))
    )
    derate = max(0.0, derate)
    return max(0.0, lam * derate - max(float(k) * float(sigma), 0.0))


def combined_slew_ok(
    max_dx: float,
    lam: float,
    sigma: float,
    *,
    gain_err: float = 0.0,
    thresh_err: float = 0.0,
    offset: float = 0.0,
    inl: float = 0.0,
    k: float = NOISE_K,
) -> bool:
    """Combined derate + noise-aware slew rule (NOTES #8b).

    max_dx = max |Δ| of the SIGNAL (noiseless / spec-sheet slew); sigma =
    front-end noise rms (V). σ = 0 reduces to the derated rule on the clean
    slew; zero front-end errors reduce to noise_aware_slew_ok.
    """
    return bool(
        max_dx
        < combined_slew_threshold(
            lam,
            sigma,
            gain_err=gain_err,
            thresh_err=thresh_err,
            offset=offset,
            inl=inl,
            k=k,
        )
    )


DEFAULT_AMPS = (6.0, 8.0, 10.0, 14.0, 20.0, 30.0, 40.0)
DEFAULT_FREQS = (500.0, 1000.0, 2000.0, 3000.0, 4000.0, 6000.0, 8000.0, 12000.0)


def ring_burst(
    sr: int = DEFAULT_SR,
    *,
    amp: float,
    f_ring: float,
    lam: float = DEFAULT_LAM_V,
    duration_s: float = 0.5,
    seed: int = 7,
) -> np.ndarray:
    """Quiet AC-coupled baseline + one damped ringing impact at 40 % of record."""
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    x = 0.08 * lam * np.sin(2 * np.pi * 60.0 * t)
    x += 0.015 * lam * rng.standard_normal(n)
    dt = t - 0.4 * duration_s
    env = np.zeros_like(t)
    post = dt >= 0
    env[post] = (1.0 - np.exp(-dt[post] / 0.0018)) * np.exp(-dt[post] / 0.012)
    x += amp * env * np.sin(2 * np.pi * f_ring * t)
    x += 0.4 * amp * env * np.sin(2 * np.pi * 2.1 * f_ring * t)
    return x


@dataclass
class FailCell:
    amp_V: float
    f_ring_Hz: float
    lam_V: float
    sr: int
    max_dx_V: float
    predicted_ok: bool
    snr_blind_db: float
    recovered_ok: bool
    slip_flag: bool
    edge_flag: bool
    bits: int | None = None  # None = ideal (unquantized) capture
    peak_V: float = float("nan")  # max |x| of the input; overloaded iff ≥ λ

    @property
    def overloaded(self) -> bool:
        """Input actually exceeded the fold threshold (a plain ADC would clip)."""
        return bool(self.peak_V >= self.lam_V)

    @property
    def silent_fail(self) -> bool:
        return (not self.recovered_ok) and not (self.slip_flag or self.edge_flag)


def eval_cell(
    amp: float,
    f_ring: float,
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    bits: int | None = None,
    seed: int = 7,
) -> FailCell:
    """One (peak, ring) cell. bits=None: ideal ADC, ok = SNR >= 60 dB.

    bits=N: the folded signal goes through an N-bit modulo-ADC quantizer
    (step Δ = λ/2^(N-1)); "ok" then means every recovered sample is within one
    LSB (Δ) of the true input — i.e. exact to ADC resolution, no unwrap slip.
    (A 60 dB SNR bar is meaningless at 4 bits.)
    """
    x = ring_burst(sr, amp=amp, f_ring=f_ring, lam=lam, seed=seed)
    y = fold_capture(x, lam)
    if bits is not None:
        y, _ = quantize_folded(y, lam, bits)
    rec, _k = recover_blind(y, lam, prior="quiet_window")
    dx = max_sample_jump(x)
    s = snr_db(x, rec)
    if bits is None:
        ok = bool(s >= OK_SNR_DB)
    else:
        ok = bool(np.max(np.abs(rec - x)) <= lam / 2 ** (bits - 1))
    return FailCell(
        amp_V=amp,
        f_ring_Hz=f_ring,
        lam_V=lam,
        sr=sr,
        max_dx_V=dx,
        predicted_ok=bool(dx < lam),
        snr_blind_db=s,
        recovered_ok=ok,
        slip_flag=slip_flag(rec, lam),
        edge_flag=edge_flag(y, lam),
        bits=bits,
        peak_V=float(np.max(np.abs(x))),
    )


def run_failmap(
    amps=DEFAULT_AMPS,
    freqs=DEFAULT_FREQS,
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    bits: int | None = None,
    seed: int = 7,
) -> list[FailCell]:
    return [
        eval_cell(a, f, lam=lam, sr=sr, bits=bits, seed=seed)
        for a in amps
        for f in freqs
    ]


DEFAULT_BITS = (4, 6, 8, 12, 16, 24)


def run_quant_sweep(
    bits_list=DEFAULT_BITS,
    amps=DEFAULT_AMPS,
    freqs=DEFAULT_FREQS,
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    seed: int = 7,
) -> dict:
    """Does ADC resolution move the slew edge? One summary row per bit depth, plus
    the ideal (unquantized) row for reference. `rule_agrees` uses the plain slew
    rule max|Δx| < λ; `tight_rule_agrees` uses the worst-case max|Δx| < λ − Δ.
    """
    rows = []
    for bits in (None, *bits_list):
        cells = run_failmap(amps, freqs, lam=lam, sr=sr, bits=bits, seed=seed)
        s = summarize(cells)
        step = None if bits is None else lam / 2 ** (bits - 1)
        s["bits"] = bits
        s["step_V"] = step
        s["tight_rule_agrees"] = (
            None
            if step is None
            else sum((c.max_dx_V < lam - step) == c.recovered_ok for c in cells)
        )
        rows.append(s)
    return {"lam_V": lam, "sr": sr, "seed": seed, "rows": rows}


def format_quant_sweep(sweep: dict) -> str:
    hdr = " bits  step(V)  ok  fail  rule  tight  flagged  SILENT  slipFA  edge-on-ok"
    lines = [hdr, "-" * len(hdr)]
    for r in sweep["rows"]:
        b = "ideal" if r["bits"] is None else f"{r['bits']:>5}"
        st = "     -" if r["step_V"] is None else f"{r['step_V']:>7.4f}"
        tight = (
            "   -" if r["tight_rule_agrees"] is None else f"{r['tight_rule_agrees']:>4}"
        )
        lines.append(
            f"{b:>5} {st:>8} {r['recovered_ok']:>3} {r['failed']:>5} {r['rule_agrees_with_outcome']:>5} "
            f"{tight:>6} {r['fails_flagged']:>8} {r['fails_silent']:>7} {r['slip_false_alarms_on_ok']:>7} "
            f"{r['edge_warnings_on_ok']:>11}"
        )
    n = sweep["rows"][0]["cells"]
    lines.append(
        f"{n} cells per row. rule = plain slew rule matches outcome; tight = worst-case rule (λ−step) matches."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Non-ideal front end (NOTES #6, 2026-10-11 Sunday hard push)
# ---------------------------------------------------------------------------
#
# Model (all SYNTHETIC, all named — not any OEM part):
#   noise_snr_db  additive white Gaussian sensor/electronic noise added BEFORE the
#                 fold; σ = rms(clean x) / 10^(SNR/20). Truth = the noisy input
#                 (the fold sees it; recovery can't remove noise, only unwrap it).
#   gain_err  g   fold subtracts 2λ(1+g) per wrap while recovery assumes 2λ
#                 ("gain mismatch between fold and quantizer"). Leaves a
#                 2λ·g staircase error per wrap crossed, and for g>0 the folded
#                 value can land below −λ (outside ADC range → clips).
#   thresh_err e  wrap threshold sits at λ(1−e) instead of λ (comparator/
#                 reference error). Folded value then spills outside the ADC range
#                 by up to λ·|e| on one side and is clipped there.
#   offset    o   quantizer DC offset o·λ added to the folded value (then ADC clip);
#                 excluded from the accuracy error (a plain ADC has it too).
#   inl       a   smooth INL bow a·λ·sin(π y/λ) on the folded value (zero at ±λ).
#   bits          optional N-bit quantizer (modulo.quantize_folded).
# ADC clip: folded value outside [−λ, λ) saturates at the ADC rails.

NONIDEAL_OK_BAR_FRAC = 0.01  # "accurate" = max error <= 1 % of true peak


@dataclass(frozen=True)
class NonIdeal:
    name: str = "ideal"
    noise_snr_db: float | None = None
    gain_err: float = 0.0
    thresh_err: float = 0.0
    offset: float = 0.0
    inl: float = 0.0
    bits: int | None = None


def nonideal_fold(x: np.ndarray, lam: float, ni: NonIdeal) -> np.ndarray:
    """Fold x through the non-ideal modulo front end described above."""
    x = np.asarray(x, dtype=float)
    m = np.floor((x + lam * (1.0 - ni.thresh_err)) / (2.0 * lam))
    y = x - 2.0 * lam * (1.0 + ni.gain_err) * m
    y = y + ni.offset * lam
    y = np.clip(y, -lam, lam - 1e-12)  # ADC rails
    if ni.inl:
        y = y + ni.inl * lam * np.sin(np.pi * y / lam)
    if ni.bits is not None:
        y, _ = quantize_folded(y, lam, ni.bits)
    return y


@dataclass
class NonIdealCell:
    config: str
    amp_V: float
    f_ring_Hz: float
    seed: int
    sigma_V: float
    max_dx_V: float  # max |Δ| of the (noisy) input the fold actually saw
    max_dx_clean_V: float  # same, before noise was added
    predicted_ok: bool  # plain slew rule on the noisy input: max_dx < λ
    clean_rule_ok: (
        bool  # slew rule on the noiseless burst (what a spec sheet would say)
    )
    derated_ok: (
        bool  # max_dx < λ(1 − 2|g| − |e| − |o| − π·inl): rule derated for fold errors
    )
    recovered_ok: bool  # no unwrap slip: max|rec − truth| < λ
    err_peak_V: float  # max |rec − truth|
    peak_err_frac: float  # err_peak / true peak
    accurate: bool  # recovered_ok and peak_err_frac <= 1 %
    slip_flag: bool
    edge_flag: bool
    rail_hits: int = (
        0  # folded samples sitting at the ADC rails (clipped; visible in the capture)
    )
    noise_aware_ok: bool = (
        True  # noise_aware_slew_ok(max_dx_clean, λ, σ): spec-sheet rule with k·σ margin
    )
    peak_V: float = float("nan")  # max |x| of the input the fold saw (noisy)
    lam_V: float = DEFAULT_LAM_V
    combined_ok: bool = True  # combined_slew_ok(max_dx_clean, λ, σ, g/e/o/inl): derate + k·σ (NOTES #8b)

    @property
    def silent_fail(self) -> bool:
        return (not self.recovered_ok) and not (self.slip_flag or self.edge_flag)

    @property
    def overloaded(self) -> bool:
        """Input the fold saw actually reached λ (a plain ADC would clip)."""
        return bool(self.peak_V >= self.lam_V)

    @property
    def silent_inaccurate(self) -> bool:
        """Recovered with no slip but off by > 1 % of peak, and nothing flagged."""
        return (
            self.recovered_ok
            and not self.accurate
            and not (self.slip_flag or self.edge_flag)
        )

    @property
    def silent_inaccurate_no_rail(self) -> bool:
        """silent_inaccurate AND no rail-clipped sample to explain it (truly invisible)."""
        return self.silent_inaccurate and self.rail_hits == 0


def eval_nonideal_cell(
    amp: float,
    f_ring: float,
    ni: NonIdeal,
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    seed: int = 7,
    gain_cal: float = 0.0,
    inl_cal: tuple = (),
    noise_k: float = NOISE_K,
) -> NonIdealCell:
    """gain_cal = calibrated fold-step gain ĝ; inl_cal = calibrated INL harmonics
    (volts, calibrate.estimate_front_end). Defaults = uncalibrated recovery.
    noise_k = k of the noise-aware spec-sheet rule (noise_aware_ok field)."""
    x_clean = ring_burst(sr, amp=amp, f_ring=f_ring, lam=lam, seed=seed)
    sigma = 0.0
    x = x_clean
    if ni.noise_snr_db is not None:
        sigma = float(np.sqrt(np.mean(x_clean**2)) / 10 ** (ni.noise_snr_db / 20.0))
        rng = np.random.default_rng(10_000 + seed)
        x = x_clean + sigma * rng.standard_normal(len(x_clean))
    y = nonideal_fold(x, lam, ni)
    y_in = inl_inverse(y, lam, inl_cal) if len(inl_cal) else y
    rec, _k = recover_blind(y_in, lam, prior="quiet_window", fold_gain=gain_cal)
    dx = max_sample_jump(x)
    dx_clean = max_sample_jump(x_clean)
    # Truth includes the quantizer's constant DC offset: a plain ADC has that error
    # too, so it is not fold-attributable (IEPE is AC-coupled anyway).
    err = float(np.max(np.abs(rec - (x + ni.offset * lam))))
    peak = float(np.max(np.abs(x)))
    derate = (
        1.0
        - 2.0 * abs(ni.gain_err)
        - abs(ni.thresh_err)
        - abs(ni.offset)
        - np.pi * abs(ni.inl)
    )
    ok = bool(err < lam)
    frac = err / peak if peak > 0 else 0.0
    return NonIdealCell(
        config=ni.name,
        amp_V=amp,
        f_ring_Hz=f_ring,
        seed=seed,
        sigma_V=sigma,
        max_dx_V=dx,
        max_dx_clean_V=dx_clean,
        predicted_ok=bool(dx < lam),
        clean_rule_ok=bool(dx_clean < lam),
        derated_ok=bool(dx < lam * derate),
        recovered_ok=ok,
        err_peak_V=err,
        peak_err_frac=frac,
        accurate=bool(ok and frac <= NONIDEAL_OK_BAR_FRAC),
        slip_flag=slip_flag(rec, lam),
        edge_flag=edge_flag(y, lam),
        rail_hits=rail_hits(y, lam, bits=ni.bits),
        noise_aware_ok=noise_aware_slew_ok(dx_clean, lam, sigma, k=noise_k),
        combined_ok=combined_slew_ok(
            dx_clean,
            lam,
            sigma,
            gain_err=ni.gain_err,
            thresh_err=ni.thresh_err,
            offset=ni.offset,
            inl=ni.inl,
            k=noise_k,
        ),
        peak_V=peak,
        lam_V=lam,
    )


def default_nonideal_configs() -> list[NonIdeal]:
    """One-factor-at-a-time sweeps plus two combined rows."""
    cfgs = [NonIdeal("ideal")]
    cfgs += [
        NonIdeal(f"noise {s:g} dB", noise_snr_db=s)
        for s in (60, 40, 30, 20, 15, 10, 5, 0)
    ]
    cfgs += [
        NonIdeal(f"gain {g:+.1%}", gain_err=g)
        for g in (-0.05, -0.01, 0.001, 0.01, 0.05)
    ]
    cfgs += [
        NonIdeal(f"thresh {e:+.0%}", thresh_err=e) for e in (-0.10, -0.02, 0.02, 0.10)
    ]
    cfgs += [NonIdeal(f"offset {o:+.0%}", offset=o) for o in (0.02, 0.10)]
    cfgs += [NonIdeal(f"inl {a:.0%}", inl=a) for a in (0.01, 0.02, 0.05)]
    cfgs += [
        NonIdeal(
            "combo-mild",
            noise_snr_db=60,
            gain_err=0.001,
            thresh_err=0.005,
            offset=0.005,
            inl=0.002,
            bits=16,
        ),
        NonIdeal(
            "combo-bad",
            noise_snr_db=40,
            gain_err=0.005,
            thresh_err=0.01,
            offset=0.01,
            inl=0.01,
            bits=12,
        ),
    ]
    return cfgs


def summarize_nonideal(cells: list[NonIdealCell]) -> dict:
    n = len(cells)
    fails = [c for c in cells if not c.recovered_ok]
    ok_cells = [c for c in cells if c.recovered_ok]
    return {
        "cells": n,
        "recovered_ok": len(ok_cells),
        "failed": len(fails),
        "rule_agrees": sum(c.predicted_ok == c.recovered_ok for c in cells),
        "clean_rule_agrees": sum(c.clean_rule_ok == c.recovered_ok for c in cells),
        "derated_rule_agrees": sum(c.derated_ok == c.recovered_ok for c in cells),
        # 2026-10-15 (additive): spec-sheet rule with k·σ margin vs plain spec-sheet rule.
        # false_ok = rule said "recovers" but the unwrap slipped (the dangerous miss).
        "noise_aware_rule_agrees": sum(
            c.noise_aware_ok == c.recovered_ok for c in cells
        ),
        "noise_aware_false_ok": sum(
            c.noise_aware_ok and not c.recovered_ok for c in cells
        ),
        "noise_aware_false_no": sum(
            (not c.noise_aware_ok) and c.recovered_ok for c in cells
        ),
        "combined_rule_agrees": sum(c.combined_ok == c.recovered_ok for c in cells),
        "combined_false_ok": sum(c.combined_ok and not c.recovered_ok for c in cells),
        "combined_false_no": sum((not c.combined_ok) and c.recovered_ok for c in cells),
        "clean_rule_false_ok": sum(
            c.clean_rule_ok and not c.recovered_ok for c in cells
        ),
        "fails_flagged": sum(c.slip_flag or c.edge_flag for c in fails),
        "fails_silent": sum(c.silent_fail for c in cells),
        "slip_false_alarms_on_ok": sum(c.slip_flag for c in ok_cells),
        "edge_warnings_on_ok": sum(c.edge_flag for c in ok_cells),
        "accurate": sum(c.accurate for c in cells),
        "inaccurate_but_recovered": sum(
            c.recovered_ok and not c.accurate for c in cells
        ),
        "silent_inaccurate": sum(c.silent_inaccurate for c in cells),
        "silent_inaccurate_no_rail": sum(c.silent_inaccurate_no_rail for c in cells),
        "median_peak_err_frac_on_ok": float(
            np.median([c.peak_err_frac for c in ok_cells])
        )
        if ok_cells
        else None,
    }


NONIDEAL_SEEDS = (7, 8, 9, 10, 11)


def run_nonideal_sweep(
    configs: list[NonIdeal] | None = None,
    amps=DEFAULT_AMPS,
    freqs=DEFAULT_FREQS,
    *,
    seeds=NONIDEAL_SEEDS,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    gain_cal: dict[str, float] | None = None,
    inl_cal: dict[str, tuple] | None = None,
    noise_k: float = NOISE_K,
) -> dict:
    """Run the amp x freq grid through each non-ideal config (x seeds).

    gain_cal: optional {config name: ĝ} — recover that config with the calibrated
    fold step (calibrate.run_calibration_sweep). Missing names use ĝ = 0.
    inl_cal: optional {config name: INL harmonic coefs} — same idea for INL.
    """
    configs = configs if configs is not None else default_nonideal_configs()
    gain_cal = gain_cal or {}
    inl_cal = inl_cal or {}
    rows, all_cells = [], []
    for ni in configs:
        gc = float(gain_cal.get(ni.name, 0.0))
        cells = [
            eval_nonideal_cell(
                a,
                f,
                ni,
                lam=lam,
                sr=sr,
                seed=sd,
                gain_cal=gc,
                inl_cal=tuple(inl_cal.get(ni.name, ())),
                noise_k=noise_k,
            )
            for sd in seeds
            for a in amps
            for f in freqs
        ]
        s = summarize_nonideal(cells)
        s["config"] = ni.name
        s["params"] = {k: v for k, v in asdict(ni).items() if k != "name"}
        s["median_sigma_V"] = float(np.median([c.sigma_V for c in cells]))
        rows.append(s)
        all_cells.extend(cells)
    return {
        "lam_V": lam,
        "sr": sr,
        "seeds": list(seeds),
        "noise_k": noise_k,
        "rows": rows,
        "cells": all_cells,
    }


def fit_noise_k(
    cells: list[NonIdealCell], ks=None, *, lam: float = DEFAULT_LAM_V
) -> dict:
    """Cheap k scan for the noise-aware rule on already-evaluated cells (no re-run).

    Returns one row per k (agrees / false_ok / false_no) plus `k_min_safe` =
    smallest k with zero false-ok cells (None if none). Reuses each cell's
    max_dx_clean_V and sigma_V, so it costs nothing beyond the sweep itself.
    """
    ks = np.arange(0.0, 8.01, 0.25) if ks is None else np.asarray(ks, dtype=float)
    rows = []
    for k in ks:
        pred = [
            noise_aware_slew_ok(c.max_dx_clean_V, lam, c.sigma_V, k=float(k))
            for c in cells
        ]
        rows.append(
            {
                "k": float(k),
                "agrees": sum(p == c.recovered_ok for p, c in zip(pred, cells)),
                "false_ok": sum(p and not c.recovered_ok for p, c in zip(pred, cells)),
                "false_no": sum(
                    (not p) and c.recovered_ok for p, c in zip(pred, cells)
                ),
            }
        )
    safe = [r["k"] for r in rows if r["false_ok"] == 0]
    return {"cells": len(cells), "rows": rows, "k_min_safe": safe[0] if safe else None}


def noise_configs() -> list[NonIdeal]:
    """The ideal + noise-only rows of default_nonideal_configs (the NOISE_K fit set)."""
    return [
        c
        for c in default_nonideal_configs()
        if c.name == "ideal" or c.name.startswith("noise")
    ]


def format_nonideal_sweep(sweep: dict) -> str:
    hdr = (
        "config            ok  fail  rule  clean  derated  flagged  SILENT  slipFA  edge-on-ok  "
        "accurate  off>1%pk-unflagged  n-aware  combined  falseOK n→c"
    )
    lines = [hdr, "-" * len(hdr)]
    for r in sweep["rows"]:
        lines.append(
            f"{r['config']:<16} {r['recovered_ok']:>4} {r['failed']:>5} {r['rule_agrees']:>5} "
            f"{r['clean_rule_agrees']:>6} {r['derated_rule_agrees']:>8} {r['fails_flagged']:>8} "
            f"{r['fails_silent']:>7} {r['slip_false_alarms_on_ok']:>7} {r['edge_warnings_on_ok']:>11} "
            f"{r['accurate']:>9} {r['silent_inaccurate']:>12} "
            f"{r.get('noise_aware_rule_agrees', '-'):>15} "
            f"{r.get('combined_rule_agrees', '-'):>9} "
            f"{str(r.get('noise_aware_false_ok', '-')) + '→' + str(r.get('combined_false_ok', '-')):>12}"
        )
    n = sweep["rows"][0]["cells"]
    lines.append(
        f"{n} cells per row ({len(sweep['seeds'])} seed(s)). rule = slew rule on the noisy input; "
        "clean = rule on noiseless burst; derated = rule with λ shrunk by fold errors."
    )
    lines.append(
        f"n-aware = spec-sheet rule with noise margin, max|Δx_clean| < λ − k·σ (k = {sweep.get('noise_k', NOISE_K):g}); "
        f"combined = derate + noise margin, max|Δx_clean| < λ·D − k·σ "
        f"(D = max(0, 1−2|g|−|e|−|o|−π·|a|)); "
        "falseOK n→c = cells the rule called ok that slipped, noise-aware → combined."
    )
    lines.append(
        "ok = no unwrap slip (max error < λ); accurate = ok AND max error ≤ 1 % of peak; "
        "off>1%pk-unflagged = recovered (no slip) but >1 % of peak off and unflagged (an accuracy limit, not an unwrap failure)."
    )
    return "\n".join(lines)


def summarize(cells: list[FailCell]) -> dict:
    n = len(cells)
    agree = sum(c.predicted_ok == c.recovered_ok for c in cells)
    fails = [c for c in cells if not c.recovered_ok]
    caught = [c for c in fails if c.slip_flag or c.edge_flag]
    ok_cells = [c for c in cells if c.recovered_ok]
    false_alarm = [c for c in ok_cells if c.slip_flag]
    edge_on_ok = [c for c in ok_cells if c.edge_flag]
    return {
        "cells": n,
        "recovered_ok": len(ok_cells),
        "failed": len(fails),
        "rule_agrees_with_outcome": agree,
        "fails_flagged": len(caught),
        "fails_silent": len(fails) - len(caught),
        "fails_caught_by_slip": sum(c.slip_flag for c in fails),
        "fails_caught_by_edge": sum(c.edge_flag for c in fails),
        "slip_false_alarms_on_ok": len(false_alarm),
        "edge_warnings_on_ok": len(edge_on_ok),
    }


def format_failmap(cells: list[FailCell]) -> str:
    """Grid: rows = peak V, cols = ring Hz. ok / F! (flagged fail) / FS (silent fail)."""
    amps = sorted({c.amp_V for c in cells})
    freqs = sorted({c.f_ring_Hz for c in cells})
    by = {(c.amp_V, c.f_ring_Hz): c for c in cells}
    hdr = "peak V \\ ring Hz " + " ".join(f"{int(f):>6}" for f in freqs)
    lines = [hdr, "-" * len(hdr)]
    for a in amps:
        row = []
        for f in freqs:
            c = by[(a, f)]
            tag = "ok" if c.recovered_ok else ("FS" if c.silent_fail else "F!")
            if c.recovered_ok and c.edge_flag:
                tag = "ok~"
            row.append(f"{tag:>6}")
        lines.append(f"{a:>16.0f} " + " ".join(row))
    lines.append(
        "ok = recovered blind (SNR≥60 dB); ok~ = recovered but edge warning; "
        "F! = failed and flagged; FS = failed silently"
    )
    return "\n".join(lines)


def write_svg(cells: list[FailCell], path: Path, *, lam: float, sr: int) -> None:
    """Dependency-free heatmap: cell colour = outcome, dashed line = slew rule (pure sine)."""
    amps = sorted({c.amp_V for c in cells})
    freqs = sorted({c.f_ring_Hz for c in cells})
    by = {(c.amp_V, c.f_ring_Hz): c for c in cells}
    cw, ch, ox, oy = 70, 40, 90, 50
    w, h = ox + cw * len(freqs) + 20, oy + ch * len(amps) + 90
    col = {"ok": "#3a9d5d", "ok~": "#9fd27a", "F!": "#e0a030", "FS": "#c0392b"}
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="11">',
        f'<text x="{ox}" y="20" font-size="13" font-weight="bold">ShockDAQ fold fail map — λ={lam:g} V, sr={sr} Hz, blind recovery</text>',
    ]
    for i, a in enumerate(reversed(amps)):
        y0 = oy + i * ch
        out.append(
            f'<text x="{ox - 8}" y="{y0 + ch / 2 + 4}" text-anchor="end">{a:g} V</text>'
        )
        for j, f in enumerate(freqs):
            c = by[(a, f)]
            tag = "ok" if c.recovered_ok else ("FS" if c.silent_fail else "F!")
            if c.recovered_ok and c.edge_flag:
                tag = "ok~"
            x0 = ox + j * cw
            out.append(
                f'<rect x="{x0}" y="{y0}" width="{cw - 2}" height="{ch - 2}" fill="{col[tag]}"/>'
            )
            out.append(
                f'<text x="{x0 + cw / 2 - 1}" y="{y0 + ch / 2 + 4}" text-anchor="middle" fill="#fff">{c.snr_blind_db:.0f} dB</text>'
            )
    for j, f in enumerate(freqs):
        out.append(
            f'<text x="{ox + j * cw + cw / 2}" y="{oy + ch * len(amps) + 14}" text-anchor="middle">{int(f)} Hz</text>'
        )
    ly = oy + ch * len(amps) + 36
    for k, (tag, label) in enumerate(
        [
            ("ok", "recovered"),
            ("ok~", "recovered, edge warning"),
            ("F!", "failed, flagged"),
            ("FS", "failed SILENTLY"),
        ]
    ):
        out.append(
            f'<rect x="{ox + k * 150}" y="{ly}" width="12" height="12" fill="{col[tag]}"/>'
        )
        out.append(f'<text x="{ox + k * 150 + 16}" y="{ly + 10}">{label}</text>')
    out.append(
        f'<text x="{ox}" y="{ly + 32}">Rule: max slew &lt; λ·sr = {lam * sr:,.0f} V/s (pure sine: peak·Hz &lt; {lam * sr / (2 * np.pi):,.0f}). '
        "Burst has a 0.4× harmonic at 2.1 f, so its limit is ~1.8× tighter.</text>"
    )
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


def run_failmap_report(
    out_dir: Path | str | None = None,
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
) -> tuple[list[FailCell], dict]:
    root = Path(__file__).resolve().parents[1]
    out = Path(out_dir) if out_dir else root / "artifacts" / "shockdaq"
    out.mkdir(parents=True, exist_ok=True)
    cells = run_failmap(lam=lam, sr=sr)
    summ = summarize(cells)
    report = {
        "slice": "ShockDAQ fail map (2026-10-07)",
        "lam_V": lam,
        "sr": sr,
        "ok_snr_db": OK_SNR_DB,
        "rule": "fold recovers iff max|Δx| < λ, i.e. max slew (V/s) < λ·sr",
        "summary": summ,
        "cells": [asdict(c) | {"silent_fail": c.silent_fail} for c in cells],
    }
    (out / "failmap.json").write_text(json.dumps(report, indent=2) + "\n")
    write_svg(cells, out / "failmap.svg", lam=lam, sr=sr)
    return cells, summ
