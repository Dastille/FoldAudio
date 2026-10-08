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

ASSUMPTIONS (named): synthetic ringing burst (same shape family as
shockdaq.gen_impact_transient: fundamental + 0.4× at 2.1 f, noise 1.5 % λ);
no quantization; λ is a demo rail, not an OEM part. CPU only, numpy only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .blind_level import EDGE_FRAC, edge_flag, recover_blind, slip_flag  # noqa: F401 (re-export)
from .foldaudio import fold_capture, max_sample_jump, snr_db
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

    @property
    def silent_fail(self) -> bool:
        return (not self.recovered_ok) and not (self.slip_flag or self.edge_flag)


def eval_cell(amp: float, f_ring: float, *, lam: float = DEFAULT_LAM_V, sr: int = DEFAULT_SR) -> FailCell:
    x = ring_burst(sr, amp=amp, f_ring=f_ring, lam=lam)
    y = fold_capture(x, lam)
    rec, _k = recover_blind(y, lam, prior="quiet_window")
    dx = max_sample_jump(x)
    s = snr_db(x, rec)
    return FailCell(
        amp_V=amp,
        f_ring_Hz=f_ring,
        lam_V=lam,
        sr=sr,
        max_dx_V=dx,
        predicted_ok=bool(dx < lam),
        snr_blind_db=s,
        recovered_ok=bool(s >= OK_SNR_DB),
        slip_flag=slip_flag(rec, lam),
        edge_flag=edge_flag(y, lam),
    )


def run_failmap(
    amps=DEFAULT_AMPS, freqs=DEFAULT_FREQS, *, lam: float = DEFAULT_LAM_V, sr: int = DEFAULT_SR
) -> list[FailCell]:
    return [eval_cell(a, f, lam=lam, sr=sr) for a in amps for f in freqs]


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
