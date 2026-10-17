"""ShockDAQ on real bearing-fault vibration recordings (CWRU Bearing Data Center).

Purpose (NOTES #3/#9, 2026-10-14 weekday slice): every earlier ShockDAQ number
came from synthetic generators. This module runs the same fold → blind unwrap →
self-check chain on public, measured accelerometer records from the Case Western
Reserve University (CWRU) Bearing Data Center, so the recovery condition is
tested against real impact waveforms, real sensor noise and real DAQ
quantization.

Method (named ASSUMPTIONS — keep honest):
1. The recorded drive-end accelerometer channel (units: g) is treated as the
   true sensor output x. A fold rail λ is placed BELOW the record's peak
   (λ = r · peak, r ∈ RATIOS) to emulate an under-ranged input stage. The
   original CWRU front end did not overload; overload is applied in software.
2. Fold is the ideal modulo fold (foldaudio.fold_capture); recovery is the
   blind path a live DAQ would run (blind_level.recover_blind, AC-coupling
   zero-mean prior) — the recorded original is used only for scoring.
3. "Recovered" means max |x̂ − x| ≤ 1e-6 · peak (ideal fold is lossless when
   the unwrap holds). Anything else is a failure; a failure that neither the
   slip nor the edge check flags is a SILENT failure.
4. Sample rates are those published by CWRU: 48 kHz for the normal-baseline
   and 48k drive-end fault files, 12 kHz for the 12k drive-end fault files.
   A "48→12 kHz" row decimates a 48 kHz record by plain 4:1 subsampling (no
   anti-alias filter — this reproduces what a slower converter would sample of
   the same physical event; an anti-alias filter would lower peaks and slew).
5. The CWRU files are NOT redistributed here. They are downloaded on demand from
   engineering.case.edu and checked against the SHA-256 digests below.
   Reading MATLAB .mat files needs scipy (optional extra: pip install .[real]).
6. CPU only. No Parrot / GPU.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .blind_level import edge_flag, recover_blind, slip_flag
from .foldaudio import fold_capture, hard_clip, max_sample_jump, snr_db

CWRU_URL = "https://engineering.case.edu/sites/default/files/{id}.mat"

# id → (sample rate, label, sha256 of the .mat as downloaded 2026-10-14)
CWRU_FILES: dict[int, tuple[int, str, str]] = {
    97: (
        48000,
        "normal, 0 hp",
        "16bf48babcf1c7ac224bc1a81cd9eafdb27e42d5cf559761907e067e8eeadf3c",
    ),
    109: (
        48000,
        "inner race 0.007 in",
        "daddef5f784879becdf8fefbe2453f11c3cfc8d061a2a671da2f546d1bb48460",
    ),
    122: (
        48000,
        "ball 0.007 in",
        "f392129bf3b43360b964d4e5b3479d0797d1647af8359934b0f56b9abab4739a",
    ),
    135: (
        48000,
        "outer race 0.007 in @6",
        "5a1c3ceec1f2b58af9e01051e425aa9d31dd018f58a8d31cda25bbdb1ac6dca9",
    ),
    213: (
        48000,
        "inner race 0.021 in",
        "6afb81f36a9efcdd370a52166d71c13cb42278c7de22752c81d4b2a22fa133f0",
    ),
    226: (
        48000,
        "ball 0.021 in",
        "fc78f08085760f2e17bcf7efe486b3a278e108093cd184acf278daecad6765e4",
    ),
    238: (
        48000,
        "outer race 0.021 in @6",
        "63209a4057f199beb42beedf5b4481987fdb3ac746c46777dd385d689bc481df",
    ),
    105: (
        12000,
        "inner race 0.007 in",
        "f80b0ea04fd06b372a0eaec7c056543ea37e4bb4727a5b173d2a5bacd2aa9cab",
    ),
    118: (
        12000,
        "ball 0.007 in",
        "b00628f8dd8d1d930af77fa465d1e5cdb385fe259489053f91f3680bda7f640e",
    ),
    130: (
        12000,
        "outer race 0.007 in @6",
        "35a095307d0971477049b343a1b5981dde465a58fb7f233ad89b035068c1717d",
    ),
    209: (
        12000,
        "inner race 0.021 in",
        "9f723d6d9d2eba714c6dc50f99321dffa73d8b1e4d3605675b2c2251511eff80",
    ),
    222: (
        12000,
        "ball 0.021 in",
        "fcc0ee740fa123b1f4683f555458891719efb2857afd9fdee63e8fde0ed14469",
    ),
    234: (
        12000,
        "outer race 0.021 in @6",
        "ebcbdb96612e8085bbdbf81f0e5e8e8a8d1a693d1ec559c4894f7792771aa9b2",
    ),
}

# Rail as a fraction of the record's peak (1.0 = no overload).
RATIOS = (0.8, 0.6, 0.5, 0.4, 0.33, 0.25)
EXACT_TOL = 1e-6


def default_cache() -> Path:
    return Path.home() / ".cache" / "foldcrypt" / "cwru"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(
    file_id: int, cache: Path | str | None = None, *, download: bool = True
) -> Path:
    """Return a checksum-verified local copy of CWRU file `file_id`."""
    sr, _label, digest = CWRU_FILES[file_id]
    cache = Path(cache) if cache else default_cache()
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{file_id}.mat"
    if path.exists() and _sha256(path) == digest:
        return path
    if not download:
        raise FileNotFoundError(
            f"{path} missing or bad checksum (run without --offline)"
        )
    last = None
    for _ in range(3):  # the CWRU server sometimes truncates responses
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(CWRU_URL.format(id=file_id), tmp)
        if _sha256(tmp) == digest:
            tmp.replace(path)
            return path
        last = _sha256(tmp)
    raise OSError(f"CWRU {file_id}: checksum mismatch after 3 tries (got {last})")


def load_de(path: Path | str) -> np.ndarray:
    """Drive-end accelerometer channel (g) from a CWRU .mat file."""
    try:
        from scipy.io import loadmat
    except ImportError as e:  # pragma: no cover - depends on environment
        raise ImportError(
            "reading CWRU .mat files needs scipy: pip install '.[real]'"
        ) from e
    m = loadmat(str(path))
    keys = [k for k in m if k.endswith("_DE_time")]
    if len(keys) != 1:
        raise ValueError(f"{path}: expected one *_DE_time channel, found {keys}")
    return np.ravel(m[keys[0]]).astype(float)


def kurtosis(x: np.ndarray) -> float:
    """Plain (non-excess) kurtosis — the standard bearing-impact indicator."""
    x = np.asarray(x, dtype=float) - np.mean(x)
    v = np.mean(x * x)
    return float(np.mean(x**4) / (v * v)) if v > 0 else 0.0


def crest_factor(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    rms = float(np.sqrt(np.mean(x * x)))
    return float(np.max(np.abs(x)) / rms) if rms > 0 else 0.0


@dataclass
class RealCell:
    record: str
    label: str
    sr: int
    ratio: float  # λ / peak
    lam: float  # g
    peak: float  # g
    max_dx: float  # g, largest sample-to-sample step of the record
    rule_ok: bool  # max_dx < λ (exact-recovery condition, §4.1)
    recovered: bool  # max |x̂ − x| ≤ EXACT_TOL · peak
    slip: bool
    edge: bool
    snr_clip_db: float
    snr_fold_db: float
    kurt_true: float
    kurt_clip: float
    kurt_fold: float
    crest_true: float
    crest_clip: float
    crest_fold: float

    @property
    def flagged(self) -> bool:
        return self.slip or self.edge

    @property
    def silent_fail(self) -> bool:
        return (not self.recovered) and not self.flagged

    @property
    def slip_false_alarm(self) -> bool:
        return self.recovered and self.slip


def eval_record(
    record: str, label: str, x: np.ndarray, sr: int, ratios=RATIOS
) -> list[RealCell]:
    x = np.asarray(x, dtype=float)
    peak = float(np.max(np.abs(x)))
    dx = max_sample_jump(x)
    kt, ct = kurtosis(x), crest_factor(x)
    cells = []
    for r in ratios:
        lam = r * peak
        y = fold_capture(x, lam)
        xh, _k = recover_blind(y, lam)
        c = hard_clip(x, lam)
        cells.append(
            RealCell(
                record=record,
                label=label,
                sr=sr,
                ratio=r,
                lam=lam,
                peak=peak,
                max_dx=dx,
                rule_ok=dx < lam,
                recovered=bool(np.max(np.abs(xh - x)) <= EXACT_TOL * peak),
                slip=slip_flag(xh, lam),
                edge=edge_flag(y, lam),
                snr_clip_db=snr_db(x, c),
                snr_fold_db=snr_db(x, xh),
                kurt_true=kt,
                kurt_clip=kurtosis(c),
                kurt_fold=kurtosis(xh),
                crest_true=ct,
                crest_clip=crest_factor(c),
                crest_fold=crest_factor(xh),
            )
        )
    return cells


def headroom_db(peak: float, max_dx: float) -> float:
    """Extra input range fold can buy on this record: 20·log10(peak / max_dx).

    Recovery needs λ > max_dx; overload needs λ < peak. ≤ 0 dB → fold cannot
    recover ANY overload of this waveform at this sample rate.
    """
    return float(20.0 * np.log10(peak / max_dx))


def run_real_sweep(
    cache: Path | str | None = None,
    *,
    download: bool = True,
    ids=None,
    decimate: bool = True,
) -> dict:
    ids = list(ids) if ids is not None else list(CWRU_FILES)
    cells: list[RealCell] = []
    records = []
    for fid in ids:
        sr, label, _ = CWRU_FILES[fid]
        x = load_de(fetch(fid, cache, download=download))
        variants = [(f"{fid}@{sr // 1000}k", x, sr)]
        if decimate and sr == 48000:
            variants.append((f"{fid}@48→12k", x[::4], 12000))
        for name, v, vsr in variants:
            pk, dx = float(np.max(np.abs(v))), max_sample_jump(v)
            records.append(
                {
                    "record": name,
                    "label": label,
                    "sr": vsr,
                    "n": int(len(v)),
                    "peak_g": pk,
                    "max_dx_g": dx,
                    "dx_over_peak": dx / pk,
                    "headroom_db": headroom_db(pk, dx),
                    "kurtosis": kurtosis(v),
                }
            )
            cells.extend(eval_record(name, label, v, vsr))
    return {"records": records, "cells": cells, "summary": summarize(cells)}


def summarize(cells: list[RealCell]) -> dict:
    n = len(cells)
    return {
        "cells": n,
        "rule_correct": sum(c.rule_ok == c.recovered for c in cells),
        "recovered": sum(c.recovered for c in cells),
        "failed": sum(not c.recovered for c in cells),
        "failed_flagged": sum((not c.recovered) and c.flagged for c in cells),
        "silent_fail": sum(c.silent_fail for c in cells),
        "slip_false_alarm": sum(c.slip_false_alarm for c in cells),
        "edge_conservative": sum(c.recovered and c.edge and not c.slip for c in cells),
    }


def format_records(records: list[dict]) -> str:
    hdr = f"{'record':<12} {'sr':>6} {'label':<24} {'peak g':>7} {'maxΔ g':>7} {'Δ/peak':>6} {'headroom':>8} {'kurt':>5}"
    lines = [hdr, "-" * len(hdr)]
    for r in records:
        hr = f"{r['headroom_db']:+.1f} dB" if r["headroom_db"] > 0 else "none"
        lines.append(
            f"{r['record']:<12} {r['sr']:>6} {r['label']:<24} {r['peak_g']:7.3f} "
            f"{r['max_dx_g']:7.3f} {r['dx_over_peak']:6.2f} {hr:>8} {r['kurtosis']:5.1f}"
        )
    return "\n".join(lines)


def format_cells(cells: list[RealCell]) -> str:
    hdr = (
        f"{'record':<12} {'λ/pk':>5} {'rule':>4} {'rec':>4} {'flag':>9} "
        f"{'SNR_c':>6} {'SNR_f':>6} {'kurt t/c/f':>16} {'crest t/c/f':>16}"
    )
    lines = [hdr, "-" * len(hdr)]
    for c in cells:
        fl = "+".join(t for t, on in (("SLIP", c.slip), ("EDGE", c.edge)) if on) or "no"
        snr_f = "exact" if c.recovered else f"{c.snr_fold_db:6.1f}"
        lines.append(
            f"{c.record:<12} {c.ratio:5.2f} {'ok' if c.rule_ok else 'NO':>4} "
            f"{'yes' if c.recovered else 'NO':>4} {fl:>9} {c.snr_clip_db:6.1f} {snr_f:>6} "
            f"{c.kurt_true:5.1f}/{c.kurt_clip:4.1f}/{c.kurt_fold:5.1f} "
            f"{c.crest_true:5.1f}/{c.crest_clip:4.1f}/{c.crest_fold:5.1f}"
        )
    return "\n".join(lines)


def write_report(sweep: dict, path: Path | str) -> None:
    out = {
        "source": "CWRU Bearing Data Center (engineering.case.edu/bearingdatacenter), drive-end accelerometer, units g",
        "assumptions": [
            "Recorded DE channel treated as true sensor output; fold rail λ = ratio·peak applied in software (the CWRU front end did not overload).",
            "Ideal modulo fold; blind recovery (AC-coupling zero-mean prior); original used only for scoring.",
            "recovered = max|x̂−x| ≤ 1e-6·peak; silent = not recovered and neither slip nor edge flag.",
            "48→12k rows = plain 4:1 subsampling of the 48 kHz record (no anti-alias filter).",
        ],
        "records": sweep["records"],
        "summary": sweep["summary"],
        "cells": [asdict(c) | {"silent_fail": c.silent_fail} for c in sweep["cells"]],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, indent=2) + "\n")
