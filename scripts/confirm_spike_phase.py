"""Confirmatory spike-phase re-run on fresh Paderborn records (NOTES #8k item a).

Usage: python scripts/confirm_spike_phase.py
-> artifacts/paderborn/spike-phase-confirm-metrics.json

Rules, seed and records are fixed in
``artifacts/paderborn/prereg-2026-10-28-phase-confirm.md``. Uses only the
SHA-256-pinned measurements _6.._10 of K001/KI04 already in the Paderborn
cache (no download). Exit status is 0 whenever the run completed.
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

BEARINGS = ("K001", "KI04")


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


def main() -> int:
    print("# prereg artifacts/paderborn/prereg-2026-10-28-phase-confirm.md")
    print(
        f"# seed {ps.CONFIRM_SEED}, null draws {ps.PHASE_NULL_DRAWS}, alpha {ps.ALPHA}"
    )
    print(
        f"# null-A gate 99th pct <= {ps.NULL_A_SCALE} * sqrt(ln100/N); C3 target {ps.C3_TARGET_DEG} deg"
    )
    rng = np.random.default_rng(ps.CONFIRM_SEED)
    recs, not_spiky = [], []
    for b in BEARINGS:
        for c in pb.CONDITIONS:
            for m in pb.CONFIRM_MEASUREMENTS:
                r = ps.phase_record(b, c, m, rng=rng)
                if r is None:
                    not_spiky.append(pb.member(b, c, m))
                    continue
                recs.append(r)
                print(
                    f"{r.record:<30} N {r.n_spikes:4d}  ref {r.ref_db:5.1f} dB "
                    f"{'ok ' if r.ref_valid else 'BAD'} depth {r.depth:.4f}  "
                    f"R {r.r:.3f}  mu {math.degrees(r.mu):+7.1f} deg  p {r.p:.1e}  "
                    f"±45° {r.frac45:.2f}  nullA99 {r.null_r99:.3f} / bar {ps.null_a_bar(r.n_spikes):.3f}"
                )
    print(f"not spiky (< {ps.SPIKY_MIN} spikes): {not_spiky or 'none'}")
    v = ps.confirm_verdicts(recs)
    print("\n[confirmation]\n" + json.dumps(v, indent=1))
    sub = {}
    for tag in ("N09", "N15"):
        sub[tag] = ps.confirm_verdicts([r for r in recs if r.condition.startswith(tag)])
        print(f"\n[{tag} subset]\n" + json.dumps(sub[tag], indent=1))
    caveat = None
    if "grand_mean_deg" in sub["N09"] and "grand_mean_deg" in sub["N15"]:
        d = ps.circ_dist_deg(sub["N09"]["grand_mean_deg"], sub["N15"]["grand_mean_deg"])
        caveat = d > 45.0
        print(f"N09 vs N15 grand-mean difference {d:.1f} deg -> caveat {caveat}")
    gm = v.get("grand_mean_deg")
    if gm is not None:
        print(
            f"grand mean {gm:+.1f} deg = {-gm / 360.0 * 10.0:.2f} ms before the ripple maximum"
        )
    print()
    for k in ("C1", "C2", "C3"):
        print(f"{v[k]:>13}  {k}")
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); vibration_1 + phase_current_1/2, 64 kHz",
        "prereg": "artifacts/paderborn/prereg-2026-10-28-phase-confirm.md",
        "verdicts": v,
        "n09_subset": sub["N09"],
        "n15_subset": sub["N15"],
        "n09_n15_caveat": caveat,
        "not_spiky": not_spiky,
        "records": [_row(r) for r in recs],
    }
    out = ROOT / "artifacts" / "paderborn" / "spike-phase-confirm-metrics.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
