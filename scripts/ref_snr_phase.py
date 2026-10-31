"""K001 phase scatter vs current-reference SNR (NOTES #8k item a2).

Usage: python scripts/ref_snr_phase.py
-> artifacts/paderborn/ref-snr-phase-metrics.json

Rules, seed and records are fixed in
``artifacts/paderborn/prereg-2026-10-31d-k001-ref-snr.md``. Uses only the
SHA-256-pinned measurements _11.._20 of K001/KI04 in the Paderborn cache (no
download). Exit status is 0 whenever the run completed.
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
        "r_ref": r.r,
        "mean_phase_deg": math.degrees(r.mu),
        "null_a_r99": r.null_r99,
        "null_a_bar": ps.null_a_bar(r.n_spikes),
    }


def main() -> int:
    print("# prereg artifacts/paderborn/prereg-2026-10-31d-k001-ref-snr.md")
    print(
        f"# seed {ps.REF_SNR_SEED}, split {ps.REF_SNR_SPLIT_DB} dB, min bin {ps.REF_SNR_MIN_BIN}"
    )
    rng = np.random.default_rng(ps.REF_SNR_SEED)
    by: dict[str, list[ps.PhaseRecord]] = {"K001": [], "KI04": []}
    not_spiky = []
    for b in by:
        for c in pb.CONDITIONS:
            for m in pb.REF_SNR_MEASUREMENTS:
                r = ps.phase_record(b, c, m, rng=rng)
                if r is None:
                    not_spiky.append(pb.member(b, c, m))
                    continue
                by[b].append(r)
                print(
                    f"{r.record:<30} N {r.n_spikes:4d}  ref {r.ref_db:5.1f} dB  "
                    f"R {r.r:.3f}  mu {math.degrees(r.mu):+7.1f}  "
                    f"nullA99 {r.null_r99:.3f}/{ps.null_a_bar(r.n_spikes):.3f}"
                )
    print(f"not spiky: {not_spiky or 'none'}")
    v = ps.ref_snr_verdicts(by["K001"], by["KI04"])
    print("\n[verdicts]\n" + json.dumps(v, indent=1))
    per_cond = {}
    for c in pb.CONDITIONS:
        k = [r for r in by["K001"] if r.condition == c and r.usable]
        per_cond[c] = {
            "n": len(k),
            "ref_db_range": [min(r.ref_db for r in k), max(r.ref_db for r in k)]
            if k
            else None,
            "r_between": ps.between_stats(k)[0] if k else None,
            "n_low": sum(r.ref_db < v["split_db"] for r in k),
        }
    print("\n[exploratory: K001 per condition]\n" + json.dumps(per_cond, indent=1))
    for x in ("A0_null_a_ok", "A1", "A1b", "A2", "A3"):
        print(f"{str(v[x]):>13}  {x}")
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); vibration_1 + phase_current_1/2, 64 kHz",
        "prereg": "artifacts/paderborn/prereg-2026-10-31d-k001-ref-snr.md",
        "verdicts": v,
        "exploratory_k001_per_condition": per_cond,
        "not_spiky": not_spiky,
        "records": [_row(r) for r in by["K001"] + by["KI04"]],
    }
    out = ROOT / "artifacts" / "paderborn" / "ref-snr-phase-metrics.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
