"""K003 N15_M01 phase scatter check (NOTES #8k optional).

Usage: python scripts/k003_phase.py
-> artifacts/paderborn/k003-phase-metrics.json

Rules, seed and records are fixed in
``artifacts/paderborn/prereg-2026-11-06-k003-phase.md``. Uses only the
SHA-256-pinned K003 N15_M01_F10 / N09_M07_F10 measurements _1.._10 in the
Paderborn cache (no download). Exit status is 0 whenever the run completed.
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

PREREG = "artifacts/paderborn/prereg-2026-11-06-k003-phase.md"


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
    print(f"# seed {ps.K003_PHASE_SEED}; conditions {pb.K003_PHASE_CONDITIONS}")
    print(f"# measurements {pb.K003_PHASE_MEASUREMENTS}")
    rng = np.random.default_rng(ps.K003_PHASE_SEED)
    by: dict[str, list[ps.PhaseRecord]] = {c: [] for c in pb.K003_PHASE_CONDITIONS}
    not_spiky: list[str] = []
    for c in pb.K003_PHASE_CONDITIONS:
        for m in pb.K003_PHASE_MEASUREMENTS:
            r = ps.phase_record("K003", c, m, rng=rng)
            if r is None:
                not_spiky.append(pb.member("K003", c, m))
                continue
            by[c].append(r)
            print(_line(r))
    print(f"not spiky: {not_spiky or 'none'}")
    v = ps.k003_phase_verdicts(by["N15_M01_F10"], by["N09_M07_F10"])
    print("\n[verdicts]\n" + json.dumps(v, indent=1))
    for x in ("Q3", "C3n", "reading"):
        print(f"{v[x]!s:>16}  {x}")

    doc = {
        "source": (
            "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); "
            "K003 vibration_1 + phase_current_1/2, 64 kHz"
        ),
        "prereg": PREREG,
        "verdicts": v,
        "not_spiky": not_spiky,
        "records": [_row(r) for c in pb.K003_PHASE_CONDITIONS for r in by[c]],
    }
    out = ROOT / "artifacts" / "paderborn" / "k003-phase-metrics.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
