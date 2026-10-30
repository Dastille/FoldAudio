"""K001 own spike-free level vs the KA04 bar (NOTES #8k d) -> artifacts/paderborn/k001-spike-free-metrics.json.

Usage: python scripts/k001_spike_free.py

Applies the rules fixed in ``artifacts/paderborn/prereg-2026-10-30-k001-spike-free.md``:
D0 (despike method control on KA04 with injected spikes), D1 (DS < B_c on the five
Table 18 LP10 misses), D2 (LP10 headroom >= DS on the 40 spiky K001/KI04 records).
LP10 headroom is read from the committed Table 18 metrics, not recomputed. Uses
cached, SHA-256-pinned files only. Exit status 0 whenever the run completed.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402


def main() -> int:
    bars = ps.HEADROOM_BAR_DB
    t18 = json.loads(
        (ROOT / "artifacts" / "paderborn" / "headroom-bar-metrics.json").read_text()
    )
    t18_by = {r["record"]: r for r in t18["records"]}
    print("# prereg artifacts/paderborn/prereg-2026-10-30-k001-spike-free.md")
    print(f"# bars B_c (dB): {bars}")
    rows, d0_rows = [], []
    for b in pb.BEARINGS:
        for c in pb.CONDITIONS:
            for m in pb.CONFIRM_MEASUREMENTS:
                name = pb.member(b, c, m)
                x = pb.load_vibration(pb.fetch(b, c, download=False, meas=m))
                d = ps.despike(x)
                ds = ps.despiked_headroom_db(x)
                t = t18_by[name]
                row = {
                    "record": name,
                    "bearing": b,
                    "condition": c,
                    "spikes": t["spikes"],
                    "spiky": t["spiky"],
                    "bar_db": bars[c],
                    "raw_headroom_db": t["raw_headroom_db"],
                    "lp10_headroom_db": t["lp10_headroom_db"],
                    "ds_db": ds,
                    "despike_modified": d.n_modified,
                    "despike_modified_frac": d.n_modified / len(x),
                    "despike_passes": d.passes,
                    "despike_converged": d.converged,
                }
                if b == "KA04":
                    d0 = ps.d0_row(x)
                    d0_rows.append({"record": name} | d0)
                    row["d0"] = d0
                rows.append(row)
                print(
                    f"{name:<34} spikes {t['spikes']:4d}  bar {bars[c]:4.2f}  "
                    f"raw {t['raw_headroom_db']:+6.2f}  DS {ds:+6.2f}  "
                    f"LP10 {t['lp10_headroom_db']:+6.2f}  mod {d.n_modified:4d} "
                    f"passes {d.passes}"
                    + (
                        f"  D0 err {row['d0']['abs_err_db']:.4f} dB"
                        if b == "KA04"
                        else ""
                    )
                )
    by = {r["record"]: r for r in rows}
    d0 = {
        "n": len(d0_rows),
        "max_abs_err_db": max(r["abs_err_db"] for r in d0_rows),
        "max_modified_frac": max(r["modified_frac"] for r in d0_rows),
        "all_converged": all(r["converged"] for r in d0_rows),
        "D0": ps.d0_verdict(d0_rows),
    }
    if d0["D0"] == "PASS":
        d1 = ps.d1_verdict(
            {k: v["ds_db"] for k, v in by.items()},
            {k: v["bar_db"] for k, v in by.items()},
        )
        spiky = [r for r in rows if r["spiky"] and r["bearing"] != "KA04"]
        d2 = ps.d2_verdict([(r["lp10_headroom_db"], r["ds_db"]) for r in spiky])
    else:
        d1 = {"D1": "UNTESTABLE"}
        d2 = {"D2": "UNTESTABLE"}
    d3: dict = {"median_db": {}, "k001_ds_at_or_above_bar": 0}
    for c in pb.CONDITIONS:
        med = {}
        for b, key in (
            ("K001", "ds_db"),
            ("KI04", "ds_db"),
            ("KA04", "raw_headroom_db"),
        ):
            med[f"{b}_{'raw' if b == 'KA04' else 'ds'}"] = statistics.median(
                r[key] for r in rows if r["bearing"] == b and r["condition"] == c
            )
        d3["median_db"][c] = med
    k001 = [r for r in rows if r["bearing"] == "K001"]
    d3["k001_ds_at_or_above_bar"] = sum(r["ds_db"] >= r["bar_db"] for r in k001)
    d3["k001_n"] = len(k001)
    spiky = [r for r in rows if r["spiky"]]
    d3["own_bar_lp10_misses_exploratory"] = [
        r["record"] for r in spiky if r["lp10_headroom_db"] < r["ds_db"]
    ]
    ki = [r for r in rows if r["bearing"] == "KI04"]
    # Validity check added after the run (exploratory): KI04 met the bar 20/20 after
    # LP10, so if DS < B_c is also common on KI04, D1 does not single out K001.
    d3["ki04_ds_below_bar_exploratory"] = sum(r["ds_db"] < r["bar_db"] for r in ki)
    d3["ki04_n"] = len(ki)
    d3["ds_range_spiky_db"] = [
        min(r["ds_db"] for r in spiky if r["bearing"] != "KA04"),
        max(r["ds_db"] for r in spiky if r["bearing"] != "KA04"),
    ]
    d3["max_modified_frac_all"] = max(r["despike_modified_frac"] for r in rows)
    d3["max_passes_all"] = max(r["despike_passes"] for r in rows)
    d3["all_converged"] = all(r["despike_converged"] for r in rows)
    d3["lp10_minus_ds_db_spiky"] = {
        "min": float(np.min([r["lp10_headroom_db"] - r["ds_db"] for r in spiky])),
        "median": float(np.median([r["lp10_headroom_db"] - r["ds_db"] for r in spiky])),
    }
    print(
        "\n# Diagnostic (exploratory): samples around the largest step left after despiking"
    )
    for b, c, m in (("K001", "N09_M07_F10", 6), ("KI04", "N15_M07_F10", 9)):
        x = pb.load_vibration(pb.fetch(b, c, download=False, meas=m))
        y = ps.despike(x).y
        j = int(np.argmax(np.abs(np.diff(y))))
        print(
            f"{pb.member(b, c, m)} step at {j}: raw {np.round(x[j - 3 : j + 5], 3).tolist()}"
        )
        print(f"{'':<34} despiked {np.round(y[j - 3 : j + 5], 3).tolist()}")
    for k, v in (("D0", d0), ("D1", d1), ("D2", d2), ("D3", d3)):
        print(f"\n[{k}]\n" + json.dumps(v, indent=1))
    out = ROOT / "artifacts" / "paderborn" / "k001-spike-free-metrics.json"
    out.write_text(
        json.dumps(
            {
                "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); measurements _6.._10, "
                "vibration_1, 64 kHz; LP10 headroom from headroom-bar-metrics.json",
                "prereg": "artifacts/paderborn/prereg-2026-10-30-k001-spike-free.md",
                "bars_db": bars,
                "D0": d0,
                "D1": d1,
                "D2": d2,
                "D3": d3,
                "records": rows,
            },
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
