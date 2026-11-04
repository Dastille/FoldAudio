"""FS-1: pre-registered hybrid-QTT compression test (2026-11-04).

Prereg: docs/folding-math-scout.md §4 and
artifacts/folding-scout/prereg-2026-11-04-fs1.md (commit f5a30b0, before any
FS-1 number). CPU only. Reads the SHA-256-pinned CWRU and Paderborn caches;
never downloads.

    python scripts/fs1_hybrid_qtt.py | tee artifacts/folding-scout/fs1-2026-11-04.log
"""

from __future__ import annotations

import platform
import statistics
import time

import numpy as np

from foldcrypt import fs1
from foldcrypt import paderborn as pb
from foldcrypt import realdata as rd

D = 17
N = 2**D
EPS = 3e-3
WIN = 0.95
CWRU_IDS = (97, 109, 122, 135, 213, 226, 238)
NEG_SEED = 20261104


def tones() -> np.ndarray:
    t = np.arange(N) / 48000.0
    return (
        np.sin(2 * np.pi * 157.0 * t)
        + 0.5 * np.sin(2 * np.pi * 1630.0 * t + 0.3)
        + 0.25 * np.sin(2 * np.pi * 4100.0 * t + 1.1)
    )


def run(name: str, x: np.ndarray) -> dict:
    t0 = time.time()
    b = fs1.encode_baseline(x, EPS)
    if b is None:
        print(f"{name} | INVALID: baseline never reached the error window")
        return {"name": name, "valid": False}
    q = fs1.stream_step(b.stream)
    b0 = fs1.encode_baseline(x, EPS, transforms=fs1.NO_PREDICTOR, q=q)
    h = fs1.encode_hybrid(x, D, b.rel)
    if h is None or b0 is None:
        print(f"{name} | INVALID: hybrid never reached the error window")
        return {"name": name, "valid": False}
    r, r0 = h.nbytes / b.nbytes, h.nbytes / b0.nbytes
    print(
        f"{name} | base {b.nbytes} B ({b.choice}) rel {b.rel:.4e} max {b.max_abs:.3e} | "
        f"no-pred {b0.nbytes} B ({b0.choice}) | hybrid {h.nbytes} B ({h.choice}) "
        f"rel {h.rel:.4e} max {h.max_abs:.3e} | hyb/base {r:.3f} | hyb/no-pred {r0:.3f} "
        f"| {time.time() - t0:.1f} s"
    )
    return {"name": name, "valid": True, "ratio": r, "ratio_nopred": r0}


def main() -> None:
    t_start = time.time()
    print("# FS-1 hybrid QTT vs fair quantized baseline (PRE-REGISTERED)")
    print(
        "# prereg: docs/folding-math-scout.md §4 + artifacts/folding-scout/prereg-2026-11-04-fs1.md (f5a30b0)"
    )
    print(
        f"# {time.strftime('%Y-%m-%d %H:%M %Z')}; python {platform.python_version()}; numpy {np.__version__}; {fs1.zstd_version()}"
    )
    print(f"# N = 2**{D}; eps = {EPS}; win if hybrid <= {WIN} x baseline")
    print("\n## Controls")
    pos = run("positive: 3 tones, no noise", tones())
    neg = run(
        "negative: white noise seed 20261104",
        np.random.default_rng(NEG_SEED).standard_normal(N),
    )
    pos_ok = pos["valid"] and pos["ratio"] < 1.0
    neg_ok = neg["valid"] and neg["ratio"] >= WIN
    print(f"positive control {'PASS' if pos_ok else 'FAIL -> run INVALID'}")
    print(f"negative control {'PASS' if neg_ok else 'FAIL -> run INVALID'}")

    print("\n## CWRU 48 kHz drive end (counted for H1)")
    rows = []
    for fid in CWRU_IDS:
        x = rd.load_de(rd.fetch(fid, download=False))[:N]
        rows.append(run(f"CWRU {fid} ({rd.CWRU_FILES[fid][1]})", x))

    print("\n## Paderborn KA04 _1, 64 kHz (secondary, NOT counted)")
    for cond in pb.CONDITIONS:
        try:
            x = pb.load_vibration(pb.fetch("KA04", cond, download=False))[:N]
        except (FileNotFoundError, OSError) as e:
            print(f"KA04 {cond} | not run: {e}")
            continue
        run(f"KA04 {cond}", x)

    print("\n## Verdict")
    valid = [r for r in rows if r["valid"]]
    if len(valid) != len(rows):
        print(f"{len(rows) - len(valid)} CWRU record(s) INVALID")
    wins = sum(r["ratio"] <= WIN for r in valid)
    wins0 = sum(r["ratio_nopred"] <= WIN for r in valid)
    med = statistics.median(r["ratio"] for r in valid) if valid else float("nan")
    f1 = wins < 4
    f2 = wins0 >= 4 and wins < 4
    f3 = med >= 1.0
    print(f"wins vs predictor baseline: {wins}/7; vs no-predictor baseline: {wins0}/7")
    print(f"median hybrid/baseline: {med:.3f}")
    print(f"F1 (wins < 4): {'FIRES' if f1 else 'no'}")
    print(f"F2 (wins only without predictor): {'FIRES' if f2 else 'no'}")
    print(f"F3 (median >= 1.00): {'FIRES' if f3 else 'no'}")
    if not (pos_ok and neg_ok) or len(valid) != len(rows):
        print("RESULT: INVALID (control failed or record invalid)")
    elif f1 or f2 or f3:
        print("RESULT: H1 FALSIFIED")
    else:
        print("RESULT: H1 HELD")
    print(f"# wall time {time.time() - t_start:.0f} s")


if __name__ == "__main__":
    main()
