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
    EDGE_FRAC, edge_flag, inl_inverse, rail_hits, rail_mask, recover_blind, slip_flag,
)
from .foldaudio import fold_capture, max_sample_jump, snr_db
from .modulo import quantize_folded
from .shockdaq import DEFAULT_LAM_V, DEFAULT_SR

OK_SNR_DB = 60.0
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
    return [eval_cell(a, f, lam=lam, sr=sr, bits=bits, seed=seed) for a in amps for f in freqs]


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
            None if step is None else sum((c.max_dx_V < lam - step) == c.recovered_ok for c in cells)
        )
        rows.append(s)
    return {"lam_V": lam, "sr": sr, "seed": seed, "rows": rows}


def format_quant_sweep(sweep: dict) -> str:
    hdr = " bits  step(V)  ok  fail  rule  tight  flagged  SILENT  slipFA  edge-on-ok"
    lines = [hdr, "-" * len(hdr)]
    for r in sweep["rows"]:
        b = "ideal" if r["bits"] is None else f"{r['bits']:>5}"
        st = "     -" if r["step_V"] is None else f"{r['step_V']:>7.4f}"
        tight = "   -" if r["tight_rule_agrees"] is None else f"{r['tight_rule_agrees']:>4}"
        lines.append(f"{b:>5} {st:>8} {r['recovered_ok']:>3} {r['failed']:>5} {r['rule_agrees_with_outcome']:>5} "
                     f"{tight:>6} {r['fails_flagged']:>8} {r['fails_silent']:>7} {r['slip_false_alarms_on_ok']:>7} "
                     f"{r['edge_warnings_on_ok']:>11}")
    n = sweep["rows"][0]["cells"]
    lines.append(f"{n} cells per row. rule = plain slew rule matches outcome; tight = worst-case rule (λ−step) matches.")
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
    max_dx_V: float            # max |Δ| of the (noisy) input the fold actually saw
    max_dx_clean_V: float      # same, before noise was added
    predicted_ok: bool         # plain slew rule on the noisy input: max_dx < λ
    clean_rule_ok: bool        # slew rule on the noiseless burst (what a spec sheet would say)
    derated_ok: bool           # max_dx < λ(1 − 2|g| − |e| − |o| − π·inl): rule derated for fold errors
    recovered_ok: bool         # no unwrap slip: max|rec − truth| < λ
    err_peak_V: float          # max |rec − truth|
    peak_err_frac: float       # err_peak / true peak
    accurate: bool             # recovered_ok and peak_err_frac <= 1 %
    slip_flag: bool
    edge_flag: bool
    rail_hits: int = 0         # folded samples sitting at the ADC rails (clipped; visible in the capture)

    @property
    def silent_fail(self) -> bool:
        return (not self.recovered_ok) and not (self.slip_flag or self.edge_flag)

    @property
    def silent_inaccurate(self) -> bool:
        """Recovered with no slip but off by > 1 % of peak, and nothing flagged."""
        return self.recovered_ok and not self.accurate and not (self.slip_flag or self.edge_flag)

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
) -> NonIdealCell:
    """gain_cal = calibrated fold-step gain ĝ; inl_cal = calibrated INL harmonics
    (volts, calibrate.estimate_front_end). Defaults = uncalibrated recovery."""
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
    derate = 1.0 - 2.0 * abs(ni.gain_err) - abs(ni.thresh_err) - abs(ni.offset) - np.pi * abs(ni.inl)
    ok = bool(err < lam)
    frac = err / peak if peak > 0 else 0.0
    return NonIdealCell(
        config=ni.name, amp_V=amp, f_ring_Hz=f_ring, seed=seed, sigma_V=sigma,
        max_dx_V=dx, max_dx_clean_V=dx_clean,
        predicted_ok=bool(dx < lam), clean_rule_ok=bool(dx_clean < lam),
        derated_ok=bool(dx < lam * derate),
        recovered_ok=ok, err_peak_V=err, peak_err_frac=frac,
        accurate=bool(ok and frac <= NONIDEAL_OK_BAR_FRAC),
        slip_flag=slip_flag(rec, lam), edge_flag=edge_flag(y, lam),
        rail_hits=rail_hits(y, lam, bits=ni.bits),
    )


