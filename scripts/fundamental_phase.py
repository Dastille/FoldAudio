"""N15_M01 phase scatter vs the motor fundamental inside the reference band (NOTES #8k).

Usage: python scripts/fundamental_phase.py
-> artifacts/paderborn/fundamental-phase-metrics.json

Rules, seed and records are fixed in
``artifacts/paderborn/prereg-2026-11-02-n15m01-fundamental.md``. Uses only the
SHA-256-pinned K002 N15_M01_F10 / N09_M07_F10 measurements _6.._20 in the
Paderborn cache (no download), plus a labelled exploratory re-run on the
already-used K001 _11.._20. Exit status is 0 whenever the run completed.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402

PREREG = "artifacts/paderborn/prereg-2026-11-02-n15m01-fundamental.md"


def _row(f: ps.FundRecord) -> dict:
    o, r = f.orig, f.resid
    return {
        "record": o.record,
        "condition": o.condition,
        "meas": o.meas,
        "n_spikes_trimmed": o.n_spikes,
        "ref_line_db": o.ref_db,
        "ref_valid": o.ref_valid,
        "f_el_hz": f.f_el,
        "fundamental_share": f.share,
        "orig_r": o.r,
        "orig_mean_phase_deg": math.degrees(o.mu),
        "orig_null_a_r99": o.null_r99,
        "resid_r": r.r,
        "resid_mean_phase_deg": math.degrees(r.mu),
        "resid_rayleigh_p": r.p,
        "resid_null_a_r99": r.null_r99,
        "null_a_bar": ps.null_a_bar(o.n_spikes),
    }


def _line(f: ps.FundRecord) -> str:
    o, r = f.orig, f.resid
    return (
        f"{o.record:<30} N {o.n_spikes:4d}  ref {o.ref_db:5.1f} dB  f_el {f.f_el:6.2f}  "
        f"F {f.share:.2f}  orig R {o.r:.3f} mu {math.degrees(o.mu):+7.1f}  "
        f"resid R {r.r:.3f} mu {math.degrees(r.mu):+7.1f}  "
        f"nullA99 {o.null_r99:.3f}/{r.null_r99:.3f} bar {ps.null_a_bar(o.n_spikes):.3f}"
    )


def _run(bearing: str, meas, rng) -> tuple[dict[str, list[ps.FundRecord]], list[str]]:
    by: dict[str, list[ps.FundRecord]] = {c: [] for c in pb.FUND_CONDITIONS}
    not_spiky = []
    for c in pb.FUND_CONDITIONS:
        for m in meas:
            f = ps.fund_record(bearing, c, m, rng=rng)
            if f is None:
                not_spiky.append(pb.member(bearing, c, m))
                continue
            by[c].append(f)
            print(_line(f))
    print(f"not spiky: {not_spiky or 'none'}")
    return by, not_spiky


def _reading(v: dict) -> str:
    """Prereg amendment A reading (F1 descriptive only)."""
    if "FALSIFIED" in (v["F2"], v["F3"], v["F4"]):
        return "H_fund rejected"
    if (
        v["F0"] == "PASS"
        and v["F2"] == "HELD"
        and v["F5"] == "PASS"
        and v["F3"] in ("HELD", "UNTESTABLE")
        and v["F4"] == "HELD"
    ):
        return "H_fund supported"
    return "not settled"


def main() -> int:
    print(f"# prereg {PREREG}")
    print(f"# seed {ps.FUND_SEED}; conditions {pb.FUND_CONDITIONS}")
    print("\n[pre-registered: K002 _6.._20]")
    rng = np.random.default_rng(ps.FUND_SEED)
    by, not_spiky = _run("K002", pb.FUND_MEASUREMENTS, rng)
    v = ps.fund_verdicts(by["N15_M01_F10"], by["N09_M07_F10"])
    v["reading"] = _reading(v)
    print("\n[verdicts]\n" + json.dumps(v, indent=1))
    for x in ("F0", "Q", "F1", "F2", "F3", "F4", "F5", "reading"):
        print(f"{v[x]:>16}  {x}")

    print("\n[exploratory, already-used data: K001 _11.._20, same code]")
    ex_by, _ = _run(
        "K001", pb.REF_SNR_MEASUREMENTS, np.random.default_rng(ps.FUND_SEED)
    )
    ex = ps.fund_verdicts(ex_by["N15_M01_F10"], ex_by["N09_M07_F10"])
    ex_keys = (
        "median_share_n15_m01",
        "median_share_n09",
        "n15_m01_orig_r_between",
        "n15_m01_resid_r_between",
        "n15_m01_resid_grand_mean_deg",
        "n09_orig_r_between",
        "n09_orig_grand_mean_deg",
    )
    ex_out = {k: ex.get(k) for k in ex_keys}
    print(json.dumps(ex_out, indent=1))

    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); vibration_1 + phase_current_1/2, 64 kHz",
        "prereg": PREREG,
        "verdicts": v,
        "not_spiky": not_spiky,
        "records": [_row(f) for c in pb.FUND_CONDITIONS for f in by[c]],
        "exploratory_k001_11_20": ex_out,
        "exploratory_k001_records": [
            _row(f) for c in pb.FUND_CONDITIONS for f in ex_by[c]
        ],
    }
    out = ROOT / "artifacts" / "paderborn" / "fundamental-phase-metrics.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
