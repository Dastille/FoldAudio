"""Run the Paderborn (KAt) 64 kHz sweep and write artifacts/paderborn/metrics.json.

Usage: python scripts/run_paderborn.py [--offline]

Needs SciPy and, for the first run, the ``unar`` tool plus about 530 MB of
download (three .rar archives from Zenodo record 15845309, MD5 checked).
Prints the per-record table, the summary, and the four pre-registered
predictions (artifacts/paderborn/prereg-2026-10-23.md) with HELD/FALSIFIED.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402


def predictions(sweep: dict) -> list[tuple[str, bool, str]]:
    """Evaluate the pre-registered predictions P1–P4 on a sweep."""
    s = sweep["summary"]
    h64 = [r["headroom_db"] for r in sweep["records"] if r["sr"] == pb.SR]
    h16 = [r["headroom_db"] for r in sweep["records"] if r["sr"] == pb.SR // 4]
    med = statistics.median(h64)
    pos64, pos16 = sum(h > 0 for h in h64), sum(h > 0 for h in h16)
    return [
        (
            "P1 rule predicts every cell",
            s["rule_correct"] == s["cells"],
            f"{s['rule_correct']}/{s['cells']}",
        ),
        (
            "P2 zero silent failures",
            s["silent_fail"] == 0,
            f"{s['silent_fail']} silent",
        ),
        (
            "P3 all 64 kHz records have headroom, median >= 7.5 dB",
            pos64 == len(h64) and med >= 7.5,
            f"{pos64}/{len(h64)} positive, median {med:+.2f} dB",
        ),
        (
            "P4 >= 7 of 12 records at 16 kHz have none",
            len(h16) - pos16 >= 7,
            f"{len(h16) - pos16}/{len(h16)} none",
        ),
    ]


def main() -> int:
    sweep = pb.run_sweep(download="--offline" not in sys.argv)
    for r in sweep["records"]:
        print(
            f"{r['record']:<26} {r['sr']:>5} Hz  peak {r['peak']:6.3f}  "
            f"Δ/peak {r['dx_over_peak']:.3f}  headroom {r['headroom_db']:+6.2f} dB  "
            f"kurt {r['kurtosis']:5.1f}  spikes {r['isolated_spikes']}"
        )
    print("summary:", sweep["summary"])
    for name, ok, detail in predictions(sweep):
        print(f"{'HELD' if ok else 'FALSIFIED':>9}  {name}: {detail}")
    out = ROOT / "artifacts" / "paderborn" / "metrics.json"
    pb.write_report(sweep, out)
    print(f"wrote {out.relative_to(ROOT)}")
    return 0 if sweep["summary"]["silent_fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
