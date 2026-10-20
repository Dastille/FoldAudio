"""ShockDAQ front-end calibration (fold-step gain + INL) — close the unflagged-accuracy gap.

NOTES slice #7 (2026-10-12 weekday slice). The 2026-10-11 non-ideal sweep found
that a fold-step gain mismatch g (front end subtracts 2λ(1+g) per wrap, recovery
assumes 2λ) never causes a silent unwrap failure, but leaves a bounded,
UNFLAGGED staircase error of 2λ·g per wrap crossed. Flags can't catch it; only
calibration can.

Method (factory / service calibration, named ASSUMPTIONS):
1. Inject a known slow test tone (default 159.2 Hz — the usual accelerometer
   reference frequency — at 4λ peak, 1 s) electrically at the DAQ input, so the
   front end folds it several times per cycle. Frequency is known; amplitude,
   phase and DC are not.
2. Itoh-unwrap the folded record with the nominal 2λ step and count wraps M[n].
   With gain error the unwrap is  r = x − 2λ·g·M  exactly.
3. Fit  r ≈ a·sin(ωt) + b·cos(ωt) + c − 2λ·g·M + Σ_k α_k·sin(kπ·y/λ)  (k=1..3)
   by linear least squares, excluding samples sitting at the ADC rails (gain
   error pushes a few folded values past ±λ, where they clip). ĝ is the M
   coefficient; α_k is the INL bow. Without the INL terms an INL bow of a
   leaks almost 1:1 into ĝ (inl 5 % → ĝ ≈ +4.7 %), so they are not optional.
4. Recovery: undo INL on the folded samples (blind_level.inl_inverse), then
   blind_level.recover_blind(fold_gain=ĝ): wraps are still detected with the 2λ
   rule but undone with the calibrated step 2λ(1+ĝ).

Honest limits (measured, see docs/shockdaq-failmap.md):
* Needs a clean injected tone: residual |ĝ−g| ≤ 1e-4 at ≥ 60 dB tone SNR, but
  ~3e-3 at 40 dB (noise chatter near the wrap thresholds) and nonsense at 20 dB
  (Itoh itself fails). Electrical injection on a real DAQ is far above 60 dB.
* Calibrates gain + INL. Wrap-threshold error is not modelled; offset is
  absorbed (a plain ADC has it too).
* What calibration CAN'T fix: samples the gain error pushed past the ADC rail
  are clipped — their value is gone. For g > 0 that happens right after every
  wrap, so a +5 % fold step stays inaccurate after calibration. Those samples
  are visible in the capture (rail_hits), so they are flagged, not silent.
  Local interpolation repair was tried and made fast bursts worse; rejected.
* Blind in-situ estimation from the impact burst itself was tried and rejected
  (biased by ~4 % — the signal moves too much between samples).
* Synthetic only; λ = 5 V is a demo rail, not an OEM part. numpy, CPU only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .blind_level import rail_mask
from .failmap import (
    DEFAULT_AMPS,
    DEFAULT_FREQS,
    NONIDEAL_SEEDS,
    NonIdeal,
    nonideal_fold,
    run_nonideal_sweep,
)
from .shockdaq import DEFAULT_LAM_V, DEFAULT_SR
from .unfold_detect import itoh_unwrap

CAL_FREQ_HZ = 159.2
CAL_AMP_LAMS = 4.0
CAL_DUR_S = 1.0
CAL_TARGET_ABS_ERR = 1e-3  # NOTES #7 target: residual ≤ 0.1 % (absolute, in g)
# Acceptance gate (NOTES #8d, 2026-10-20): reject a calibration whose fit residual
# RMS exceeds this fraction of λ. Measured on the 25 front ends x 48/12 kHz x 3
# seeds (white injection noise): resid/λ ≈ 2.8e-3 at 60 dB (worst |ĝ−g| 5.8e-4,
# meets target), ≈ 8.9e-3 at 50 dB (worst |ĝ−g| 3.9e-3, misses). On the CWRU
# records an accepted-but-noisy calibration is worse than none: at 40 dB it raised
# invisible >1 % errors from 57 to 216, at 20 dB it produced 4 silent slips.
CAL_MAX_RESID_FRAC = 5e-3


def cal_tone(
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    *,
    amp_lams: float = CAL_AMP_LAMS,
    f: float = CAL_FREQ_HZ,
    duration_s: float = CAL_DUR_S,
    phase: float = 0.3,
    noise_snr_db: float | None = None,
    seed: int = 0,
) -> np.ndarray:
    """Known-frequency calibration sine at amp_lams·λ peak (+ optional white noise)."""
    t = np.arange(int(sr * duration_s)) / sr
    x = amp_lams * lam * np.sin(2 * np.pi * f * t + phase)
    if noise_snr_db is not None:
        sigma = np.sqrt(np.mean(x**2)) / 10 ** (noise_snr_db / 20.0)
        x = x + sigma * np.random.default_rng(seed).standard_normal(len(x))
    return x


INL_HARMONICS = 3


@dataclass
class FrontEndCal:
    g_hat: float
    inl_coefs: tuple  # α_1..α_K in volts (INL bow harmonics on the folded value)
    wraps: int  # wrap events in the calibration record
    used: int  # samples used in the fit (rail-clipped ones excluded)
    resid_rms_V: float  # fit residual (noise + unmodelled errors)

    def accepted(self, lam: float, max_resid_frac: float = CAL_MAX_RESID_FRAC) -> bool:
        """True if the fit residual is small enough to trust ĝ and the INL terms.

        A rejected calibration must not be applied: recover uncalibrated instead
        (bounded, documented gain/INL error) and report the channel as uncalibrated.
        """
        return bool(np.isfinite(self.resid_rms_V)) and (
            self.resid_rms_V <= max_resid_frac * lam
        )


def estimate_front_end(
    y_folded: np.ndarray,
    lam: float,
    *,
    f: float = CAL_FREQ_HZ,
    sr: int = DEFAULT_SR,
    bits: int | None = None,
    inl_harmonics: int = INL_HARMONICS,
) -> FrontEndCal:
    """Estimate fold-step gain error g (+ INL bow) from a folded known-frequency tone."""
    y = np.asarray(y_folded, dtype=float)
    r = itoh_unwrap(y, lam)
    m = np.round((r - y) / (2.0 * lam))
    keep = ~rail_mask(y, lam, bits=bits)
    t = np.arange(len(y)) / sr
    w = 2 * np.pi * f
    cols = [np.sin(w * t), np.cos(w * t), np.ones_like(t), -2.0 * lam * m]
    cols += [np.sin(k * np.pi * y / lam) for k in range(1, inl_harmonics + 1)]
    A = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(A[keep], r[keep], rcond=None)
    resid = r[keep] - A[keep] @ coef
    return FrontEndCal(
        g_hat=float(coef[3]),
        inl_coefs=tuple(float(c) for c in coef[4:]),
        wraps=int(np.count_nonzero(np.diff(m))),
        used=int(np.count_nonzero(keep)),
        resid_rms_V=float(np.sqrt(np.mean(resid**2))),
    )


def calibrate_config(
    ni: NonIdeal,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    *,
    cal_snr_db: float | None = 60.0,
    seed: int = 0,
) -> FrontEndCal:
    """Run the calibration tone through front end `ni` and estimate its gain error.

    The tone gets its own injection noise (cal_snr_db) instead of ni's sensor
    noise: calibration is electrical, the accelerometer is not in the loop.
    """
    x = cal_tone(lam, sr, noise_snr_db=cal_snr_db, seed=seed)
    front = NonIdeal(
        ni.name, None, ni.gain_err, ni.thresh_err, ni.offset, ni.inl, ni.bits
    )
    y = nonideal_fold(x, lam, front)
    return estimate_front_end(y, lam, sr=sr, bits=ni.bits)


def default_cal_configs() -> list[NonIdeal]:
    """Ideal + gain + INL rows from the 2026-10-11 sweep + the two combo rows."""
    from .failmap import default_nonideal_configs

    return [
        c
        for c in default_nonideal_configs()
        if c.gain_err or c.inl or c.name == "ideal"
    ]


def run_calibration_sweep(
    configs: list[NonIdeal] | None = None,
    amps=DEFAULT_AMPS,
    freqs=DEFAULT_FREQS,
    *,
    seeds=NONIDEAL_SEEDS,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
    cal_snr_db: float | None = 60.0,
) -> dict:
    """Calibrate each config, then re-run the burst grid with and without ĝ."""
    configs = configs if configs is not None else default_cal_configs()
    cals = {
        ni.name: calibrate_config(ni, lam, sr, cal_snr_db=cal_snr_db) for ni in configs
    }
    before = run_nonideal_sweep(configs, amps, freqs, seeds=seeds, lam=lam, sr=sr)
    after = run_nonideal_sweep(
        configs,
        amps,
        freqs,
        seeds=seeds,
        lam=lam,
        sr=sr,
        gain_cal={k: v.g_hat for k, v in cals.items()},
        inl_cal={k: v.inl_coefs for k, v in cals.items()},
    )
    rows = []
    for ni, b, a in zip(configs, before["rows"], after["rows"]):
        c = cals[ni.name]
        rows.append(
            {
                "config": ni.name,
                "g_true": ni.gain_err,
                "g_hat": c.g_hat,
                "g_abs_err": abs(c.g_hat - ni.gain_err),
                "inl_true": ni.inl,
                "inl_hat": c.inl_coefs[0] / lam if c.inl_coefs else 0.0,
                "cal_wraps": c.wraps,
                "cells": b["cells"],
                "accurate_before": b["accurate"],
                "accurate_after": a["accurate"],
                "silent_inaccurate_before": b["silent_inaccurate"],
                "silent_inaccurate_after": a["silent_inaccurate"],
                "invisible_inaccurate_before": b["silent_inaccurate_no_rail"],
                "invisible_inaccurate_after": a["silent_inaccurate_no_rail"],
                "median_err_frac_before": b["median_peak_err_frac_on_ok"],
                "median_err_frac_after": a["median_peak_err_frac_on_ok"],
                "fails_silent_after": a["fails_silent"],
                "slip_false_alarms_after": a["slip_false_alarms_on_ok"],
            }
        )
    return {
        "lam_V": lam,
        "sr": sr,
        "cal_freq_Hz": CAL_FREQ_HZ,
        "cal_amp_lams": CAL_AMP_LAMS,
        "cal_snr_db": cal_snr_db,
        "seeds": list(seeds),
        "rows": rows,
    }


def run_cal_snr_limit(
    snrs=(None, 80.0, 60.0, 40.0, 20.0),
    gains=(-0.05, -0.01, -0.001, 0.001, 0.01, 0.05),
    bits=(None, 16, 12),
    seeds=(1, 2, 3),
    *,
    lam: float = DEFAULT_LAM_V,
    sr: int = DEFAULT_SR,
) -> list[dict]:
    """Worst |ĝ−g| vs calibration-tone SNR (over gains x bit depths x seeds)."""
    out = []
    for s in snrs:
        worst = 0.0
        for g in gains:
            for b in bits:
                for sd in seeds:
                    y = nonideal_fold(
                        cal_tone(lam, sr, noise_snr_db=s, seed=sd),
                        lam,
                        NonIdeal(gain_err=g, bits=b),
                    )
                    worst = max(
                        worst, abs(estimate_front_end(y, lam, sr=sr, bits=b).g_hat - g)
                    )
        out.append(
            {
                "cal_snr_db": s,
                "worst_abs_err": worst,
                "meets_target": worst <= CAL_TARGET_ABS_ERR,
            }
        )
    return out


def format_calibration(sweep: dict, limit: list[dict] | None = None) -> str:
    hdr = (
        "config         g_true    g_hat   |g err|  inl  inl_hat  accurate before→after  "
        "off>1%pk unflagged before→after  ...with no rail hit before→after  median err/peak before→after"
    )
    lines = [hdr, "-" * len(hdr)]
    for r in sweep["rows"]:
        lines.append(
            f"{r['config']:<13} {r['g_true']:+.4f} {r['g_hat']:+.5f} {r['g_abs_err']:.1e} "
            f"{r['inl_true']:.3f} {r['inl_hat']:+.4f}  {r['accurate_before']:>4} → {r['accurate_after']:<4}/{r['cells']}"
            f"          {r['silent_inaccurate_before']:>4} → {r['silent_inaccurate_after']:<4}"
            f"                     {r['invisible_inaccurate_before']:>4} → {r['invisible_inaccurate_after']:<4}"
            f"             {r['median_err_frac_before']:.2e} → {r['median_err_frac_after']:.2e}"
        )
    lines.append(
        f"cal tone {sweep['cal_freq_Hz']} Hz at {sweep['cal_amp_lams']:g}λ, 1 s, injected at "
        f"{sweep['cal_snr_db']} dB SNR. accurate = no slip AND max error ≤ 1 % of peak. "
        "'with no rail hit' = unflagged >1 %-off cells with NO rail-clipped sample in the capture (truly invisible)."
    )
    if limit:
        lines.append(
            "cal-tone SNR limit (worst |ĝ−g| over gains ±0.1–5 %, ideal/16/12-bit, 3 seeds; target ≤ 1e-3):"
        )
        for row in limit:
            s = (
                "noiseless"
                if row["cal_snr_db"] is None
                else f"{row['cal_snr_db']:g} dB"
            )
            lines.append(
                f"  {s:>9}: {row['worst_abs_err']:.1e}  {'meets' if row['meets_target'] else 'MISSES'}"
            )
    return "\n".join(lines)