def default_nonideal_configs() -> list[NonIdeal]:
    """One-factor-at-a-time sweeps plus two combined rows."""
    cfgs = [NonIdeal("ideal")]
    cfgs += [NonIdeal(f"noise {s:g} dB", noise_snr_db=s) for s in (60, 40, 30, 20, 15, 10, 5, 0)]
    cfgs += [NonIdeal(f"gain {g:+.1%}", gain_err=g) for g in (-0.05, -0.01, 0.001, 0.01, 0.05)]
    cfgs += [NonIdeal(f"thresh {e:+.0%}", thresh_err=e) for e in (-0.10, -0.02, 0.02, 0.10)]
    cfgs += [NonIdeal(f"offset {o:+.0%}", offset=o) for o in (0.02, 0.10)]
    cfgs += [NonIdeal(f"inl {a:.0%}", inl=a) for a in (0.01, 0.02, 0.05)]
    cfgs += [
        NonIdeal("combo-mild", noise_snr_db=60, gain_err=0.001, thresh_err=0.005, offset=0.005, inl=0.002, bits=16),
        NonIdeal("combo-bad", noise_snr_db=40, gain_err=0.005, thresh_err=0.01, offset=0.01, inl=0.01, bits=12),
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
        "fails_flagged": sum(c.slip_flag or c.edge_flag for c in fails),
        "fails_silent": sum(c.silent_fail for c in cells),
        "slip_false_alarms_on_ok": sum(c.slip_flag for c in ok_cells),
        "edge_warnings_on_ok": sum(c.edge_flag for c in ok_cells),
        "accurate": sum(c.accurate for c in cells),
        "inaccurate_but_recovered": sum(c.recovered_ok and not c.accurate for c in cells),
        "silent_inaccurate": sum(c.silent_inaccurate for c in cells),
        "silent_inaccurate_no_rail": sum(c.silent_inaccurate_no_rail for c in cells),
        "median_peak_err_frac_on_ok": float(np.median([c.peak_err_frac for c in ok_cells])) if ok_cells else None,
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
        cells = [eval_nonideal_cell(a, f, ni, lam=lam, sr=sr, seed=sd, gain_cal=gc,
                                     inl_cal=tuple(inl_cal.get(ni.name, ())))
                 for sd in seeds for a in amps for f in freqs]
        s = summarize_nonideal(cells)
        s["config"] = ni.name
        s["params"] = {k: v for k, v in asdict(ni).items() if k != "name"}
        s["median_sigma_V"] = float(np.median([c.sigma_V for c in cells]))
        rows.append(s)
        all_cells.extend(cells)
    return {"lam_V": lam, "sr": sr, "seeds": list(seeds), "rows": rows, "cells": all_cells}


def format_nonideal_sweep(sweep: dict) -> str:
    hdr = ("config            ok  fail  rule  clean  derated  flagged  SILENT  slipFA  edge-on-ok  "
           "accurate  off>1%pk-unflagged")
    lines = [hdr, "-" * len(hdr)]
    for r in sweep["rows"]:
        lines.append(f"{r['config']:<16} {r['recovered_ok']:>4} {r['failed']:>5} {r['rule_agrees']:>5} "
                     f"{r['clean_rule_agrees']:>6} {r['derated_rule_agrees']:>8} {r['fails_flagged']:>8} "
                     f"{r['fails_silent']:>7} {r['slip_false_alarms_on_ok']:>7} {r['edge_warnings_on_ok']:>11} "
                     f"{r['accurate']:>9} {r['silent_inaccurate']:>12}")
    n = sweep["rows"][0]["cells"]
    lines.append(f"{n} cells per row ({len(sweep['seeds'])} seed(s)). rule = slew rule on the noisy input; "
                 "clean = rule on noiseless burst; derated = rule with λ shrunk by fold errors.")
    lines.append("ok = no unwrap slip (max error < λ); accurate = ok AND max error ≤ 1 % of peak; "
                 "off>1%pk-unflagged = recovered (no slip) but >1 % of peak off and unflagged (an accuracy limit, not an unwrap failure).")
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
    lines.append("ok = recovered blind (SNR≥60 dB); ok~ = recovered but edge warning; "
                 "F! = failed and flagged; FS = failed silently")
    return "\n".join(lines)


def write_svg(cells: list[FailCell], path: Path, *, lam: float, sr: int) -> None:
    """Dependency-free heatmap: cell colour = outcome, dashed line = slew rule (pure sine)."""
    amps = sorted({c.amp_V for c in cells})
    freqs = sorted({c.f_ring_Hz for c in cells})
    by = {(c.amp_V, c.f_ring_Hz): c for c in cells}
    cw, ch, ox, oy = 70, 40, 90, 50
    w, h = ox + cw * len(freqs) + 20, oy + ch * len(amps) + 90
    col = {"ok": "#3a9d5d", "ok~": "#9fd27a", "F!": "#e0a030", "FS": "#c0392b"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="11">',
           f'<text x="{ox}" y="20" font-size="13" font-weight="bold">ShockDAQ fold fail map — λ={lam:g} V, sr={sr} Hz, blind recovery</text>']
    for i, a in enumerate(reversed(amps)):
        y0 = oy + i * ch
        out.append(f'<text x="{ox-8}" y="{y0+ch/2+4}" text-anchor="end">{a:g} V</text>')
        for j, f in enumerate(freqs):
            c = by[(a, f)]
            tag = "ok" if c.recovered_ok else ("FS" if c.silent_fail else "F!")
            if c.recovered_ok and c.edge_flag:
                tag = "ok~"
            x0 = ox + j * cw
            out.append(f'<rect x="{x0}" y="{y0}" width="{cw-2}" height="{ch-2}" fill="{col[tag]}"/>')
            out.append(f'<text x="{x0+cw/2-1}" y="{y0+ch/2+4}" text-anchor="middle" fill="#fff">{c.snr_blind_db:.0f} dB</text>')
    for j, f in enumerate(freqs):
        out.append(f'<text x="{ox+j*cw+cw/2}" y="{oy+ch*len(amps)+14}" text-anchor="middle">{int(f)} Hz</text>')
    ly = oy + ch * len(amps) + 36
    for k, (tag, label) in enumerate([("ok", "recovered"), ("ok~", "recovered, edge warning"),
                                       ("F!", "failed, flagged"), ("FS", "failed SILENTLY")]):
        out.append(f'<rect x="{ox+k*150}" y="{ly}" width="12" height="12" fill="{col[tag]}"/>')
        out.append(f'<text x="{ox+k*150+16}" y="{ly+10}">{label}</text>')
    out.append(f'<text x="{ox}" y="{ly+32}">Rule: max slew &lt; λ·sr = {lam*sr:,.0f} V/s (pure sine: peak·Hz &lt; {lam*sr/(2*np.pi):,.0f}). '
               'Burst has a 0.4× harmonic at 2.1 f, so its limit is ~1.8× tighter.</text>')
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n")


def run_failmap_report(out_dir: Path | str | None = None, *, lam: float = DEFAULT_LAM_V,
                       sr: int = DEFAULT_SR) -> tuple[list[FailCell], dict]:
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
