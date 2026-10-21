"""Check the CWRU numbers in the docs against the committed metrics files.

Covers the whitepaper's Section 6.6 Tables 10-13 and docs/shockdaq-realdata.md,
at the precision the docs state. Exit code 1 on any mismatch.

    python scripts/check_cwru_numbers.py              # committed JSON vs docs
    python scripts/check_cwru_numbers.py --recompute  # + verify .mat SHA-256s,
        re-run the sweeps from the cache and diff against the committed JSON
    python scripts/check_cwru_numbers.py --recompute --table13-all
        # + re-run every Table 13 row (8 extra sweeps, ~40 s each)

--recompute needs the CWRU cache (python -m foldcrypt shockdaq-real once) and
SciPy, so it is not part of CI. It never writes to artifacts/.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "artifacts" / "realdata"
FLOAT_TOL = 1e-9

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

# Table 13: (cal SNR dB, gate) -> rejected, fallback, silent slip, uncovered
# samples, bad kept, bad fallback, invisible, largest trusted error (% of peak).
TABLE13_UNCAL = (None, 2492, 0, 0, 145, 50, 57, 8.000)
TABLE13 = {
    (60.0, True): (0, 2489, 0, 0, 0, 0, 0, 0.037),
    (60.0, False): (None, 2489, 0, 0, 0, 0, 0, 0.037),
    (50.0, True): (3000, 2492, 0, 0, 145, 50, 57, 8.000),
    (50.0, False): (None, 2488, 0, 0, 0, 0, 0, 0.467),
    (40.0, True): (3000, 2492, 0, 0, 145, 50, 57, 8.000),
    (40.0, False): (None, 2476, 0, 0, 524, 19, 216, 4.850),
    (20.0, True): (3000, 2492, 0, 0, 145, 50, 57, 8.000),
    (20.0, False): (None, 2996, 4, 9199, 4, 2465, 4, 142.371),
}


class Checker:
    def __init__(self) -> None:
        self.results: list[bool] = []

    def __call__(self, name: str, got: object, want: object) -> None:
        ok = got == want
        self.results.append(ok)
        print(f"  {'OK  ' if ok else 'DIFF'} {name}: run={got} doc={want}")

    def section(self, title: str) -> None:
        print(f"## {title}")


def check_tables_10_11(m: dict, chk: Checker) -> None:
    s = m["summary"]
    cells = m["cells"]
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


def table13_row(t: dict, gated: bool | None) -> tuple:
    return (
        t["cal_rejected"] if gated else None,
        t["fallback"],
        t["silent_slip"],
        t["uncovered_samples"],
        t["trusted_inaccurate_kept"],
        t["trusted_inaccurate_fallback"],
        t["invisible_kept"],
        round(100 * t["max_trusted_err_frac"], 3),
    )


def check_table12(m: dict, chk: Checker) -> None:
    t = m["summary"]["total"]
    by = m["summary"]["by_config"]
    cells = m["cells"]
    chk("cells", t["cells"], 3000)
    chk("configurations", len(by), 25)
    chk("fallback", t["fallback"], 2492)
    chk(
        "ideal front end fallback",
        (by["ideal"]["fallback"], by["ideal"]["cells"]),
        (97, 120),
    )
    chk("kept reconstruction", t["kept_unwrap"], 508)
    chk(
        "kept cells all at 48 kHz",
        all(c["sr"] == 48000 for c in cells if not c["fallback"]),
        True,
    )
    chk("silent slip", t["silent_slip"], 0)
    chk("uncovered samples (event | rail mask)", t["uncovered_samples"], 0)
    chk("fallback cells uncovered", t["fallback_cells_uncovered"], 0)
    chk("bad kept", t["trusted_inaccurate_kept"], 145)
    inv = {k: v["invisible_kept"] for k, v in by.items() if v["invisible_kept"]}
    chk("invisible", t["invisible_kept"], 57)
    chk(
        "invisible by config",
        inv,
        {"gain -1.0%": 16, "gain -5.0%": 16, "inl 2%": 11, "inl 5%": 14},
    )
    badfb = {
        k: v["trusted_inaccurate_fallback"]
        for k, v in by.items()
        if v["trusted_inaccurate_fallback"]
    }
    chk("bad fallback", t["trusted_inaccurate_fallback"], 50)
    chk("bad fallback by config", badfb, {"inl 2%": 7, "inl 5%": 43})
    fb_err = max(c["trusted_err_frac"] for c in cells if c["fallback"])
    chk(
        "largest trusted error on fallback (% of peak, 1 dp)",
        round(100 * fb_err, 1),
        3.9,
    )
    chk(
        "largest trusted error (% of peak)",
        round(100 * t["max_trusted_err_frac"], 1),
        8.0,
    )
    chk(
        "uncalibrated error at |g| = 1 / 5 %, INL 5 % (% of peak)",
        tuple(
            round(
                100 * max(by[a]["max_trusted_err_frac"], by[b]["max_trusted_err_frac"]),
                1,
            )
            for a, b in (
                ("gain -1.0%", "gain +1.0%"),
                ("gain -5.0%", "gain +5.0%"),
                ("inl 5%", "inl 5%"),
            )
        ),
        (1.6, 8.0, 4.0),
    )
    chk(
        "median masked on fallback, every config",
        all(v["median_masked_frac_fallback"] == 1.0 for v in by.values()),
        True,
    )
    low = min((c for c in cells if c["fallback"]), key=lambda c: c["masked_frac"])
    chk(
        "lowest masked fallback cell",
        (round(100 * low["masked_frac"], 1), low["record"]),
        (6.2, "238@48k"),
    )
    chk("Table 13 uncalibrated row", table13_row(t, None), TABLE13_UNCAL)


def check_table13_committed(m: dict, chk: Checker) -> None:
    chk("calibrated", m["calibrated"], True)
    chk("cal SNR dB", m["cal_snr_db"], 60.0)
    chk("cells", m["summary"]["total"]["cells"], 3000)
    chk(
        "Table 13 row 60 dB gate on",
        table13_row(m["summary"]["total"], True),
        TABLE13[(60.0, True)],
    )


def _diff(a: object, b: object, path: str, out: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: present in only one side")
            else:
                _diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out)
    elif (
        isinstance(a, float) and isinstance(b, (int, float)) and not isinstance(b, bool)
    ):
        if not math.isclose(a, b, rel_tol=FLOAT_TOL, abs_tol=FLOAT_TOL):
            out.append(f"{path}: {a!r} vs {b!r}")
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}")


def json_roundtrip(write, sweep: dict, tmp: Path) -> dict:
    write(sweep, tmp)
    return json.loads(tmp.read_text())


def recompute(chk: Checker, committed: dict[str, dict], table13_all: bool) -> None:
    import tempfile

    from foldcrypt import realdata as rd

    chk.section("CWRU cache SHA-256 (pinned in foldcrypt/realdata.py)")
    cache = rd.default_cache()
    for fid, (_sr, _label, digest) in sorted(rd.CWRU_FILES.items()):
        path = cache / f"{fid}.mat"
        got = rd._sha256(path) if path.exists() else "missing"
        print(f"  {got}  {path}")
        chk(f"{fid}.mat sha256 matches pin", got == digest, True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "m.json"
        runs = (
            (
                "metrics.json",
                rd.write_report,
                lambda: rd.run_real_sweep(download=False),
            ),
            (
                "nonideal-metrics.json",
                rd.write_nonideal_report,
                lambda: rd.run_real_nonideal_sweep(download=False),
            ),
            (
                "nonideal-cal-metrics.json",
                rd.write_nonideal_report,
                lambda: rd.run_real_nonideal_sweep(download=False, calibrate=True),
            ),
        )
        for name, write, run in runs:
            chk.section(f"recompute {name} from the .mat files")
            fresh = json_roundtrip(write, run(), tmp)
            diffs: list[str] = []
            _diff(fresh, committed[name], name, diffs)
            for d in diffs[:10]:
                print(f"    {d}")
            chk(f"{name}: fields differing from committed", len(diffs), 0)

    if table13_all:
        chk.section("recompute every Table 13 row")
        for (snr, gate), want in TABLE13.items():
            t = rd.run_real_nonideal_sweep(
                download=False, calibrate=True, cal_snr_db=snr, cal_gate=gate
            )["summary"]["total"]
            chk(
                f"Table 13 row {snr:g} dB gate {'on' if gate else 'off'}",
                table13_row(t, gate),
                want,
            )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recompute", action="store_true")
    p.add_argument("--table13-all", action="store_true", dest="table13_all")
    a = p.parse_args(argv)
    if a.table13_all and not a.recompute:
        p.error("--table13-all needs --recompute")

    committed = {
        n: json.loads((REAL / n).read_text())
        for n in ("metrics.json", "nonideal-metrics.json", "nonideal-cal-metrics.json")
    }
    chk = Checker()
    chk.section("Tables 10-11 (metrics.json)")
    check_tables_10_11(committed["metrics.json"], chk)
    chk.section("Table 12 (nonideal-metrics.json)")
    check_table12(committed["nonideal-metrics.json"], chk)
    chk.section("Table 13, committed 60 dB gated run (nonideal-cal-metrics.json)")
    check_table13_committed(committed["nonideal-cal-metrics.json"], chk)
    if a.recompute:
        recompute(chk, committed, a.table13_all)

    ok = all(chk.results)
    print(
        f"RESULT: {'ALL MATCH' if ok else 'MISMATCH'} "
        f"({sum(chk.results)}/{len(chk.results)} checks)"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
