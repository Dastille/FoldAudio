"""What separates N15_M01 phase-scatter bearings from lock bearings (exploratory).

Usage: python scripts/scatter_covariates.py
-> artifacts/paderborn/scatter-covariates-metrics.json

Covariates, labels, rules, controls and seed are fixed in
``artifacts/paderborn/prereg-2026-11-10-scatter-covariates.md``. Uses only the
SHA-256-pinned N15_M01_F10 label records of K001–K006 in the Paderborn cache
(no download). Exit status is 0 whenever the run completed.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402

PREREG = "artifacts/paderborn/prereg-2026-11-10-scatter-covariates.md"


def _fmt(x: float) -> str:
    return f"{x:.6g}"


def main() -> int:
    print(f"# prereg {PREREG}")
    print(f"# seed {ps.SCATTER_COV_SEED}; condition {ps.SCATTER_COV_CONDITION}")
    labels = {b: v[0] for b, v in ps.SCATTER_COV_LABELS.items()}
    keys = ps.SCATTER_COVARIATES + ps.SCATTER_NONBLIND
    per_rec: dict[str, dict[str, list[float]]] = {k: {} for k in keys}
    rows = []
    for b, (_lab, _rb, meas) in ps.SCATTER_COV_LABELS.items():
        for k in keys:
            per_rec[k][b] = []
        for m in meas:
            c = ps.scatter_covariates_record(b, m)
            rows.append({"record": pb.member(b, ps.SCATTER_COV_CONDITION, m)} | c)
            for k in keys:
                per_rec[k][b].append(c[k])
            print(
                f"{pb.member(b, ps.SCATTER_COV_CONDITION, m):<30} "
                + "  ".join(f"{k} {_fmt(c[k])}" for k in keys)
            )
    med = {k: {b: statistics.median(v) for b, v in per_rec[k].items()} for k in keys}

    print("\n[bearing medians]  label  R_between  " + "  ".join(keys))
    for b, (lab, rb, _m) in ps.SCATTER_COV_LABELS.items():
        print(f"{b} {lab:<8} {rb:.3f}  " + "  ".join(_fmt(med[k][b]) for k in keys))

    out: dict = {}
    print("\n[pre-registered covariates, k = 4] (exploratory; min two-sided p = 0.10)")
    for k in ps.SCATTER_COVARIATES:
        v = ps.covariate_verdict(med[k], labels)
        v["ranges_disjoint"] = ps.ranges_disjoint(per_rec[k], labels)
        v["record_range"] = {b: [min(x), max(x)] for b, x in per_rec[k].items()}
        out[k] = v
        print(
            f"{k:<18} {v['verdict']:<10} dir {v['direction']}  p {v['perm_p_two_sided']:.2f}"
            f"  ranges_disjoint {v['ranges_disjoint']}"
            f"  scatter {[_fmt(x) for x in v['scatter_values']]}"
            f"  lock {[_fmt(x) for x in v['lock_values']]}"
        )

    rbs = {b: v[1] for b, v in ps.SCATTER_COV_LABELS.items()}
    pos = ps.covariate_verdict(rbs, labels)
    shuf = ps.shuffled_labels(labels)
    neg = ps.covariate_verdict(rbs, shuf)
    pos_ok = pos["verdict"] == "SEPARATES" and abs(pos["perm_p_two_sided"] - 0.1) < 1e-9
    neg_ok = neg["verdict"] == "OVERLAPS"
    print("\n[controls]")
    print(
        f"P+ R_between, true labels: {pos['verdict']} p {pos['perm_p_two_sided']:.2f} -> {'PASS' if pos_ok else 'FAIL'}"
    )
    print(
        f"P- R_between, shuffled {shuf}: {neg['verdict']} p {neg['perm_p_two_sided']:.2f} -> {'PASS' if neg_ok else 'FAIL'}"
    )
    valid = pos_ok and neg_ok
    print(f"controls {'PASS' if valid else 'FAIL — all verdicts void'}")

    print("\n[NON-BLIND, already published quantities; not verdicts]")
    nb: dict = {}
    for k in ps.SCATTER_NONBLIND:
        nb[k] = ps.covariate_verdict(med[k], labels)
        nb[k]["ranges_disjoint"] = ps.ranges_disjoint(per_rec[k], labels)
        nb[k]["record_range"] = {b: [min(x), max(x)] for b, x in per_rec[k].items()}
        print(
            f"{k:<18} {nb[k]['verdict']:<10} dir {nb[k]['direction']}  p {nb[k]['perm_p_two_sided']:.2f}"
            f"  ranges_disjoint {nb[k]['ranges_disjoint']}"
            f"  ranges {{{', '.join(f'{b}: {_fmt(r[0])}-{_fmt(r[1])}' for b, r in nb[k]['record_range'].items())}}}"
        )
    r0 = ps.covariate_verdict(ps.RUN_IN_HOURS, labels)
    print(
        f"R0 run-in hours (Lessmeier 2016 Table 7, K001 '>50' as 50): {r0['verdict']} "
        f"p {r0['perm_p_two_sided']:.2f}"
    )

    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); N15_M01_F10 label records K001-K006",
        "prereg": PREREG,
        "exploratory": True,
        "labels": {
            b: {"label": v[0], "r_between": v[1], "meas": list(v[2])}
            for b, v in ps.SCATTER_COV_LABELS.items()
        },
        "controls": {
            "positive": pos | {"pass": pos_ok},
            "negative": neg | {"pass": neg_ok, "labels": shuf},
            "valid": valid,
        },
        "covariates": out,
        "bearing_medians": med,
        "nonblind": nb,
        "run_in_context": r0 | {"hours": ps.RUN_IN_HOURS},
        "records": rows,
    }
    dst = ROOT / "artifacts" / "paderborn" / "scatter-covariates-metrics.json"
    dst.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
