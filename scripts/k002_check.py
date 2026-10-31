"""K002 (second healthy bearing) further check (NOTES #8k item b).

Usage: python scripts/k002_check.py
-> artifacts/paderborn/k002-check-metrics.json

Rules and records are fixed in ``artifacts/paderborn/prereg-2026-10-31d-k002.md``.
Uses only the SHA-256-pinned K002 measurements _1.._5 in the Paderborn cache
(no download). Exit status is 0 whenever the run completed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402


def main() -> int:
    print("# prereg artifacts/paderborn/prereg-2026-10-31d-k002.md")
    print(f"# bars B_c {ps.HEADROOM_BAR_DB}")
    probes = []
    for c in pb.CONDITIONS:
        for m in pb.K002_MEASUREMENTS:
            p = ps.probe_record("K002", c, download=False, meas=m)
            probes.append(p)
            line = f"{p.record:<30} spikes {p.n_spikes:5d}  raw {p.raw['headroom_db']:+6.2f} dB  "
            line += f"LP10 {p.filters['LP10']['headroom_db']:+6.2f} dB  bar {ps.HEADROOM_BAR_DB[c]:.2f}"
            if p.spiky:
                line += (
                    f"  16k {'Y' if p.bands['pwm16k'].significant else 'n'}"
                    f"  100 {'Y' if p.exploratory['mains100'].significant else 'n'}"
                    f"  mech {'Y' if p.h2_evidence else 'n'}"
                )
            print(line)
    v = ps.k002_verdicts(probes)
    print("\n[verdicts]\n" + json.dumps(v, indent=1, default=str))
    for k in ("K0", "K1", "K2", "K3", "K4", "K5"):
        print(f"{v[k]:>13}  {k}")
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); K002 vibration_1 + phase currents, 64 kHz",
        "prereg": "artifacts/paderborn/prereg-2026-10-31d-k002.md",
        "verdicts": v,
        "records": [
            {
                "record": p.record,
                "condition": p.condition,
                "n_spikes": p.n_spikes,
                "spiky": p.spiky,
                "raw_headroom_db": p.raw["headroom_db"],
                "lp10_headroom_db": p.filters["LP10"]["headroom_db"],
            }
            for p in probes
        ],
    }
    out = ROOT / "artifacts" / "paderborn" / "k002-check-metrics.json"
    out.write_text(json.dumps(doc, indent=2, default=str) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
