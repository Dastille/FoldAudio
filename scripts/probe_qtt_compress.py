"""Folding-math scout smoke probe (2026-11-03). EXPLORATORY, not the
pre-registered test in docs/folding-math-scout.md.

Question: does "folding" a measured vibration record into a 2x2x...x2 tensor
(quantized tensor train, QTT; Khoromskij 2011, Oseledets 2011 TT-SVD) give a
smaller file than a fair quantized baseline at the same error?

For each signal (first 2**17 samples):
  baseline  uniform quantizer with step q = sqrt(12) * eps * rms(x), so the
            expected RMSE is eps * rms(x); integers stored raw (int32) or as
            first differences, then xz -9e / bz2 -9 / zlib -9 (Python stdlib;
            zstd is not installed on this box, so it is not in this probe).
  QTT       TT-SVD of x reshaped to (2,)*17 with the truncation set so the
            relative error matches the baseline's measured relative error;
            cores stored as float32, then xz -9e. Error is re-measured after
            the float32 rounding.
Signals: CWRU 97 (normal, 48 kHz) and 238 (outer race 0.021 in, 48 kHz), from
the SHA-256-checked cache (no download), plus a positive control: a sum of
three sinusoids (exact QTT rank <= 6) with no noise, and the same with white
noise at 40 dB SNR. Deterministic (seed 20261103). CPU, a few seconds.

    python scripts/probe_qtt_compress.py
"""

from __future__ import annotations

import bz2
import lzma
import zlib

import numpy as np

from foldcrypt import realdata as rd

D = 17
N = 2**D
EPS = (1e-2, 3e-3, 1e-3)
SEED = 20261103


def xz(b: bytes) -> int:
    return len(lzma.compress(b, preset=9 | lzma.PRESET_EXTREME))


def baseline(x: np.ndarray, eps: float) -> dict:
    rms = float(np.sqrt(np.mean(x**2)))
    q = np.sqrt(12.0) * eps * rms
    k = np.round(x / q).astype(np.int64)
    rel = float(np.linalg.norm(x - k * q) / np.linalg.norm(x))
    raw = k.astype(np.int32).tobytes()
    dif = np.diff(k, prepend=0).astype(np.int32).tobytes()
    sizes = {
        "xz": xz(raw),
        "bz2": len(bz2.compress(raw, 9)),
        "zlib": len(zlib.compress(raw, 9)),
        "xz_diff": xz(dif),
        "bz2_diff": len(bz2.compress(dif, 9)),
    }
    best = min(sizes, key=sizes.get)
    return {"rel": rel, "sizes": sizes, "best": best, "best_bytes": sizes[best]}


def tt_svd(x: np.ndarray, rel_eps: float) -> list[np.ndarray]:
    """Oseledets (2011) Alg. 1: delta = eps/sqrt(d-1) * ||x|| per unfolding."""
    delta = rel_eps / np.sqrt(D - 1) * np.linalg.norm(x)
    cores, r, c = [], 1, x.reshape(-1)
    for _ in range(D - 1):
        c = c.reshape(r * 2, -1)
        u, s, vt = np.linalg.svd(c, full_matrices=False)
        tail = np.sqrt(np.cumsum((s**2)[::-1]))[::-1]  # tail[i] = ||s[i:]||
        keep = max(1, int(np.sum(tail > delta)))
        cores.append(u[:, :keep].reshape(r, 2, keep))
        c = s[:keep, None] * vt[:keep]
        r = keep
    cores.append(c.reshape(r, 2, 1))
    return cores


def tt_full(cores: list[np.ndarray]) -> np.ndarray:
    out = cores[0].reshape(2, -1)
    for g in cores[1:]:
        r = g.shape[0]
        out = (out.reshape(-1, r) @ g.reshape(r, -1)).reshape(-1)
    return out.reshape(-1)


def qtt(x: np.ndarray, rel_target: float) -> dict:
    cores = [g.astype(np.float32) for g in tt_svd(x, rel_target)]
    y = tt_full([g.astype(np.float64) for g in cores])
    rel = float(np.linalg.norm(x - y) / np.linalg.norm(x))
    blob = b"".join(g.tobytes() for g in cores)
    return {
        "rel": rel,
        "ranks": [g.shape[2] for g in cores[:-1]],
        "params": int(sum(g.size for g in cores)),
        "bytes": xz(blob),
    }


def signals() -> list[tuple[str, np.ndarray]]:
    rng = np.random.default_rng(SEED)
    t = np.arange(N) / 48000.0
    tones = (
        np.sin(2 * np.pi * 157.0 * t)
        + 0.5 * np.sin(2 * np.pi * 1630.0 * t + 0.3)
        + 0.25 * np.sin(2 * np.pi * 4100.0 * t + 1.1)
    )
    noise = rng.standard_normal(N) * np.sqrt(np.mean(tones**2)) * 10 ** (-40 / 20)
    out = [
        ("control: 3 tones, no noise", tones),
        ("control: 3 tones + 40 dB noise", tones + noise),
    ]
    for fid in (97, 238):
        x = rd.load_de(rd.fetch(fid, download=False))[:N]
        out.append((f"CWRU {fid} ({rd.CWRU_FILES[fid][1]})", x - x.mean()))
    return out


def main() -> None:
    print("# folding-math scout smoke probe, EXPLORATORY (not the pre-registered test)")
    print(
        f"# N = 2**{D} = {N} samples per signal; raw int32 = {4 * N} bytes; seed {SEED}"
    )
    print(
        "signal | eps | base rel | base best (bytes) | QTT rel | QTT max rank | QTT params | QTT xz bytes | QTT/base"
    )
    for name, x in signals():
        for eps in EPS:
            b = baseline(x, eps)
            t = qtt(x, b["rel"])
            ratio = t["bytes"] / b["best_bytes"]
            print(
                f"{name} | {eps:g} | {b['rel']:.2e} | {b['best']} {b['best_bytes']} | "
                f"{t['rel']:.2e} | {max(t['ranks'])} | {t['params']} | {t['bytes']} | {ratio:.2f}"
            )


if __name__ == "__main__":
    main()
