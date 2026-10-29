"""Condition-matched headroom bar test (NOTES #8k c) -> artifacts/paderborn/headroom-bar-metrics.json.

Usage: python scripts/headroom_bar.py

Applies the rules fixed in ``artifacts/paderborn/prereg-2026-10-29-headroom-bar.md``:
B1 (bar stability on fresh spike-free KA04 _6.._10) and B2 (LP10 headroom >= B_c on
spiky K001/KI04 _6.._10). Uses cached, SHA-256-pinned files only. Exit status is 0
whenever the run completed; verdicts are results, not errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402


def _row(p: ps.RecordProbe) -> dict:
    row = {
        "record": p.record,
        "condition": p.condition,
        "spikes": p.n_spikes,
        "spiky": p.spiky,
        "bar_db": ps.HEADROOM_BAR_DB[p.condition],
        "raw_headroom_db": p.raw["headroom_db"],
        "raw_line_snr_db": p.raw["line_snr_db"],
    }
    for name in ps.FILTERS:
        f = p.filters[name]
        row[f"{name.lower()}_headroom_db"] = f["headroom_db"]
        row[f"{name.lower()}_line_snr_db"] = f["line_snr_db"]
        if p.spiky:
            for k in ("cells", "recovered", "silent_fail", "rule_correct"):
                row[f"{name.lower()}_{k}"] = f[k]
    return row


def main() -> int:
    bars = ps.HEADROOM_BAR_DB
    print("# prereg artifacts/paderborn/prereg-2026-10-29-headroom-bar.md")
    print(f"# bars B_c (dB): {bars}")
    probes = [
        ps.probe_record(b, c, download=False, meas=m)
        for b in pb.BEARINGS
        for c in pb.CONDITIONS
        for m in pb.CONFIRM_MEASUREMENTS
    ]
    for p in probes:
        lp = p.filters["LP10"]
        line = (
            f"{p.record:<34} spikes {p.n_spikes:4d}  bar {bars[p.condition]:4.2f}  "
            f"raw {p.raw['headroom_db']:+6.2f}  LP10 {lp['headroom_db']:+6.2f}"
        )
        if p.raw["line_snr_db"] is not None:
            line += (
                f"  line raw {p.raw['line_snr_db']:5.1f} LP10 {lp['line_snr_db']:5.1f}"
            )
        print(line)
    ka = [p for p in probes if p.bearing == "KA04"]
    controls = [(p.condition, p.raw["headroom_db"]) for p in ka if not p.spiky]
    excluded = [p.record for p in ka if p.spiky]
    b1 = ps.bar_stability_verdict(controls, bars) | {"excluded_spiky": excluded}
    b2 = ps.bar_lp10_verdict([p for p in probes if p.bearing != "KA04"], bars)
    lines_all = ps.bar_lp10_verdict(probes, bars)
    b2["lines_testable"] = lines_all["lines_testable"]
    b2["lines_lost"] = lines_all["lines_lost"]
    if lines_all["lines_lost"] and b2["B2"] != "UNTESTABLE":
        b2["B2"] = "FALSIFIED"
    print("\n[B1]\n" + json.dumps(b1, indent=1))
    print("\n[B2]\n" + json.dumps(b2, indent=1))
    out = ROOT / "artifacts" / "paderborn" / "headroom-bar-metrics.json"
    out.write_text(
        json.dumps(
            {
                "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); measurements _6.._10, "
                "vibration_1 + phase_current_1/2, 64 kHz",
                "prereg": "artifacts/paderborn/prereg-2026-10-29-headroom-bar.md",
                "bars_db": bars,
                "B1": b1,
                "B2": b2,
                "records": [_row(p) for p in probes],
            },
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
