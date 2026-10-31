"""Guarded short-tile headroom, raw + LP10 (prereg-2026-10-31-k001-gap-headroom.md)
-> artifacts/paderborn/gap-headroom-metrics.json. Cached, SHA-256-pinned files only.
Exit 0 whenever the run completed; verdicts are results, not errors."""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

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
                r = ps.gap_headroom(load(b, c, m))
                r.update(bearing=b, condition=c, meas=m)
                rec[pb.member(b, c, m)] = r
    bars = {}
    for key in ("sh_raw", "sh_lp"):
        bars[key] = {}
        for c in pb.CONDITIONS:
            v = [
                r[key]
                for r in rec.values()
                if r["bearing"] == "KA04" and r["condition"] == c and r["meas"] <= 5
            ]
            bars[key][c] = floor2(min(v)) if v and None not in v else None

    g0 = []
    for c in pb.CONDITIONS:
        for m in range(6, 11):
            x = load("KA04", c, m)
            inj, _ = ps.inject_bursts(x)
            a, b2 = ps.gap_headroom(x), ps.gap_headroom(inj)
            row = {"record": pb.member("KA04", c, m), "tiles": b2["tiles"]}
            for k in ("sh_raw", "sh_lp"):
                row[k + "_err"] = (
                    None if a[k] is None or b2[k] is None else abs(a[k] - b2[k])
                )
            g0.append(row)
    g0v = (
        "PASS"
        if all(
            r["tiles"] >= ps.STRETCH_MIN_TILES
            and r["sh_raw_err"] is not None
            and r["sh_raw_err"] <= ps.D0_TOL_DB
            and r["sh_lp_err"] is not None
            and r["sh_lp_err"] <= ps.D0_TOL_DB
            for r in g0
        )
        else "FAIL"
    )

    def below(k, key):
        r = rec[k]
        bar = bars[key][r["condition"]]
        return r[key] is not None and bar is not None and r[key] < bar

    k001 = [k for k, r in rec.items() if r["bearing"] == "K001"]
    ki04 = [k for k, r in rec.items() if r["bearing"] == "KI04"]
    cnt = {
        "raw_misses": sum(below(k, "sh_raw") for k in ps.D1_MISSES),
        "raw_k001": sum(below(k, "sh_raw") for k in k001),
        "lp_misses": sum(below(k, "sh_lp") for k in ps.D1_MISSES),
        "lp_k001": sum(below(k, "sh_lp") for k in k001),
        "lp_ki04": sum(below(k, "sh_lp") for k in ki04),
    }
    gate = g0v == "PASS"

    def v(x):
        return x if gate else "UNTESTABLE"

    g1 = v(ps.count_verdict(cnt["raw_misses"], ps.S1_HELD_MIN, ps.S1_FAIL_MAX))
    g2 = v(ps.count_verdict(cnt["raw_k001"], ps.S2_HELD_MIN, ps.S2_FAIL_MAX))
    if cnt["lp_misses"] >= ps.G3_HELD_MISSES and cnt["lp_k001"] >= ps.G3_HELD_K001:
        g3 = "HELD"
    elif cnt["lp_misses"] <= ps.G3_FAIL_MISSES or cnt["lp_k001"] <= ps.G3_FAIL_K001:
        g3 = "FALSIFIED"
    else:
        g3 = "INCONCLUSIVE"
    g3 = v(g3)
    g4 = (
        "HELD"
        if cnt["lp_ki04"] <= ps.G4_HELD_MAX
        else "FALSIFIED"
        if cnt["lp_ki04"] >= ps.G4_FAIL_MIN
        else "INCONCLUSIVE"
    )
    g4 = v(g4)
    g5 = {}
    for b in ("K001", "KA04", "KI04"):
        rs = [r for r in rec.values() if r["bearing"] == b and r["meas"] >= 6]

        def med(k, rs=rs):
            x = [r[k] for r in rs if r[k] is not None]
            return statistics.median(x) if x else None

        g5[b] = {
            "median_sh_raw": med("sh_raw"),
            "median_sh_lp": med("sh_lp"),
            "median_tiles": med("tiles"),
            "median_own_peak_reject_frac": med("own_peak_reject_frac"),
            "testable": sum(r["sh_raw"] is not None for r in rs),
        }
    explained = gate and g3 == "HELD" and g4 == "HELD"
    for k in ps.D1_MISSES:
        r = rec[k]
        print(
            f"miss {k:<34} raw {r['sh_raw']} (SB {bars['sh_raw'][r['condition']]})  "
            f"lp {r['sh_lp']} (LB {bars['sh_lp'][r['condition']]})  tiles {r['tiles']}"
        )
    for k in k001 + ki04:
        r = rec[k]
        print(f"{k:<34} raw {r['sh_raw']}  lp {r['sh_lp']}  tiles {r['tiles']}")
    print(
        "[G0]",
        g0v,
        max((r["sh_raw_err"] or 0) for r in g0),
        max((r["sh_lp_err"] or 0) for r in g0),
    )
    print("[bars]", bars)
    print("[counts]", cnt)
    print("[G1]", g1, "[G2]", g2, "[G3]", g3, "[G4]", g4, "explained", explained)
    print("[G5]", json.dumps(g5))
    out = ROOT / "artifacts" / "paderborn" / "gap-headroom-metrics.json"
    out.write_text(
        json.dumps(
            {
                "prereg": "artifacts/paderborn/prereg-2026-10-31-k001-gap-headroom.md",
                "tile_len": ps.GAP_LEN,
                "guard": ps.STRETCH_GUARD,
                "bars_db": bars,
                "G0": {"verdict": g0v, "rows": g0},
                "counts": cnt,
                "G1": g1,
                "G2": g2,
                "G3": g3,
                "G4": g4,
                "G5": g5,
                "k001_explained": explained,
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
