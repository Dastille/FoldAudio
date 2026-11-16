"""New-bearing test of the ripple-depth lead (exploratory, NOTES #8k).

Usage:
  python scripts/new_bearing.py depth   # stage 1: ripple depths + predicted labels
  python scripts/new_bearing.py phase   # stage 2: spike phase, phase labels, verdict

Stage 1 loads only the two phase-current channels of the N15_M01_F10 records
(no vibration, no spikes, no phase) and writes
``artifacts/paderborn/new-bearing-depth-metrics.json``. Stage 2 refuses to run
unless that file is committed and unchanged, so the predictions provably
precede the phase numbers. Records, rules, seed and controls are fixed in
``artifacts/paderborn/prereg-2026-11-16-new-bearing.md``. Uses only
SHA-256-pinned records in the Paderborn cache (no download). Exit status is 0
whenever the stage completed.
"""

from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn as pb  # noqa: E402
from foldcrypt import paderborn_spikes as ps  # noqa: E402

PREREG = "artifacts/paderborn/prereg-2026-11-16-new-bearing.md"
DEPTH_JSON = "artifacts/paderborn/new-bearing-depth-metrics.json"
PHASE_JSON = "artifacts/paderborn/new-bearing-phase-metrics.json"
M01, N09 = pb.NEW_BEARING_CONDITIONS


def _pinned(b: str, c: str, meas) -> None:
    for m in meas:
        if pb.member(b, c, m) not in pb.MAT_SHA256:
            raise SystemExit(f"{pb.member(b, c, m)} is not SHA-256 pinned")


def stage_depth() -> int:
    print(f"# prereg {PREREG}")
    print(
        f"# stage 1 (depth only); T = {ps.RIPPLE_HELDOUT_T}; bearings {pb.NEW_BEARINGS}"
    )
    kmeas = ps.NEW_BEARING_PPLUS_MEASUREMENTS
    _pinned("K001", M01, kmeas)
    kd = [ps.ripple_depth_record("K001", m) for m in kmeas]
    kmed = statistics.median(kd)
    want = ps.RIPPLE_TRAIN_MEDIANS["K001"]
    pplus_a = math.isclose(kmed, want, rel_tol=1e-9)
    print(f"[P+a] K001 {M01} _11.._20 median depth {kmed:.9g} vs published {want:.9g}")
    print(f"P+a {'PASS' if pplus_a else 'FAIL'}")

    per: dict[str, dict] = {}
    print("\n[new-bearing N15_M01 records]")
    for b in pb.NEW_BEARINGS:
        _pinned(b, M01, pb.NEW_BEARING_MEASUREMENTS)
        depths = []
        for m in pb.NEW_BEARING_MEASUREMENTS:
            d = ps.ripple_depth_record(b, m)
            depths.append(d)
            print(f"{pb.member(b, M01, m):<30} depth {d:.6f}")
        per[b] = ps.predict_label(depths) | {"records": depths}
    print("\n[predictions]")
    for b, v in per.items():
        near = "  (within 10% of T)" if v["near_t"] else ""
        print(
            f"{b} median {v['median']:.6f}  range {v['min']:.6f}-{v['max']:.6f}"
            f"  -> predicted {v['predicted']}{near}"
        )
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); N15_M01_F10 phase currents",
        "prereg": PREREG,
        "stage": "depth (no spike or phase number computed)",
        "threshold": ps.RIPPLE_HELDOUT_T,
        "p_plus_a": {"pass": pplus_a, "k001_median": kmed, "published": want},
        "per_bearing": per,
        "predicted": {b: v["predicted"] for b, v in per.items()},
    }
    dst = ROOT / DEPTH_JSON
    dst.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {DEPTH_JSON}")
    return 0


def _committed_unchanged(rel: str) -> bool:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True
    )
    diff = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT)
    return tracked.returncode == 0 and diff.returncode == 0


def _phase_set(b: str, meas, rng) -> tuple[dict[str, list], list[str]]:
    by: dict[str, list] = {c: [] for c in pb.NEW_BEARING_CONDITIONS}
    not_spiky = []
    for c in pb.NEW_BEARING_CONDITIONS:
        _pinned(b, c, meas)
        for m in meas:
            r = ps.phase_record(b, c, m, rng=rng)
            if r is None:
                not_spiky.append(pb.member(b, c, m))
                continue
            by[c].append(r)
            print(
                f"{r.record:<30} N {r.n_spikes:4d}  ref {r.ref_db:5.1f} dB "
                f"{'ok ' if r.ref_valid else 'BAD'}  R {r.r:.3f}  "
                f"mu {math.degrees(r.mu):+7.1f} deg"
            )
    return by, not_spiky


