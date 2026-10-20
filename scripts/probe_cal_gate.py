"""NOTES #8d: one-tone calibration on the CWRU non-ideal sweep vs injection SNR.

Runs the 3,000-cell Table 12 sweep (13 CWRU records, 25 front ends) with the
calibration applied, at several calibration-tone SNRs, with and without the
residual acceptance gate (calibrate.CAL_MAX_RESID_FRAC). Needs the CWRU cache
(python -m foldcrypt shockdaq-real once). CPU only, ~40 s per row.

    python scripts/probe_cal_gate.py
"""

from __future__ import annotations

from foldcrypt import realdata as rd

KEYS = (
    "cal_rejected",
    "fallback",
    "silent_slip",
    "uncovered_samples",
    "trusted_inaccurate_kept",
    "trusted_inaccurate_fallback",
    "invisible_kept",
    "max_trusted_err_frac",
)


def main() -> None:
    base = rd.run_real_nonideal_sweep(download=False)["summary"]["total"]
    rows = [("uncalibrated", None, None, base)]
    for snr in (60.0, 50.0, 40.0, 20.0):
        for gate in (True, False):
            t = rd.run_real_nonideal_sweep(
                download=False, calibrate=True, cal_snr_db=snr, cal_gate=gate
            )["summary"]["total"]
            rows.append(("calibrated", snr, gate, t))
    print(
        f"{'run':<13} {'cal SNR':>7} {'gate':>5} {'rejected':>8} {'fallbk':>6} "
        f"{'silent':>6} {'uncov':>6} {'bad kept':>8} {'bad fb':>6} {'invis':>5} "
        f"{'max trusted err':>15}"
    )
    for name, snr, gate, t in rows:
        print(
            f"{name:<13} {'-' if snr is None else f'{snr:g} dB':>7} "
            f"{'-' if gate is None else ('on' if gate else 'off'):>5} "
            f"{t['cal_rejected']:>8} {t['fallback']:>6} {t['silent_slip']:>6} "
            f"{t['uncovered_samples']:>6} {t['trusted_inaccurate_kept']:>8} "
            f"{t['trusted_inaccurate_fallback']:>6} {t['invisible_kept']:>5} "
            f"{100 * t['max_trusted_err_frac']:>13.3f} %",
            flush=True,
        )


if __name__ == "__main__":
    main()
