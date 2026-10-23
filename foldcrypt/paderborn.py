"""ShockDAQ on a second public bearing dataset: Paderborn University KAt
Bearing DataCenter, vibration channel at 64 kHz (NOTES #8g, 2026-10-23).

Why: CWRU (``realdata.py``) only goes up to 48 kHz and showed that sample rate
decides whether fold can recover an overload at all (7.5–9.8 dB at 48 kHz,
none at 12 kHz). Paderborn records the bearing-housing accelerometer at 64 kHz,
so it tests that finding on a second test rig, a second sensor chain and a
higher rate. The scoring chain is exactly ``realdata.eval_record``.

Named ASSUMPTIONS (same as the CWRU study unless stated):

1. The recorded ``vibration_1`` channel is treated as the true sensor output.
   The dataset does not state its unit in the .mat file, so numbers are
   reported as ratios (Δ/peak, λ/peak, dB) and the raw unit is "dataset units".
2. Overload is applied in software (λ = r · peak); the KAt rig did not overload.
3. Ideal fold, blind recovery (zero-mean prior); the original is used only for
   scoring. "Recovered" = max |x̂ − x| ≤ 1e-6 · peak.
4. "64→16k" rows are plain 4:1 subsampling (no anti-alias filter), as in CWRU.
5. Source files: the KAt archives as mirrored on Zenodo (record 15845309,
   CC BY 4.0, MD5 listed by Zenodo). Only the needed .mat members are extracted
   (needs the ``unar`` command-line tool) and each is pinned by SHA-256. Nothing
   is redistributed in this repository.
6. CPU only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .foldaudio import max_sample_jump
from .realdata import RealCell, eval_record, headroom_db, kurtosis, summarize

SR = 64_000
ZENODO_URL = "https://zenodo.org/api/records/15845309/files/{bearing}.rar/content"

#: bearing code → (label, MD5 of the .rar as listed by Zenodo record 15845309)
BEARINGS: dict[str, tuple[str, str]] = {
    "K001": ("healthy", "af6dc58283d356cd438e7738a2d525b8"),
    "KA04": ("outer ring, fatigue pitting", "f87503ed69a624ba6e1d9e573e6c09fb"),
    "KI04": ("inner ring, fatigue pitting", "a5a634fcdcb33a8501e7411d30441c6d"),
}

#: operating conditions (speed / torque / radial force codes), measurement _1
CONDITIONS = ("N15_M07_F10", "N09_M07_F10", "N15_M01_F10", "N15_M07_F04")

#: member name → SHA-256 of the extracted .mat (filled 2026-10-23)
MAT_SHA256: dict[str, str] = {
    "K001/N09_M07_F10_K001_1.mat": "c55f4c6a5d6d9a83d18d24dce4f164ffc85721e4e358df1c1ac9886583c2269f",
    "K001/N15_M01_F10_K001_1.mat": "84ff03769c3efa9cd2c3e0cbeefa60ed6bcec3436efa804637788a638b5f23f3",
    "K001/N15_M07_F04_K001_1.mat": "4790406e566cd6ed93241bc0a1e51ea7b9603c38a712a93d2946140dfa581458",
    "K001/N15_M07_F10_K001_1.mat": "e1a971e93991e5f8bbfdcacde5a0fec895a4248f8232d52b59ff85d034c9c00d",
    "KA04/N09_M07_F10_KA04_1.mat": "7db59955c834c4f74e8360bc873a4adc27beb569cf4406ba857777b1f986f138",
    "KA04/N15_M01_F10_KA04_1.mat": "060dc5acbcab35a2aaad7d19be4b771e993a29f5b927d66bec96d23a972fd040",
    "KA04/N15_M07_F04_KA04_1.mat": "46f3a5e8984ed72eca6b0824764c8c608132918ba6185002a59433c35904ae3e",
    "KA04/N15_M07_F10_KA04_1.mat": "c1caff884401a8476d3e8f42fb6efcd57c721888706af26cfeaeb2c3e99b35a5",
    "KI04/N09_M07_F10_KI04_1.mat": "fa5d43cd8ab8cec9cadb0b9356096231b9f2a1a925a2bf935b5d3bcb2eecdf5f",
    "KI04/N15_M01_F10_KI04_1.mat": "24cd3f08730e2ffe0117e77ef8eb14433b6131bddf6508d2ea50bae950f936b3",
    "KI04/N15_M07_F04_KI04_1.mat": "935c1b56751894110c6256fa3d06b0cc9e526417d0b7eee92abeaea1dce0617f",
    "KI04/N15_M07_F10_KI04_1.mat": "d77409dca95d03986b5957b73c2219f42f7bbfd8080ebbf6f5b9f11571476f9c",
}

#: Environment variable that overrides the Paderborn cache directory.
CACHE_ENV = "FOLDCRYPT_PADERBORN_CACHE"


def default_cache() -> Path:
    """``$FOLDCRYPT_PADERBORN_CACHE`` if set, else ``~/.cache/foldcrypt/paderborn``."""
    env = os.environ.get(CACHE_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "foldcrypt" / "paderborn"


def member(bearing: str, condition: str) -> str:
    """Archive member path, e.g. ``K001/N15_M07_F10_K001_1.mat``."""
    return f"{bearing}/{condition}_{bearing}_1.mat"


def _digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_rar(bearing: str, cache: Path) -> Path:
    _label, md5 = BEARINGS[bearing]
    rar = cache / "rar" / f"{bearing}.rar"
    if rar.exists() and _digest(rar, "md5") == md5:
        return rar
    rar.parent.mkdir(parents=True, exist_ok=True)
    tmp = rar.with_suffix(".part")
    urllib.request.urlretrieve(ZENODO_URL.format(bearing=bearing), tmp)
    got = _digest(tmp, "md5")
    if got != md5:
        raise OSError(f"{bearing}.rar: MD5 mismatch (got {got}, want {md5})")
    tmp.replace(rar)
    return rar


def fetch(
    bearing: str,
    condition: str,
    cache: Path | str | None = None,
    *,
    download: bool = True,
) -> Path:
    """Checksum-verified local copy of one Paderborn measurement (.mat)."""
    cache = Path(cache) if cache else default_cache()
    name = member(bearing, condition)
    path = cache / name
    want = MAT_SHA256.get(name)
    if path.exists() and want is not None and _digest(path, "sha256") == want:
        return path
    if not download:
        raise FileNotFoundError(f"{path} missing or bad checksum")
    if shutil.which("unar") is None:
        raise OSError("extracting the Paderborn .rar archives needs the 'unar' tool")
    rar = _fetch_rar(bearing, cache)
    subprocess.run(
        ["unar", "-q", "-f", "-o", str(cache), str(rar), name],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    got = _digest(path, "sha256")
    if want is not None and got != want:
        raise OSError(f"{name}: SHA-256 mismatch (got {got})")
    return path


def load_vibration(path: Path | str) -> np.ndarray:
    """The ``vibration_1`` channel (64 kHz) from a Paderborn .mat file."""
    try:
        from scipy.io import loadmat
    except ImportError as e:  # pragma: no cover - depends on environment
        raise ImportError(
            "reading .mat files needs scipy: pip install '.[real]'"
        ) from e
    m = loadmat(str(path))
    keys = [k for k in m if not k.startswith("__")]
    if len(keys) != 1:
        raise ValueError(f"{path}: expected one measurement struct, found {keys}")
    rec = m[keys[0]][0, 0]
    for ch in rec["Y"][0]:
        if str(np.ravel(ch["Name"])[0]) == "vibration_1":
            return np.ravel(ch["Data"]).astype(float)
    raise ValueError(f"{path}: no vibration_1 channel")


def isolated_spikes(x: np.ndarray, frac: float = 0.5) -> int:
    """Count single-sample spikes: samples where the step in and the step out
    both exceed ``frac`` · peak and have opposite signs (the signal jumps away
    and straight back). One such sample sets max|Δx| on its own, so it alone
    can remove fold headroom (recovery needs λ > max|Δx|)."""
    x = np.asarray(x, dtype=float)
    if len(x) < 3:
        return 0
    bar = frac * float(np.max(np.abs(x)))
    d_in, d_out = x[1:-1] - x[:-2], x[2:] - x[1:-1]
    hit = (np.abs(d_in) > bar) & (np.abs(d_out) > bar) & (d_in * d_out < 0)
    return int(np.count_nonzero(hit))


def record_row(name: str, label: str, v: np.ndarray, sr: int) -> dict:
    """Per-record summary: peak, largest step, headroom, kurtosis."""
    pk, dx = float(np.max(np.abs(v))), max_sample_jump(v)
    return {
        "record": name,
        "label": label,
        "sr": sr,
        "n": int(len(v)),
        "peak": pk,
        "max_dx": dx,
        "dx_over_peak": dx / pk,
        "headroom_db": headroom_db(pk, dx),
        "kurtosis": kurtosis(v),
        "isolated_spikes": isolated_spikes(v),
    }


def run_sweep(
    cache: Path | str | None = None, *, download: bool = True, decimate: bool = True
) -> dict:
    """All BEARINGS × CONDITIONS at 64 kHz (and 64→16k), scored by eval_record."""
    cells: list[RealCell] = []
    records = []
    for b, (label, _md5) in BEARINGS.items():
        for cond in CONDITIONS:
            x = load_vibration(fetch(b, cond, cache, download=download))
            variants = [(f"{b}/{cond}@64k", x, SR)]
            if decimate:
                variants.append((f"{b}/{cond}@64→16k", x[::4], SR // 4))
            for name, v, vsr in variants:
                records.append(record_row(name, label, v, vsr))
                cells.extend(eval_record(name, label, v, vsr))
    return {"records": records, "cells": cells, "summary": summarize(cells)}


def write_report(sweep: dict, path: Path | str) -> None:
    out = {
        "source": "Paderborn University KAt Bearing DataCenter via Zenodo 15845309 (CC BY 4.0), vibration_1, 64 kHz, dataset units",
        "assumptions": [
            "Recorded vibration_1 treated as true sensor output; λ = ratio·peak applied in software.",
            "Ideal modulo fold; blind recovery (zero-mean prior); original used only for scoring.",
            "recovered = max|x̂−x| ≤ 1e-6·peak; silent = not recovered and neither slip nor edge flag.",
            "64→16k rows = plain 4:1 subsampling (no anti-alias filter).",
        ],
        "prereg": "artifacts/paderborn/prereg-2026-10-23.md",
        "records": sweep["records"],
        "summary": sweep["summary"],
        "cells": [asdict(c) | {"silent_fail": c.silent_fail} for c in sweep["cells"]],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, indent=2) + "\n")