def stage_phase() -> int:
    if not _committed_unchanged(DEPTH_JSON):
        raise SystemExit(f"{DEPTH_JSON} must be committed and unchanged before stage 2")
    dep = json.loads((ROOT / DEPTH_JSON).read_text())
    predicted = dep["predicted"]
    print(f"# prereg {PREREG}")
    print(f"# stage 2 (phase); seed {ps.NEW_BEARING_SEED}; predictions {predicted}")
    import numpy as np

    rng = np.random.default_rng(ps.NEW_BEARING_SEED)

    print("\n[P+b K001 _11.._20 pipeline reproduction]")
    kby, _ = _phase_set("K001", ps.NEW_BEARING_PPLUS_MEASUREMENTS, rng)
    k = ps.k003_phase_verdicts(kby[M01], kby[N09])
    pplus_b = (
        all(
            math.isclose(
                ps.between_stats([r for r in kby[c] if r.usable])[0], want, rel_tol=1e-9
            )
            for c, want in ps.NEW_BEARING_PPLUS_RB.items()
        )
        and ps.phase_label(k) == "SCATTER"
    )
    print(
        f"K001 N15_M01 R_between {k.get('n15_m01_r_between', math.nan):.9g} "
        f"(published {ps.NEW_BEARING_PPLUS_RB[M01]:.9g}); N09 "
        f"{k.get('n09_r_between', math.nan):.9g} (published "
        f"{ps.NEW_BEARING_PPLUS_RB[N09]:.9g}); Q3 {k['Q3']} C3n {k['C3n']}"
    )
    print(f"P+b {'PASS' if pplus_b else 'FAIL'}")

    per: dict[str, dict] = {}
    not_spiky: list[str] = []
    pminus: dict[str, float] = {}
    for b in pb.NEW_BEARINGS:
        print(f"\n[{b}]")
        by, ns = _phase_set(b, pb.NEW_BEARING_MEASUREMENTS, rng)
        not_spiky += ns
        per[b] = ps.k003_phase_verdicts(by[M01], by[N09])
        if ps.phase_label(per[b]) is not None:
            pminus[b] = ps.null_b_r99(by[M01])
        print(
            f"{b} usable N15_M01 {per[b]['n15_m01_usable']} / N09 {per[b]['n09_usable']}"
            f"  Q3 {per[b]['Q3']}  C3n {per[b]['C3n']}"
        )
        for key in (
            "n15_m01_r_between",
            "n15_m01_p_between",
            "n09_r_between",
            "n09_p_between",
        ):
            if key in per[b]:
                print(f"    {key} {per[b][key]:.4g}")
        if b in pminus:
            print(f"    P- null-B R_between 99th pct {pminus[b]:.3f}")

    pminus_ok = all(v < ps.R_BETWEEN_HELD for v in pminus.values())
    controls = dep["p_plus_a"]["pass"] and pplus_b and pminus_ok
    v = ps.new_bearing_verdict(predicted, per)
    print(f"\nnot spiky: {not_spiky or 'none'}")
    print(f"P- {'PASS' if pminus_ok else 'FAIL'} {pminus}")
    print(f"controls {'PASS' if controls else 'FAIL — verdict void'}")
    print("\n[verdict]\n" + json.dumps(v, indent=1))

    doc = {
        "source": (
            "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); "
            "KA01/KA05/KI01 + K001 vibration_1 + phase_current_1/2, 64 kHz"
        ),
        "prereg": PREREG,
        "depth_metrics": DEPTH_JSON,
        "controls": {
            "p_plus_a": dep["p_plus_a"]["pass"],
            "p_plus_b": {"pass": pplus_b, "k001": k},
            "p_minus": {"pass": pminus_ok, "null_b_r99": pminus},
            "valid": controls,
        },
        "verdict": v,
        "per_bearing": per,
        "not_spiky": not_spiky,
    }
    dst = ROOT / PHASE_JSON
    dst.write_text(json.dumps(doc, indent=2, default=float) + "\n")
    print(f"wrote {PHASE_JSON}")
    return 0


def main(argv: list[str]) -> int:
    if argv == ["depth"]:
        return stage_depth()
    if argv == ["phase"]:
        return stage_phase()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
