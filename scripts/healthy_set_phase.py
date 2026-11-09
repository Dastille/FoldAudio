"""N15_M01 phase scatter on the remaining healthy bearings K004–K006.

Usage: python scripts/healthy_set_phase.py
-> artifacts/paderborn/healthy-set-phase-metrics.json

Rules, seed and records are fixed in
``artifacts/paderborn/prereg-2026-11-08-healthy-set-phase.md``. Uses only the
SHA-256-pinned K004/K005/K006 N15_M01_F10 / N09_M07_F10 measurements _1.._10
in the Paderborn cache (no download). Exit status is 0 whenever the run completed.
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

PREREG = "artifacts/paderborn/prereg-2026-11-08-healthy-set-phase.md"
M01, N09 = pb.HEALTHY_SET_CONDITIONS


def _row(r: ps.PhaseRecord) -> dict:
    return {
        "record": r.record,
        "condition": r.condition,
        "meas": r.meas,
        "n_spikes_trimmed": r.n_spikes,
        "ref_line_db": r.ref_db,
        "ref_valid": r.ref_valid,
        "ripple_depth": r.depth,
        "r_ref": r.r,
        "mean_phase_deg": math.degrees(r.mu),
        "rayleigh_p": r.p,
        "frac_within_45deg": r.frac45,
        "null_a_r99": r.null_r99,
        "null_a_bar": ps.null_a_bar(r.n_spikes),
    }


def _line(r: ps.PhaseRecord) -> str:
    return (
        f"{r.record:<30} N {r.n_spikes:4d}  ref {r.ref_db:5.1f} dB "
        f"{'ok ' if r.ref_valid else 'BAD'} depth {r.depth:.4f}  "
        f"R {r.r:.3f}  mu {math.degrees(r.mu):+7.1f} deg  p {r.p:.1e}  "
        f"±45° {r.frac45:.2f}  nullA99 {r.null_r99:.3f} / bar {ps.null_a_bar(r.n_spikes):.3f}"
    )


def main() -> int:
    print(f"# prereg {PREREG}")
    print(f"# seed {ps.HEALTHY_SET_SEED}; bearings {pb.HEALTHY_SET_BEARINGS}")
    print(
        f"# conditions {pb.HEALTHY_SET_CONDITIONS}; measurements {pb.HEALTHY_SET_MEASUREMENTS}"
    )
    rng = np.random.default_rng(ps.HEALTHY_SET_SEED)
    per: dict[str, dict] = {}
    records: list[dict] = []
    not_spiky: list[str] = []
    for b in pb.HEALTHY_SET_BEARINGS:
        by: dict[str, list[ps.PhaseRecord]] = {c: [] for c in pb.HEALTHY_SET_CONDITIONS}
        for c in pb.HEALTHY_SET_CONDITIONS:
            for m in pb.HEALTHY_SET_MEASUREMENTS:
                r = ps.phase_record(b, c, m, rng=rng)
                if r is None:
                    not_spiky.append(pb.member(b, c, m))
                    continue
                by[c].append(r)
                records.append(_row(r))
                print(_line(r))
        per[b] = ps.k003_phase_verdicts(by[M01], by[N09], seed=ps.HEALTHY_SET_SEED)
        print(f"\n[{b}] Q3 {per[b]['Q3']}  C3n {per[b]['C3n']}  ({per[b]['reading']})")
        for k in (
            "n15_m01_r_between",
            "n15_m01_p_between",
            "n09_r_between",
            "n09_p_between",
        ):
            if k in per[b]:
                print(f"    {k} {per[b][k]:.4g}")
        print()
    s = ps.healthy_set_verdict(per)
    print(f"not spiky: {not_spiky or 'none'}")
    print("\n[set verdict]\n" + json.dumps(s, indent=1))

    doc = {
        "source": (
            "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); "
            "K004/K005/K006 vibration_1 + phase_current_1/2, 64 kHz"
        ),
        "prereg": PREREG,
        "set_verdict": s,
        "per_bearing": per,
        "not_spiky": not_spiky,
        "records": records,
    }
    out = ROOT / "artifacts" / "paderborn" / "healthy-set-phase-metrics.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
