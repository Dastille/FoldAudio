"""New-bearing test of the ripple-depth lead (exploratory, NOTES #8k).

Usage:
  python scripts/new_bearing.py depth   # stage 1: ripple depths + predicted labels
  python scripts/new_bearing.py phase   # stage 2: spike phase, phase labels, verdict
  python scripts/new_bearing.py screen --run 2026-11-23   # spike-count screen
  python scripts/new_bearing.py depth --run 2026-11-23
  python scripts/new_bearing.py phase --run 2026-11-23

Without ``--run`` the 2026-11-16 run (prereg-2026-11-16-new-bearing.md) is
reproduced unchanged. ``--run 2026-11-23`` (prereg-2026-11-23-spiky-new-bearing.md)
adds a spike-count eligibility screen that reads vibration only, downloads and
extracts the screened records (MD5-checked archives) and records their SHA-256;
stage 1 refuses to run unless the screen metrics are committed and unchanged.

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

M01, N09 = pb.NEW_BEARING_CONDITIONS

RUNS: dict[str, dict] = {
    "2026-11-16": {
        "prereg": "artifacts/paderborn/prereg-2026-11-16-new-bearing.md",
        "screen_json": None,
        "depth_json": "artifacts/paderborn/new-bearing-depth-metrics.json",
        "phase_json": "artifacts/paderborn/new-bearing-phase-metrics.json",
        "seed": ps.NEW_BEARING_SEED,
        "source_set": "KA01/KA05/KI01",
    },
    "2026-11-23": {
        "prereg": "artifacts/paderborn/prereg-2026-11-23-spiky-new-bearing.md",
        "screen_json": "artifacts/paderborn/spiky-screen-metrics.json",
        "depth_json": "artifacts/paderborn/new-bearing-2-depth-metrics.json",
        "phase_json": "artifacts/paderborn/new-bearing-2-phase-metrics.json",
        "seed": ps.SPIKY_SCREEN_SEED,
        "source_set": "spike-count screened set",
    },
}
DEFAULT_RUN = "2026-11-16"
RUN = RUNS[DEFAULT_RUN]
PREREG = RUN["prereg"]
DEPTH_JSON = RUN["depth_json"]
PHASE_JSON = RUN["phase_json"]


def _use_run(name: str) -> None:
    global RUN, PREREG, DEPTH_JSON, PHASE_JSON
    RUN = RUNS[name]
    PREREG, DEPTH_JSON, PHASE_JSON = RUN["prereg"], RUN["depth_json"], RUN["phase_json"]


def _bearings() -> tuple[str, ...]:
    """Bearings of the current run: fixed (2026-11-16) or the committed screen
    selection (2026-11-23)."""
    if RUN["screen_json"] is None:
        return pb.NEW_BEARINGS
    rel = RUN["screen_json"]
    if not _committed_unchanged(rel):
        raise SystemExit(f"{rel} must be committed and unchanged before stage 1/2")
    return tuple(json.loads((ROOT / rel).read_text())["selected"])


def _pinned(b: str, c: str, meas) -> None:
    for m in meas:
        if pb.member(b, c, m) not in pb.MAT_SHA256:
            raise SystemExit(f"{pb.member(b, c, m)} is not SHA-256 pinned")


def stage_depth() -> int:
    print(f"# prereg {PREREG}")
    bearings = _bearings()
    print(f"# stage 1 (depth only); T = {ps.RIPPLE_HELDOUT_T}; bearings {bearings}")
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
    for b in bearings:
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
    print(f"# stage 2 (phase); seed {RUN['seed']}; predictions {predicted}")
    import numpy as np

    bearings = _bearings()
    if tuple(predicted) != bearings:
        raise SystemExit(f"stage-1 bearings {tuple(predicted)} != selection {bearings}")
    screen = _screen_counts()
    rng = np.random.default_rng(RUN["seed"])

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
    s0_bad: list[str] = []
    for b in bearings:
        print(f"\n[{b}]")
        by, ns = _phase_set(b, pb.NEW_BEARING_MEASUREMENTS, rng)
        not_spiky += ns
        if screen is not None:
            s0_bad += _s0_mismatches(b, by, ns, screen[b])
        per[b] = ps.k003_phase_verdicts(by[M01], by[N09])
        if ps.phase_label(per[b]) is not None:
            pminus[b] = ps.null_b_r99(by[M01], seed=RUN["seed"])
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
    s0_ok = not s0_bad
    controls = dep["p_plus_a"]["pass"] and pplus_b and pminus_ok and s0_ok
    v = ps.new_bearing_verdict(predicted, per)
    print(f"\nnot spiky: {not_spiky or 'none'}")
    print(f"P- {'PASS' if pminus_ok else 'FAIL'} {pminus}")
    if screen is not None:
        print(f"S0 {'PASS' if s0_ok else 'FAIL'} {s0_bad or ''}".rstrip())
    print(f"controls {'PASS' if controls else 'FAIL — verdict void'}")
    print("\n[verdict]\n" + json.dumps(v, indent=1))

    doc = {
        "source": (
            "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); "
            f"{RUN['source_set']} + K001 vibration_1 + phase_current_1/2, 64 kHz"
        ),
        "prereg": PREREG,
        "depth_metrics": DEPTH_JSON,
        "controls": {
            "p_plus_a": dep["p_plus_a"]["pass"],
            "p_plus_b": {"pass": pplus_b, "k001": k},
            "p_minus": {"pass": pminus_ok, "null_b_r99": pminus},
            **(
                {"s0": {"pass": s0_ok, "mismatches": s0_bad}}
                if screen is not None
                else {}
            ),
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


def _screen_counts() -> dict[str, dict[str, list[int]]] | None:
    if RUN["screen_json"] is None:
        return None
    doc = json.loads((ROOT / RUN["screen_json"]).read_text())
    return {b: doc["counts"][b] for b in doc["selected"]}


def _s0_mismatches(b: str, by, not_spiky: list[str], counts) -> list[str]:
    """S0: stage-2 trimmed spike counts must equal the screen counts."""
    bad = []
    for c in pb.NEW_BEARING_CONDITIONS:
        got = {r.meas: r.n_spikes for r in by[c]}
        for m, want in zip(pb.NEW_BEARING_MEASUREMENTS, counts[c], strict=True):
            name = pb.member(b, c, m)
            if m in got:
                if got[m] != want:
                    bad.append(f"{name}: {got[m]} != {want}")
            elif name in not_spiky and want >= ps.SPIKY_MIN:
                bad.append(f"{name}: not spiky in stage 2, screen {want}")
    return bad


def stage_screen() -> int:
    """Spike-count eligibility screen (vibration only), 2026-11-23 run."""
    import hashlib

    if RUN["screen_json"] is None:
        raise SystemExit("this run has no screen")
    print(f"# prereg {PREREG}")
    print(
        f"# spike-count screen (vibration_1 only; no reference, depth or phase); "
        f"spiky = >= {ps.SPIKY_MIN} spikes after {ps.EDGE_TRIM_S} s edge trim; "
        f"eligible = >= {ps.SPIKY_SCREEN_MIN_RECORDS}/10 spiky at each of "
        f"{pb.NEW_BEARING_CONDITIONS}; stop at {ps.SPIKY_SCREEN_TARGET} eligible"
    )
    sha: dict[str, str] = {}

    def counts(b: str) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for c in pb.NEW_BEARING_CONDITIONS:
            out[c] = []
            for m in pb.NEW_BEARING_MEASUREMENTS:
                path = pb.fetch(b, c, meas=m)
                sha[pb.member(b, c, m)] = hashlib.sha256(path.read_bytes()).hexdigest()
                x = ps.load_channels(path, ("vibration_1",))["vibration_1"]
                out[c].append(ps.screen_spike_count(x))
            print(f"{b} {c} spike counts {out[c]}", flush=True)
        ok = ps.screen_eligible(out)
        print(f"{b} -> {'ELIGIBLE' if ok else 'not eligible'}", flush=True)
        return out

    selected, screened, cnt = ps.screen_select(pb.SPIKY_SCREEN_POOL, counts)
    print(f"\nscreened {screened}")
    print(f"selected {selected}")
    if len(selected) < ps.NEW_BEARING_MIN_VALID:
        print("fewer than 2 eligible bearings: N = UNTESTABLE, stop (no stage 1/2)")
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); vibration_1 only",
        "prereg": PREREG,
        "stage": "screen (spike counts only; no reference, depth or phase computed)",
        "rule": {
            "spiky_min": ps.SPIKY_MIN,
            "edge_trim_s": ps.EDGE_TRIM_S,
            "min_records": ps.SPIKY_SCREEN_MIN_RECORDS,
            "target": ps.SPIKY_SCREEN_TARGET,
            "pool": list(pb.SPIKY_SCREEN_POOL),
        },
        "screened": screened,
        "selected": selected,
        "counts": cnt,
        "sha256": sha,
    }
    (ROOT / RUN["screen_json"]).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {RUN['screen_json']}")
    return 0


def main(argv: list[str]) -> int:
    argv = list(argv)
    run = DEFAULT_RUN
    if len(argv) == 3 and argv[1] == "--run" and argv[2] in RUNS:
        run = argv[2]
        argv = argv[:1]
    _use_run(run)
    if argv == ["depth"]:
        return stage_depth()
    if argv == ["phase"]:
        return stage_phase()
    if argv == ["screen"]:
        return stage_screen()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
