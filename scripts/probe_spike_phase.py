"""Spike phase vs the 100 Hz current ripple (NOTES #8j) -> artifacts/paderborn/spike-phase-metrics.json.

Usage: python scripts/probe_spike_phase.py

Rules, reference, seed and nulls are fixed in
``artifacts/paderborn/prereg-2026-10-27-phase.md``. Uses only the SHA-256-pinned
records already in the Paderborn cache (no download). Verdicts come from the
held-out measurements _2.._5; measurement _1 (seen data) is printed as
exploratory only. Exit status is 0 whenever the run completed.
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
    }


def _print(r: ps.PhaseRecord) -> None:
    print(
        f"{r.record:<30} N {r.n_spikes:4d}  ref {r.ref_db:5.1f} dB "
        f"{'ok ' if r.ref_valid else 'BAD'} depth {r.depth:.4f}  "
        f"R {r.r:.3f}  mu {math.degrees(r.mu):+7.1f} deg  p {r.p:.1e}  "
        f"±45° {r.frac45:.2f}  nullA99 {r.null_r99:.3f}"
    )


def _set(meas_list) -> tuple[list[ps.PhaseRecord], list[str]]:
    rng = np.random.default_rng(ps.PHASE_SEED)
    recs, dropped = [], []
    for b in pb.BEARINGS:
        for c in pb.CONDITIONS:
            for m in meas_list:
                r = ps.phase_record(b, c, m, rng=rng)
                if r is None:
                    continue
                _print(r)
                if r.n_spikes < ps.SPIKY_MIN:
                    dropped.append(r.record)
                recs.append(r)
    return recs, dropped


def _summary(tag: str, v: dict) -> None:
    print(f"\n[{tag}]")
    print(json.dumps(v, indent=1))


def main() -> int:
    print("# prereg artifacts/paderborn/prereg-2026-10-27-phase.md (commit de4d54f)")
    print("# reference: phase of 95-105 Hz zero-phase band-pass of |i_s| (Clarke of")
    print("#   phase_current_1/2, means removed); 0 deg = ripple maximum")
    print(f"# seed {ps.PHASE_SEED}, null draws {ps.PHASE_NULL_DRAWS}, alpha {ps.ALPHA}")
    print("\n== CONFIRMATION: held-out measurements _2.._5, spiky records ==")
    held, dropped = _set(pb.HELDOUT_MEASUREMENTS)
    print(f"spiky but < {ps.SPIKY_MIN} spikes after edge trim: {dropped or 'none'}")
    v = ps.phase_verdicts(held)
    _summary("confirmation verdict inputs", v)
    n09 = [r for r in held if r.condition.startswith("N09")]
    n15 = [r for r in held if r.condition.startswith("N15")]
    v09 = ps.phase_verdicts(n09)
    v15 = ps.phase_verdicts(n15)
    _summary("N09 subset (f_e 60 Hz; reference cannot be motor-made)", v09)
    _summary("N15 subset", v15)
    caveat = None
    if "grand_mean_deg" in v09 and "grand_mean_deg" in v15:
        d = abs(
            math.degrees(
                np.angle(
                    np.exp(
                        1j * math.radians(v09["grand_mean_deg"] - v15["grand_mean_deg"])
                    )
                )
            )
        )
        caveat = d > 45.0
        print(f"N09 vs N15 grand-mean difference {d:.1f} deg -> caveat {caveat}")

    print("\n== EXPLORATORY (seen data): measurement _1, spiky records ==")
    seen, _ = _set((1,))
    vs = ps.phase_verdicts(seen)
    _summary("seen _1 (descriptive only, no verdict)", vs)

    print()
    for k in ("P1", "P2", "P3"):
        print(f"{v[k]:>13}  {k}")
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); vibration_1 + phase_current_1/2, 64 kHz",
        "prereg": "artifacts/paderborn/prereg-2026-10-27-phase.md",
        "verdicts": v,
        "n09_subset": v09,
        "n15_subset": v15,
        "n09_n15_caveat": caveat,
        "seen_meas1_exploratory": vs,
        "records": [_row(r) for r in held],
        "records_seen_meas1": [_row(r) for r in seen],
    }
    out = ROOT / "artifacts" / "paderborn" / "spike-phase-metrics.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
