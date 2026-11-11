"""Ripple depth on held-out N15_M01 records: does it still separate scatter
from lock bearings? (exploratory)

Usage: python scripts/ripple_heldout.py
-> artifacts/paderborn/ripple-heldout-metrics.json

Records, predictions, threshold, controls and seed are fixed in
``artifacts/paderborn/prereg-2026-11-11-ripple-heldout.md``. Uses only
SHA-256-pinned records in the Paderborn cache (no download). Exit status is 0
whenever the run completed.
"""

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

PREREG = "artifacts/paderborn/prereg-2026-11-11-ripple-heldout.md"
COND = ps.SCATTER_COV_CONDITION


def _medians(meas_map: dict[str, tuple[int, ...]]) -> tuple[dict, dict]:
    per: dict[str, list[float]] = {}
    for b, meas in meas_map.items():
        per[b] = [ps.ripple_depth_record(b, m) for m in meas]
    return per, {b: statistics.median(v) for b, v in per.items()}


def main() -> int:
    print(f"# prereg {PREREG}")
    labels = {b: v[0] for b, v in ps.SCATTER_COV_LABELS.items()}

    train_meas = {b: v[2] for b, v in ps.SCATTER_COV_LABELS.items()}
    _tp, tmed = _medians(train_meas)
    pplus = all(
        math.isclose(tmed[b], ps.RIPPLE_TRAIN_MEDIANS[b], rel_tol=1e-9) for b in tmed
    )
    print("[P+ training medians recomputed vs published]")
    for b in tmed:
        print(f"{b} {tmed[b]:.9g} vs {ps.RIPPLE_TRAIN_MEDIANS[b]:.9g}")
    print(f"P+ {'PASS' if pplus else 'FAIL'}")

    per, med = _medians(pb.RIPPLE_HELDOUT_MEASUREMENTS)
    print("\n[held-out records]")
    rows = []
    for b, meas in pb.RIPPLE_HELDOUT_MEASUREMENTS.items():
        for m, d in zip(meas, per[b]):
            name = pb.member(b, COND, m)
            rows.append({"record": name, "ripple_depth": d, "label": labels[b]})
            print(f"{name:<30} {labels[b]:<8} depth {d:.6f}")

    print("\n[held-out bearing medians]")
    for b in med:
        tag = " (non-blind)" if b in ps.RIPPLE_HELDOUT_NONBLIND else ""
        print(
            f"{b} {labels[b]:<8} held-out {med[b]:.6f}  training {ps.RIPPLE_TRAIN_MEDIANS[b]:.6f}{tag}"
        )

    shuf = ps.shuffled_labels(labels)
    neg = ps.covariate_verdict(med, shuf)
    pminus = neg["verdict"] == "OVERLAPS"
    print(f"\nP- shuffled {shuf}: {neg['verdict']} -> {'PASS' if pminus else 'FAIL'}")
    valid = pplus and pminus
    print(f"controls {'PASS' if valid else 'FAIL — all verdicts void'}")

    h1 = ps.one_sided_verdict(med, labels)
    blind = {b: x for b, x in med.items() if b not in ps.RIPPLE_HELDOUT_NONBLIND}
    h1b = ps.one_sided_verdict(blind, labels)
    h2 = ps.threshold_verdict(med, labels)
    print("\n[verdicts]")
    print(
        f"H1  all 6 bearings: {h1['verdict']}  one-sided p {h1['perm_p_one_sided']:.2f}"
    )
    print(
        f"H1b blind 5:        {h1b['verdict']}  one-sided p {h1b['perm_p_one_sided']:.2f}"
    )
    print(
        f"H2  T={ps.RIPPLE_HELDOUT_T}: {h2['verdict']}  {h2['correct']}/{h2['n']} bearings"
    )

    rec_ok = sum(
        ("SCATTER" if r["ripple_depth"] > ps.RIPPLE_HELDOUT_T else "LOCK") == r["label"]
        for r in rows
    )
    disjoint = ps.ranges_disjoint(per, labels)
    print(
        f"\n[descriptive] per-record accuracy at T: {rec_ok}/{len(rows)}; record ranges disjoint: {disjoint}"
    )

    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); N15_M01_F10 K001-K006",
        "prereg": PREREG,
        "exploratory": True,
        "controls": {
            "p_plus": {"pass": pplus, "recomputed": tmed},
            "p_minus": neg | {"pass": pminus, "labels": shuf},
            "valid": valid,
        },
        "verdicts": {"H1": h1, "H1b_blind": h1b, "H2": h2},
        "heldout_medians": med,
        "train_medians": ps.RIPPLE_TRAIN_MEDIANS,
        "nonblind": list(ps.RIPPLE_HELDOUT_NONBLIND),
        "per_record_accuracy": [rec_ok, len(rows)],
        "record_ranges_disjoint": disjoint,
        "records": rows,
    }
    dst = ROOT / "artifacts" / "paderborn" / "ripple-heldout-metrics.json"
    dst.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
