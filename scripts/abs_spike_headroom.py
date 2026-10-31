"""Absolute small-spike guard + same-tile control (prereg-2026-10-31c-k001-abs-spike.md)
-> artifacts/paderborn/abs-spike-metrics.json. Cached, SHA-256-pinned files only.
Exit 0 whenever the run completed; verdicts are results, not errors."""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402


def load(b, c, m):
    return pb.load_vibration(pb.fetch(b, c, download=False, meas=m))


def floor2(v):
    return math.floor(v * 100) / 100


def main() -> int:
    rec = {}
    for b in ("K001", "KA04", "KI04"):
        ms = range(1, 11) if b == "KA04" else range(6, 11)
        for c in pb.CONDITIONS:
            for m in ms:
                x = load(b, c, m)
                r = ps.abs_headroom(x, ps.ABS_T[c])
                r.update(bearing=b, condition=c, meas=m)
                if b == "KA04" and m <= 5:
                    r["abs_flags"] = int(len(ps.abs_flags(x, ps.ABS_T[c])))
                rec[pb.member(b, c, m)] = r
    bars = {}
    for key in ("ah_raw", "ah_lp"):
        bars[key] = {}
        for c in pb.CONDITIONS:
            v = [
                r[key]
                for r in rec.values()
                if r["bearing"] == "KA04" and r["condition"] == c and r["meas"] <= 5
            ]
            bars[key][c] = floor2(min(v)) if v and None not in v else None

    a0, a0s = [], []
    for c in pb.CONDITIONS:
        t = ps.ABS_T[c]
        for m in range(6, 11):
            x = load("KA04", c, m)
            inj, _ = ps.inject_bursts(x)
            good, _f = ps.abs_tiles(inj, t)
            lpx, lpi = ps.apply_filter(x, "LP10"), ps.apply_filter(inj, "LP10")
            row = {"record": pb.member("KA04", c, m), "tiles": len(good)}
            for k, (u, w) in {"raw": (x, inj), "lp": (lpx, lpi)}.items():
                p, q = ps.tile_headroom_db(u, good), ps.tile_headroom_db(w, good)
                row[k + "_err"] = None if p is None or q is None else abs(p - q)
            a0.append(row)
            amp = ps.A0S_AMP_X_T * t / float(np.max(np.abs(x)))
            sm, pos = ps.inject_bursts(x, amp_x_peak=amp)
            a0s.append(
                {
                    "record": row["record"],
                    "detect_frac": ps.burst_detect_frac(sm, pos, t),
                }
            )
    a0v = (
        "PASS"
        if all(
            r["tiles"] >= ps.STRETCH_MIN_TILES
            and r["raw_err"] is not None
            and r["raw_err"] <= ps.D0_TOL_DB
            and r["lp_err"] is not None
            and r["lp_err"] <= ps.D0_TOL_DB
            for r in a0
        )
        else "FAIL"
    )
    a0sv = "PASS" if all(r["detect_frac"] >= ps.A0S_MIN_FRAC for r in a0s) else "FAIL"
    gate = a0v == "PASS" and a0sv == "PASS"

    def lb(k):
        return bars["ah_lp"][rec[k]["condition"]]

    def below(k):
        r = rec[k]
        return r["ah_lp"] is not None and r["ah_lp"] < lb(k)

    k001 = [k for k, r in rec.items() if r["bearing"] == "K001"]
    ki04 = [k for k, r in rec.items() if r["bearing"] == "KI04"]
    a3_ok = [
        k
        for k in ps.D1_MISSES
        if rec[k]["ah_lp"] is not None
        and rec[k]["ah_lp_flagged"] is not None
        and rec[k]["ah_lp"] >= lb(k)
        and rec[k]["ah_lp"] - rec[k]["ah_lp_flagged"] >= ps.A3_MIN_DIFF_DB
    ]
    cnt = {
        "lp_misses": sum(below(k) for k in ps.D1_MISSES),
        "lp_k001": sum(below(k) for k in k001),
        "lp_ki04": sum(below(k) for k in ki04),
        "a3_misses": len(a3_ok),
        "k001_untestable": sum(rec[k]["tiles"] < ps.STRETCH_MIN_TILES for k in k001),
        "ki04_untestable": sum(rec[k]["tiles"] < ps.STRETCH_MIN_TILES for k in ki04),
    }
    if cnt["lp_misses"] >= 4 and cnt["lp_k001"] >= 15:
        a1 = "HELD"
    elif cnt["lp_misses"] <= 2 or cnt["lp_k001"] <= 10:
        a1 = "FALSIFIED"
    else:
        a1 = "INCONCLUSIVE"
    a2 = (
        "HELD"
        if cnt["lp_ki04"] <= 5
        else "FALSIFIED"
        if cnt["lp_ki04"] >= 10
        else "INCONCLUSIVE"
    )
    a3 = ps.count_verdict(cnt["a3_misses"], 4, 2)
    if not gate:
        a1 = a2 = a3 = "UNTESTABLE"
        outcome = "UNTESTABLE (gate FAIL); (d) stays open"
    elif a1 == "HELD" and a2 == "HELD":
        outcome = "K001 own level lower (explained)"
    elif a3 == "HELD":
        outcome = "small spikes explain the misses"
    else:
        outcome = None
    close_why = []
    if gate:
        if cnt["k001_untestable"] >= 10:
            close_why.append("K001 untestable >= 10/20")
        if a2 == "FALSIFIED":
            close_why.append("A2 FALSIFIED (KI04 equally low)")
        if a1 != "HELD" and a3 != "HELD":
            close_why.append("A1 and A3 both not HELD")
    closed = (
        bool(close_why)
        and outcome is None
        or (bool(close_why) and "explained" not in (outcome or ""))
    )
    if closed and outcome is None:
        outcome = "CLOSED: not separable on this rig"
    g5 = {}
    for b in ("K001", "KA04", "KI04"):
        rs = [r for r in rec.values() if r["bearing"] == b and r["meas"] >= 6]

        def med(k, rs=rs):
            x = [r[k] for r in rs if r[k] is not None]
            return statistics.median(x) if x else None

        g5[b] = {
            k: med(k) for k in ("ah_raw", "ah_lp", "ah_lp_flagged", "tiles", "coverage")
        }
    for k in k001 + ki04:
        r = rec[k]
        tag = " MISS" if k in ps.D1_MISSES else ""
        print(
            f"{k:<34} lp {r['ah_lp']}  flagged {r['ah_lp_flagged']}  LB {lb(k)}  "
            f"tiles {r['tiles']}/{r['flagged_tiles']}{tag}"
        )
    print(
        "[KA04 _1.._5 abs flags]",
        [r.get("abs_flags") for r in rec.values() if "abs_flags" in r],
    )
    print(
        "[A0]",
        a0v,
        max((r["raw_err"] or 0) for r in a0),
        max((r["lp_err"] or 0) for r in a0),
    )
    print("[A0s]", a0sv, min(r["detect_frac"] for r in a0s))
    print("[bars]", bars)
    print("[counts]", cnt)
    print("[A1]", a1, "[A2]", a2, "[A3]", a3)
    print("[close]", close_why, "->", outcome)
    print("[G5]", json.dumps(g5))
    out = (
        ROOT / "artifacts" / "paderborn" / "abs-spike-metrics.json"
    )  # amended run (v1 kept as abs-spike-v1-*)
    out.write_text(
        json.dumps(
            {
                "prereg": "artifacts/paderborn/prereg-2026-10-31c-k001-abs-spike.md",
                "abs_t": ps.ABS_T,
                "bars_db": bars,
                "A0": {"verdict": a0v, "rows": a0},
                "A0s": {"verdict": a0sv, "rows": a0s},
                "counts": cnt,
                "A1": a1,
                "A2": a2,
                "A3": a3,
                "close_reasons": close_why,
                "outcome": outcome,
                "medians": g5,
                "records": rec,
            },
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
