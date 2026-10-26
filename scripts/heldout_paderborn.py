"""Paderborn held-out confirmation (NOTES #8i) -> artifacts/paderborn/heldout-metrics.json.

Usage: python scripts/heldout_paderborn.py [--download]

Runs the unchanged 2026-10-25 spike probe on measurements _2.._5 of the same
12 bearing x condition cells (48 SHA-256-pinned records) and applies the rules
fixed in ``artifacts/paderborn/prereg-2026-10-26-heldout.md``. Exit status is
0 whenever the run completed; verdicts are results, not errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn_spikes as ps  # noqa: E402


def main() -> int:
    probes = ps.run_heldout(download="--download" in sys.argv)
    rows = []
    for p in probes:
        lp = p.filters["LP10"]
        row = {
            "record": p.record,
            "spikes": p.n_spikes,
            "spiky": p.spiky,
            "raw_headroom_db": p.raw["headroom_db"],
            "lp10_headroom_db": lp["headroom_db"],
            "lp5_headroom_db": p.filters["LP5"]["headroom_db"],
            "med3_headroom_db": p.filters["MED3"]["headroom_db"],
            "raw_line_snr_db": p.raw["line_snr_db"],
            "lp10_line_snr_db": lp["line_snr_db"],
            "lp5_line_snr_db": p.filters["LP5"]["line_snr_db"],
        }
        line = (
            f"{p.record:<32} spikes {p.n_spikes:4d}  raw {p.raw['headroom_db']:+6.2f} dB  "
            f"LP10 {lp['headroom_db']:+6.2f}  LP5 {p.filters['LP5']['headroom_db']:+6.2f}"
        )
        if p.raw["line_snr_db"] is not None:
            line += (
                f"  line raw {p.raw['line_snr_db']:5.1f} LP10 {lp['line_snr_db']:5.1f} "
                f"LP5 {p.filters['LP5']['line_snr_db']:5.1f}"
            )
        if p.spiky:
            b = p.bands
            m = p.exploratory["mains100"]
            row |= {
                "mains100_p": m.p,
                "mains100_r": m.r_max,
                "pwm16k_p": b["pwm16k"].p,
                "fe_p": b["fe"].p,
                "h2_evidence": p.h2_evidence,
                "decoy_contaminated": p.decoy_contaminated,
                "lp10_cells": lp["cells"],
                "lp10_recovered": lp["recovered"],
                "lp10_silent": lp["silent_fail"],
                "lp10_rule_correct": lp["rule_correct"],
            }
            line += (
                f"\n{'':32} 100Hz R={m.r_max:.2f} p={m.p:.1e}  16k p={b['pwm16k'].p:.1e}  "
                f"fe p={b['fe'].p:.1e}  H2={p.h2_evidence} decoy={p.decoy_contaminated}  "
                f"LP10 rec {lp['recovered']}/{lp['cells']} silent {lp['silent_fail']} "
                f"rule {lp['rule_correct']}/{lp['cells']}"
            )
        print(line)
        rows.append(row)
    v = ps.heldout_verdicts(probes)
    print()
    print(json.dumps({k: val for k, val in v.items() if k != "filters"}, indent=1))
    for name, f in v["filters"].items():
        print(f"  {name}: {f}")
    for r in ("R1", "R1b", "R2", "R3", "R4"):
        print(f"{v[r]:>13}  {r}")
    out = ROOT / "artifacts" / "paderborn" / "heldout-metrics.json"
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); measurements _2.._5, vibration_1 + phase_current_1/2, 64 kHz",
        "prereg": "artifacts/paderborn/prereg-2026-10-26-heldout.md",
        "verdicts": v,
        "records": rows,
    }
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
