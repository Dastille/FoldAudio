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
    # held-out measurements _2.._5 (NOTES #8i), pinned 2026-10-26 before analysis
    "K001/N15_M07_F10_K001_2.mat": "9ed50c2cf9b280e65471ee9dde35b280b5deb43a6fc861fabd7935bd772f969a",
    "K001/N15_M07_F10_K001_3.mat": "721a04849ea72d90bcf623f80b2d6ca8126f3b13910f34319495af0554795549",
    "K001/N15_M07_F10_K001_4.mat": "d4ee7fef3b3f2b1f310324034ee22894a84163d7b078c63210f77ffa589f9dc0",
    "K001/N15_M07_F10_K001_5.mat": "f47c9c9de878ba24479b7f8c1cb48c813354ec71a57112d35b1d87986124fe55",
    "K001/N09_M07_F10_K001_2.mat": "353451b91afc757be1883b4af2ba36724d58534a24b310662be7cd93dba156bb",
    "K001/N09_M07_F10_K001_3.mat": "6c4d86af80479b864b57966669574a00b218370b1e75f75411bbc50599e60dd3",
    "K001/N09_M07_F10_K001_4.mat": "8396cebc4fe63ee49b4282ae6e4f6989ed5f9fdd65dcec9b89c13a6ff4ab201e",
    "K001/N09_M07_F10_K001_5.mat": "44c8d4df1c288ba321c10795122da1cacb37471302aa41183b131f655d90088d",
    "K001/N15_M01_F10_K001_2.mat": "a47179a2266ebb83132ccd844cc6b685cdfd5355c9d6fd53a13f1744d9e05304",
    "K001/N15_M01_F10_K001_3.mat": "2f385585e485962b0563651cae9c72c4ff178ceec5938950e0d87e2b754b9d94",
    "K001/N15_M01_F10_K001_4.mat": "12746ba1bf85716ac7ae5c8e182792b412de83d82bf8daa0aef3ccf1ada3ad32",
    "K001/N15_M01_F10_K001_5.mat": "19e5d6b775a3a810640adaef02354bced5f5dcb70f93b351f299ed92f1d96e91",
    "K001/N15_M07_F04_K001_2.mat": "b0eea67e384a64b4585273a81dc48fd6093c57a98e2e25966187b6c914e73b72",
    "K001/N15_M07_F04_K001_3.mat": "be5b0d6ec89ab7d6fbbe72a7600148fe5a11b489e3a9865c0717d82374418898",
    "K001/N15_M07_F04_K001_4.mat": "c83b69d9d725bb53ff59eff2f43c7a29316a01f6f449db29036c0a4edc0054c3",
    "K001/N15_M07_F04_K001_5.mat": "c9baa4c611ef25d37abd2ead35caf0f655cb9da111e915b187f1ccb2c1226501",
    "KA04/N15_M07_F10_KA04_2.mat": "22210c904d75338060e03859cab6c6c55c1f509ff250e266f178eb198b210017",
    "KA04/N15_M07_F10_KA04_3.mat": "6ae0d36410a6dd32ac307ab8ffae4d81b867b433b01ab24dcc1a12172dff2f31",
    "KA04/N15_M07_F10_KA04_4.mat": "700369d50867284ed9969d730354d4fe9e60b29d7e90e568359fcbee26615e07",
    "KA04/N15_M07_F10_KA04_5.mat": "c6dc56d18a2704193756e502b656ca21781b6ec983e4b36c5a2ef7c939d1cbfa",
    "KA04/N09_M07_F10_KA04_2.mat": "4e66934fe250625318364b3973468faedd555b66156f8d9212f5f14a2fd1f4a5",
    "KA04/N09_M07_F10_KA04_3.mat": "2e543cbd0d246ac0eff03b95f4d9e0e94a72c39000d70c93d6608239ab03d259",
    "KA04/N09_M07_F10_KA04_4.mat": "09426652f1cd315bc515fe78efda2b990c8c6b89bcf1e77db721bbfe638e5638",
    "KA04/N09_M07_F10_KA04_5.mat": "8bd04b23789c5f09a360c144784223f857c462ac7df113450061ecef66ebd9db",
    "KA04/N15_M01_F10_KA04_2.mat": "c0d941668d8f08ab37c3d2c248a43abbed2faea28b7823e1a3efeec29eb139dc",
    "KA04/N15_M01_F10_KA04_3.mat": "35c5de1a76b9016de9efda509006d91d9446e25765f6478a4d46914b4c8f4d98",
    "KA04/N15_M01_F10_KA04_4.mat": "51aeb6a22b9d40bf7ef5e42e71fd6b4034374cf51f0b782ecb440dbfbbca81db",
    "KA04/N15_M01_F10_KA04_5.mat": "e2b542b321ecfb15233795903eae2b45bc2d72c42d7cb5066952213e77f87ac9",
    "KA04/N15_M07_F04_KA04_2.mat": "e9186aefeb54f3ed36e59160b0cd5f38d63c6516ebd412948e92b924a0fcdc52",
    "KA04/N15_M07_F04_KA04_3.mat": "fe7426500684250bf32bce968b79d0e254bf3b56792745790386e7f3ccef04e6",
    "KA04/N15_M07_F04_KA04_4.mat": "fbf129ea0e125092f5e82c853840e63876f2e0a4368f5088267c4efbceba458b",
    "KA04/N15_M07_F04_KA04_5.mat": "7d3cc4032c59523404faf152596cd6b9c6f97b93b88938f49f617ab4b5b9abc6",
    "KI04/N15_M07_F10_KI04_2.mat": "21e8db6824fb887c13ac5fefcd678d81b70c51734d6fc9a24fb580a9acf3d2dc",
    "KI04/N15_M07_F10_KI04_3.mat": "160e9630ad5c2d9c8378eed1ee5d596177d85d31aad1bbb3f396b8305aadb5bd",
    "KI04/N15_M07_F10_KI04_4.mat": "6c8cf4dc8f8df64561c9ad653f6d2bf0c48fd9d1a534276a22ebc13fa2d5b27d",
    "KI04/N15_M07_F10_KI04_5.mat": "65844dfbaf87208e490960fb0f7ae9c8f69dc6d85a171becf76abfa5629213bb",
    "KI04/N09_M07_F10_KI04_2.mat": "c993511853ff0a4326896586e0d21e06e0f3ad56be2c08f7a3e204a4e00ab9e9",
    "KI04/N09_M07_F10_KI04_3.mat": "dfb89ba32084c6563b11569c6413368e5cf24f907f9dc9711dcb5e11a20f75ca",
    "KI04/N09_M07_F10_KI04_4.mat": "3921cd85b2c14e36124fe83434ed742455d1ece94db4997e7af753888e96421a",
    "KI04/N09_M07_F10_KI04_5.mat": "bcb8337e6cac324c82712abf92d2a48184fc6bcbd07aaa99cee0423cfe99da00",
    "KI04/N15_M01_F10_KI04_2.mat": "12ba66b4a46a7e80edda7bf1488cd466b6d1f6e74764b98ea54cdcfc407e0293",
    "KI04/N15_M01_F10_KI04_3.mat": "925ed9eb060749da30e696e1b5e1fabf3504fc4c3aaf81803e6762c832672659",
    "KI04/N15_M01_F10_KI04_4.mat": "bf5097d71828555e329fc66fe4f93742154ac50c50c7efa296207a79ff399631",
    "KI04/N15_M01_F10_KI04_5.mat": "12b7c250d7ea6581701d2222610a0ddd12af9aa79ab93be96c97e994924c7149",
    "KI04/N15_M07_F04_KI04_2.mat": "4c3bb2a4c26da6655fdc75678b3d744058b05aaf19ee96c49a301971f5a5fd0d",
    "KI04/N15_M07_F04_KI04_3.mat": "bc4020a6282482aad661690b204ad133dcee45d6b6c36073a26beb94050ddb28",
    "KI04/N15_M07_F04_KI04_4.mat": "cdbfa5ea85ab3befa445d83e8787635b796da9fe6b6b7ad9f43fcefb0d0ae39c",
    "KI04/N15_M07_F04_KI04_5.mat": "469c137ee402d25f97781110ff07338ca2f10191750fcdca82a7de2693dab6b0",
}

#: Environment variable that overrides the Paderborn cache directory.
CACHE_ENV = "FOLDCRYPT_PADERBORN_CACHE"


def default_cache() -> Path:
    """``$FOLDCRYPT_PADERBORN_CACHE`` if set, else ``~/.cache/foldcrypt/paderborn``."""
    env = os.environ.get(CACHE_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "foldcrypt" / "paderborn"


#: held-out measurement numbers used by the 2026-10-26 confirmation (NOTES #8i)
HELDOUT_MEASUREMENTS = (2, 3, 4, 5)


def member(bearing: str, condition: str, meas: int = 1) -> str:
    """Archive member path, e.g. ``K001/N15_M07_F10_K001_1.mat``."""
    return f"{bearing}/{condition}_{bearing}_{meas}.mat"


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
    meas: int = 1,
) -> Path:
    """Checksum-verified local copy of one Paderborn measurement (.mat).

    ``meas`` selects the measurement number within the operating condition
    (1 for the 2026-10-23 sweep; 2–5 for the held-out confirmation)."""
    cache = Path(cache) if cache else default_cache()
    name = member(bearing, condition, meas)
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
