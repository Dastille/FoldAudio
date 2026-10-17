"""Check artifacts/realdata/metrics.json against the CWRU numbers in the docs.

Run after `python -m foldcrypt shockdaq-real --cells` (needs the CWRU download,
so it is not part of CI). Compares the run with the whitepaper (§6.6, Tables
10-11) and docs/shockdaq-realdata.md at the precision they state. Exit code 1
on any mismatch.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Table 11: step/peak, extra range dB, lowest r recovered, clip SNR at r = 0.5,
# kurtosis true / clipped, crest true / clipped (r = 0.5).
TABLE11 = {
    "97": (0.42, 7.5, 0.5, 23.2, 2.8, 2.5, 4.2, 2.2),
    "109": (0.38, 8.3, 0.4, 19.5, 6.0, 4.7, 6.1, 3.2),
    "122": (0.35, 9.0, 0.4, 24.6, 3.1, 2.8, 4.9, 2.5),
    "135": (0.40, 7.9, 0.5, 15.8, 6.7, 4.9, 5.2, 2.8),
    "213": (0.37, 8.7, 0.4, 21.0, 4.2, 3.4, 5.3, 2.7),
    "226": (0.32, 9.8, 0.33, 29.7, 3.2, 3.0, 5.6, 2.8),
    "238": (0.40, 7.9, 0.5, 19.6, 20.8, 15.9, 11.5, 6.0),
}


def main() -> int:
    m = json.loads((ROOT / "artifacts" / "realdata" / "metrics.json").read_text())
    s = m["summary"]
    cells = m["cells"]
    results = []

    def chk(name, got, want):
        results.append(got == want)
        tag = "OK  " if got == want else "DIFF"
        print(f"  {tag} {name}: run={got} doc={want}")

    chk("cells", s["cells"], 120)
    chk("rule correct", s["rule_correct"], 120)
    chk("recovered", s["recovered"], 26)
    chk("failed", s["failed"], 94)
    chk("failures flagged", s["failed_flagged"], 94)
    chk("silent failures", s["silent_fail"], 0)
    chk("slip false alarms", s["slip_false_alarm"], 0)
    chk("edge conservative", s["edge_conservative"], 3)
    c48 = [c for c in cells if c["sr"] == 48000]
    c12 = [c for c in cells if c["sr"] == 12000]
    chk("48 kHz recovered", (sum(c["recovered"] for c in c48), len(c48)), (26, 42))
    chk("12 kHz failed", (sum(not c["recovered"] for c in c12), len(c12)), (78, 78))
    chk("every cell overloaded", all(c["lam"] < c["peak"] for c in cells), True)
    edge_ok = sorted(
        (c["record"], c["ratio"]) for c in cells if c["recovered"] and c["edge"]
    )
    chk(
        "edge on recovered",
        edge_ok,
        [("109@48k", 0.4), ("213@48k", 0.4), ("226@48k", 0.33)],
    )

    step48 = {
        c["record"]: c["max_dx"] / c["peak"]
        for c in cells
        if c["record"].endswith("@48k")
    }
    step12 = [c["max_dx"] / c["peak"] for c in cells if c["sr"] == 12000]
    chk(
        "48 kHz step/peak",
        (round(min(step48.values()), 2), round(max(step48.values()), 2)),
        (0.32, 0.42),
    )
    chk(
        "12 kHz step/peak", (round(min(step12), 2), round(max(step12), 2)), (1.03, 1.61)
    )
    extra = [20 * math.log10(1 / v) for v in step48.values()]
    chk(
        "48 kHz extra range dB",
        (round(min(extra), 1), round(max(extra), 1)),
        (7.5, 9.8),
    )

    for rec, want in TABLE11.items():
        cs = [c for c in cells if c["record"] == f"{rec}@48k"]
        h = next(c for c in cs if c["ratio"] == 0.5)
        st = step48[f"{rec}@48k"]
        got = (
            round(st, 2),
            round(20 * math.log10(1 / st), 1),
            min(c["ratio"] for c in cs if c["recovered"]),
            round(h["snr_clip_db"], 1),
            round(h["kurt_true"], 1),
            round(h["kurt_clip"], 1),
            round(h["crest_true"], 1),
            round(h["crest_clip"], 1),
        )
        chk(f"Table 11 row {rec}", got, want)
        exact = all(
            abs(c["kurt_fold"] - c["kurt_true"]) < 1e-9
            and abs(c["crest_fold"] - c["crest_true"]) < 1e-9
            for c in cs
            if c["recovered"]
        )
        chk(f"  {rec}: fold-recovered kurtosis/crest exact", exact, True)

    verdict = "ALL MATCH" if all(results) else "MISMATCH"
    print(f"RESULT: {verdict} ({sum(results)}/{len(results)} checks)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
