"""Spike-free stretch headroom + burst-D0 re-check (prereg-2026-10-31-stretch-headroom.md)
-> artifacts/paderborn/stretch-headroom-metrics.json. Cached, SHA-256-pinned files only.
Exit status 0 whenever the run completed; verdicts are results, not errors."""

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


def main() -> int:
    # Part B: burst + single-sample D0 with the fixed despike, all 40 KA04 records.
    b_rows = {}
    for c in pb.CONDITIONS:
        for m in range(1, 11):
            x = load("KA04", c, m)
            r = ps.d0_burst_row(x)
            s = ps.d0_row(x)
            b_rows[pb.member("KA04", c, m)] = {"burst": r, "single": s}
            print(
                f"{pb.member('KA04', c, m):<34} burst err {r['abs_err_db']:.3f}  single err {s['abs_err_db']:.3f}"
            )

    def ok(r):
        return (
            r["converged"]
            and r["abs_err_db"] <= ps.D0_TOL_DB
            and r["modified_frac"] <= ps.D0_MAX_MODIFIED_FRAC
        )

    nb = sum(ok(v["burst"]) for v in b_rows.values())
    ns = sum(ok(v["single"]) for v in b_rows.values())
    partb = {
        "burst_pass": nb,
        "single_pass": ns,
        "n": len(b_rows),
        "B1": "HELD" if nb >= 38 and ns == len(b_rows) else "FALSIFIED",
    }
    print("\n[Part B]", partb)

    # Part A
    sh = {}
    for b in ("K001", "KA04", "KI04"):
        for c in pb.CONDITIONS:
            for m in range(1, 11):
                v, n = ps.stretch_headroom_db(load(b, c, m))
                sh[pb.member(b, c, m)] = {
                    "bearing": b,
                    "condition": c,
                    "meas": m,
                    "sh_db": v,
                    "tiles": n,
                }
    bars = {}
    for c in pb.CONDITIONS:
        vals = [
            sh[k]["sh_db"]
            for k in sh
            if sh[k]["bearing"] == "KA04"
            and sh[k]["condition"] == c
            and sh[k]["meas"] <= 5
        ]
        bars[c] = (
            math.floor(min(v for v in vals if v is not None) * 100) / 100
            if any(v is not None for v in vals)
            else None
        )
    s0 = []
    for c in pb.CONDITIONS:
        for m in range(6, 11):
            x = load("KA04", c, m)
            inj, _ = ps.inject_bursts(x)
            a, na = ps.stretch_headroom_db(x)
            bb, nb2 = ps.stretch_headroom_db(inj)
            err = None if a is None or bb is None else abs(a - bb)
            s0.append(
                {
                    "record": pb.member("KA04", c, m),
                    "clean": a,
                    "injected": bb,
                    "err_db": err,
                    "tiles": nb2,
                }
            )
    s0v = (
        "PASS"
        if all(
            r["err_db"] is not None
            and r["err_db"] <= ps.D0_TOL_DB
            and r["tiles"] >= ps.STRETCH_MIN_TILES
            for r in s0
        )
        else "FAIL"
    )

    def below(k):
        r = sh[k]
        return (
            r["sh_db"] is not None
            and bars[r["condition"]] is not None
            and r["sh_db"] < bars[r["condition"]]
        )

    k1 = sum(below(k) for k in ps.D1_MISSES)
    k001 = [k for k in sh if sh[k]["bearing"] == "K001" and sh[k]["meas"] >= 6]
    k2 = sum(below(k) for k in k001)
    s1 = {
        "below": k1,
        "n": 5,
        "S1": ps.count_verdict(k1, ps.S1_HELD_MIN, ps.S1_FAIL_MAX)
        if s0v == "PASS"
        else "UNTESTABLE",
    }
    s2 = {
        "below": k2,
        "n": len(k001),
        "S2": ps.count_verdict(k2, ps.S2_HELD_MIN, ps.S2_FAIL_MAX)
        if s0v == "PASS"
        else "UNTESTABLE",
    }
    s3 = {}
    for b in ("K001", "KA04", "KI04"):
        v = [
            sh[k]["sh_db"]
            for k in sh
            if sh[k]["bearing"] == b
            and sh[k]["meas"] >= 6
            and sh[k]["sh_db"] is not None
        ]
        t = [sh[k]["tiles"] for k in sh if sh[k]["bearing"] == b and sh[k]["meas"] >= 6]
        s3[b] = {
            "median_sh_db": statistics.median(v) if v else None,
            "testable": len(v),
            "median_tiles": statistics.median(t),
        }
    for k in ps.D1_MISSES:
        print(
            f"miss {k:<34} SH {sh[k]['sh_db']}  SB {bars[sh[k]['condition']]}  tiles {sh[k]['tiles']}"
        )
    print("\n[S0]", s0v, max((r["err_db"] or 0) for r in s0))
    print("[bars]", bars)
    print("[S1]", s1, "\n[S2]", s2, "\n[S3]", json.dumps(s3))
    out = ROOT / "artifacts" / "paderborn" / "stretch-headroom-metrics.json"
    out.write_text(
        json.dumps(
            {
                "prereg": "artifacts/paderborn/prereg-2026-10-31-stretch-headroom.md",
                "stretch_len": ps.STRETCH_LEN,
                "guard": ps.STRETCH_GUARD,
                "part_b": partb,
                "part_b_rows": b_rows,
                "stretch_bars_db": bars,
                "S0": {"verdict": s0v, "rows": s0},
                "S1": s1,
                "S2": s2,
                "S3": s3,
                "records": sh,
            },
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
