"""Spike-origin probe on the Paderborn KAt records (NOTES #8h, 2026-10-25).

Why: the 2026-10-23 sweep (``paderborn.py``) found that single-sample spikes
(49–845 per record on K001/KI04) set max|Δx| ≈ peak and remove fold headroom.
This module tests where they come from and whether a filter in front of the
fold would give the headroom back. Hypotheses, thresholds and seeds are fixed in
``artifacts/paderborn/prereg-2026-10-25.md`` (committed before any result).

- H1 electrical: spike times phase-locked to the 16 kHz inverter switching
  frequency, or coincident with transients on the motor phase currents (same
  .mat file, same 64 kHz raster, sample-aligned).
- H2 mechanical: spike times phase-locked to the shaft frequency or the 6203
  bearing defect frequencies (BPFO/BPFI), with non-kinematic decoy bands as a
  guard against clustered spike times.
- H3 pre-fold filter: causal 4th-order Butterworth low-pass (analog-realisable)
  or a 3-point median (digital-only bound); headroom on the spiky records and
  envelope-spectrum fault-line preservation on KI04/KA04.

Bearing geometry and rig facts: Lessmeier et al., PHME 2016 (Table 1 and
Section 4.1): 8 balls, d = 6.75 mm, D = 28.55 mm, contact angle 0; inverter
switching 16 kHz; PMSM with 4 pole pairs; charge amplifier low-pass 30 kHz.
CPU only. Data are read from the pinned cache; nothing is redistributed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import paderborn as pb
from .foldaudio import max_sample_jump
from .realdata import eval_record, headroom_db, kurtosis

# --- fixed parameters (prereg-2026-10-25.md) --------------------------------

N_BALLS = 8
BALL_D_MM = 6.75
PITCH_D_MM = 28.55
#: ball-pass multipliers for a rotating inner ring, contact angle 0
BPFO_X = N_BALLS / 2 * (1 - BALL_D_MM / PITCH_D_MM)
BPFI_X = N_BALLS / 2 * (1 + BALL_D_MM / PITCH_D_MM)
POLE_PAIRS = 4
PWM_HZ = 16_000.0
PWM_BAND_FRAC = 0.01
KIN_BAND_FRAC = 0.03
DECOY_X = (1.37, 3.71, 5.53)
GRID_STEP_HZ = 0.01
ALPHA = 1e-3
SPIKY_MIN = 10
CUR_WIN = 2
CUR_PCTL = 99.0
CUR_NULL_DRAWS = 2000
SEED = 20261025
H1B_MIN_FRAC = 0.5
H1B_NULL_MULT = 3.0
HEADROOM_TARGET_DB = 3.0
LINE_DROP_DB = 3.0
LINE_MIN_DB = 6.0
ENV_HP_HZ = 500.0
LINE_BG_HZ = 20.0
FILTERS = ("LP10", "LP5", "MED3")
#: EXPLORATORY (post hoc, added after the pre-registered run): mains-related
#: bands (50 Hz supply, 100 Hz = 2 × supply, e.g. rectifier charging) and
#: equal-width high-frequency control bands for the 16 kHz test.
EXPLORATORY_BANDS: dict[str, tuple[float, float]] = {
    "mains50": (50.0, KIN_BAND_FRAC),
    "mains100": (100.0, KIN_BAND_FRAC),
    "ctl8k": (8_000.0, PWM_BAND_FRAC),
    "ctl12k": (12_000.0, PWM_BAND_FRAC),
    "ctl20k": (20_000.0, PWM_BAND_FRAC),
    "ctl24k": (24_000.0, PWM_BAND_FRAC),
}
CURRENT_CHANNELS = ("phase_current_1", "phase_current_2")


def shaft_hz(condition: str) -> float:
    """Nominal shaft frequency from the condition code (N15 → 25 Hz, N09 → 15 Hz)."""
    code = condition.split("_")[0]
    if not (code.startswith("N") and code[1:].isdigit()):
        raise ValueError(f"unrecognised speed code in {condition!r}")
    return int(code[1:]) * 100 / 60.0


def load_channels(path, names) -> dict[str, np.ndarray]:
    """Named channels (as float arrays) from one Paderborn .mat file."""
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
    have = {str(np.ravel(ch["Name"])[0]): ch for ch in rec["Y"][0]}
    missing = [n for n in names if n not in have]
    if missing:
        raise ValueError(f"{path}: missing channels {missing}")
    return {n: np.ravel(have[n]["Data"]).astype(float) for n in names}


def spike_indices(x: np.ndarray, frac: float = 0.5) -> np.ndarray:
    """Sample indices of the spikes counted by ``paderborn.isolated_spikes``."""
    x = np.asarray(x, dtype=float)
    if len(x) < 3:
        return np.zeros(0, dtype=int)
    bar = frac * float(np.max(np.abs(x)))
    d_in, d_out = x[1:-1] - x[:-2], x[2:] - x[1:-1]
    hit = (np.abs(d_in) > bar) & (np.abs(d_out) > bar) & (d_in * d_out < 0)
    return np.flatnonzero(hit) + 1


def vector_strength(idx: np.ndarray, sr: float, freqs: np.ndarray) -> np.ndarray:
    """R(f) = |mean_k exp(2πi f n_k / sr)| for each frequency in ``freqs``."""
    idx = np.asarray(idx, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    if len(idx) == 0:
        return np.zeros(len(freqs))
    t = idx / sr
    out = np.empty(len(freqs))
    step = max(1, 2_000_000 // len(t))
    for a in range(0, len(freqs), step):
        ph = np.outer(freqs[a : a + step], t)
        out[a : a + step] = np.abs(np.exp(2j * np.pi * ph).mean(axis=1))
    return out


@dataclass
class BandTest:
    """Rayleigh test of spike-time phase locking over one frequency band."""

    name: str
    lo_hz: float
    hi_hz: float
    n: int
    r_max: float
    f_at_max: float
    m_eff: int
    p: float

    @property
    def significant(self) -> bool:
        return self.p < ALPHA


def band_test(
    name: str, idx: np.ndarray, sr: float, lo: float, hi: float, duration_s: float
) -> BandTest:
    """Max vector strength over [lo, hi] (grid GRID_STEP_HZ) with a Rayleigh
    p-value Bonferroni-corrected for M = max(1, ceil(BW·T)) frequencies."""
    freqs = np.arange(lo, hi + GRID_STEP_HZ / 2, GRID_STEP_HZ)
    r = vector_strength(idx, sr, freqs)
    k = int(np.argmax(r))
    n = int(len(idx))
    m_eff = max(1, math.ceil((hi - lo) * duration_s))
    p = min(1.0, m_eff * math.exp(-n * float(r[k]) ** 2)) if n else 1.0
    return BandTest(name, lo, hi, n, float(r[k]), float(freqs[k]), m_eff, p)


def periodicity_tests(
    idx: np.ndarray, sr: float, fr: float, duration_s: float
) -> dict[str, BandTest]:
    """All pre-registered band tests: PWM, kinematic targets, decoys, and the
    descriptive electrical-fundamental bands."""
    bands: dict[str, tuple[float, float]] = {
        "pwm16k": (PWM_HZ * (1 - PWM_BAND_FRAC), PWM_HZ * (1 + PWM_BAND_FRAC))
    }
    kin = {"fr": fr, "bpfo": BPFO_X * fr, "bpfi": BPFI_X * fr}
    for i, x in enumerate(DECOY_X):
        kin[f"decoy{i + 1}"] = x * fr
    fe = POLE_PAIRS * fr
    kin["fe"] = fe
    kin["6fe"] = 6 * fe
    for k, f in kin.items():
        bands[k] = (f * (1 - KIN_BAND_FRAC), f * (1 + KIN_BAND_FRAC))
    return {
        k: band_test(k, idx, sr, lo, hi, duration_s) for k, (lo, hi) in bands.items()
    }


def exploratory_tests(idx: np.ndarray, sr: float, duration_s: float) -> dict:
    """EXPLORATORY (not pre-registered): band tests for EXPLORATORY_BANDS plus
    the histogram of spike index mod 4 (one 16 kHz period = 4 samples at 64 kHz;
    a carrier locked to the DAQ clock would load one bin)."""
    out: dict = {
        k: band_test(k, idx, sr, f * (1 - w), f * (1 + w), duration_s)
        for k, (f, w) in EXPLORATORY_BANDS.items()
    }
    out["mod4"] = [int(v) for v in np.bincount(np.asarray(idx) % 4, minlength=4)]
    return out


def current_coincidence(
    idx: np.ndarray, currents: list[np.ndarray], *, seed: int = SEED
) -> dict:
    """Fraction of spikes with a current transient within ±CUR_WIN samples, and
    the same fraction at CUR_NULL_DRAWS random non-spike indices."""
    n = len(currents[0])
    hot = np.zeros(n, dtype=bool)
    for c in currents:
        d = np.abs(np.diff(np.asarray(c, dtype=float), prepend=c[0]))
        hot |= d > np.percentile(d, CUR_PCTL)
    near = np.zeros(n, dtype=bool)
    for k in range(-CUR_WIN, CUR_WIN + 1):
        near |= np.roll(hot, -k)
    near[:CUR_WIN] = near[n - CUR_WIN :] = False  # no wrap-around credit
    excl = np.zeros(n, dtype=bool)
    for k in range(-CUR_WIN, CUR_WIN + 1):
        excl[np.clip(np.asarray(idx) + k, 0, n - 1)] = True
    pool = np.flatnonzero(~excl[CUR_WIN : n - CUR_WIN]) + CUR_WIN
    rng = np.random.default_rng(seed)
    null_idx = rng.choice(pool, size=CUR_NULL_DRAWS, replace=False)
    frac = float(near[idx].mean()) if len(idx) else 0.0
    null = float(near[null_idx].mean())
    return {
        "frac": frac,
        "null_frac": null,
        "evidence": frac >= H1B_MIN_FRAC and frac >= H1B_NULL_MULT * null,
    }


def spike_shape(x: np.ndarray, idx: np.ndarray) -> dict:
    """Descriptive: polarity split and median spike height over the larger
    of its two neighbours (absolute values, mean removed)."""
    x = np.asarray(x, dtype=float) - float(np.mean(x))
    if len(idx) == 0:
        return {"pos": 0, "neg": 0, "height_over_neighbour_med": None}
    h = np.abs(x[idx])
    nb = np.maximum(np.abs(x[idx - 1]), np.abs(x[idx + 1]))
    ratio = h / np.maximum(nb, 1e-12)
    return {
        "pos": int(np.count_nonzero(x[idx] > 0)),
        "neg": int(np.count_nonzero(x[idx] < 0)),
        "height_over_neighbour_med": float(np.median(ratio)),
    }


def apply_filter(x: np.ndarray, name: str, sr: int = pb.SR) -> np.ndarray:
    """Pre-fold filter: ``LP10``/``LP5`` causal 4th-order Butterworth low-pass
    (10 / 5 kHz), ``MED3`` 3-point running median (edges kept)."""
    x = np.asarray(x, dtype=float)
    if name == "MED3":
        y = x.copy()
        y[1:-1] = np.median(np.stack([x[:-2], x[1:-1], x[2:]]), axis=0)
        return y
    if name in ("LP10", "LP5"):
        from scipy.signal import butter, sosfilt

        fc = 10_000.0 if name == "LP10" else 5_000.0
        sos = butter(4, fc, btype="low", fs=sr, output="sos")
        return sosfilt(sos, x)
    raise ValueError(f"unknown filter {name!r}")


def envelope_line_snr_db(x: np.ndarray, sr: int, target_hz: float) -> float:
    """Envelope-spectrum line SNR at ``target_hz`` (±KIN_BAND_FRAC) against the
    median of target ± LINE_BG_HZ outside that band (prereg definition)."""
    from scipy.signal import butter, hilbert, sosfiltfilt

    sos = butter(4, ENV_HP_HZ, btype="high", fs=sr, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, np.asarray(x, dtype=float))))
    spec = np.abs(np.fft.rfft(env - env.mean()))
    f = np.fft.rfftfreq(len(env), 1.0 / sr)
    lo, hi = target_hz * (1 - KIN_BAND_FRAC), target_hz * (1 + KIN_BAND_FRAC)
    line = spec[(f >= lo) & (f <= hi)]
    bg_sel = (np.abs(f - target_hz) <= LINE_BG_HZ) & ~((f >= lo) & (f <= hi))
    bg = float(np.median(spec[bg_sel]))
    return float(20 * np.log10(float(line.max()) / bg))


@dataclass
class RecordProbe:
    """All probe numbers for one 64 kHz record."""

    record: str
    bearing: str
    condition: str
    n_spikes: int
    fr_hz: float
    spiky: bool
    bands: dict[str, BandTest] = field(default_factory=dict)
    exploratory: dict = field(default_factory=dict)
    current: dict | None = None
    shape: dict | None = None
    current_spikes: dict | None = None
    filters: dict[str, dict] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @property
    def decoy_contaminated(self) -> bool:
        return any(self.bands[f"decoy{i + 1}"].significant for i in range(len(DECOY_X)))

    @property
    def h1_evidence(self) -> bool:
        if not self.spiky:
            return False
        return self.bands["pwm16k"].significant or bool(self.current["evidence"])

    @property
    def h2_evidence(self) -> bool:
        if not self.spiky or self.decoy_contaminated:
            return False
        return any(self.bands[k].significant for k in ("fr", "bpfo", "bpfi"))


def fault_target(bearing: str, fr: float) -> float | None:
    """Envelope target for the preservation check: BPFI on KI04, BPFO on KA04."""
    if bearing.startswith("KI"):
        return BPFI_X * fr
    if bearing.startswith("KA"):
        return BPFO_X * fr
    return None


def probe_record(
    bearing: str, condition: str, cache=None, *, download=False
) -> RecordProbe:
    """Run every pre-registered measurement on one record."""
    path = pb.fetch(bearing, condition, cache, download=download)
    ch = load_channels(path, ("vibration_1", *CURRENT_CHANNELS))
    x = ch["vibration_1"]
    sr = pb.SR
    idx = spike_indices(x)
    fr = shaft_hz(condition)
    dur = len(x) / sr
    p = RecordProbe(
        record=pb.member(bearing, condition),
        bearing=bearing,
        condition=condition,
        n_spikes=int(len(idx)),
        fr_hz=fr,
        spiky=len(idx) >= SPIKY_MIN,
    )
    target = fault_target(bearing, fr)
    p.raw = {
        "headroom_db": headroom_db(float(np.max(np.abs(x))), max_sample_jump(x)),
        "kurtosis": kurtosis(x),
        "line_snr_db": envelope_line_snr_db(x, sr, target) if target else None,
    }
    if p.spiky:
        p.bands = periodicity_tests(idx, sr, fr, dur)
        p.exploratory = exploratory_tests(idx, sr, dur)
        cur = [ch[c] for c in CURRENT_CHANNELS]
        p.current = current_coincidence(idx, cur)
        p.shape = spike_shape(x, idx)
        cs = {c: spike_indices(ch[c]) for c in CURRENT_CHANNELS}
        p.current_spikes = {
            c: {"count": int(len(v)), "same_sample": int(len(np.intersect1d(v, idx)))}
            for c, v in cs.items()
        }
    for name in FILTERS:
        y = apply_filter(x, name, sr)
        row = {
            "headroom_db": headroom_db(float(np.max(np.abs(y))), max_sample_jump(y)),
            "kurtosis": kurtosis(y),
            "spikes_left": int(len(spike_indices(y))),
            "line_snr_db": envelope_line_snr_db(y, sr, target) if target else None,
        }
        if p.spiky:
            cells = eval_record(f"{bearing}/{condition}:{name}", "filtered", y, sr)
            row["cells"] = len(cells)
            row["recovered"] = sum(c.recovered for c in cells)
            row["silent_fail"] = sum(c.silent_fail for c in cells)
            row["rule_correct"] = sum(c.rule_ok == c.recovered for c in cells)
        p.filters[name] = row
    return p


def _count_verdict(n_ev: int, n_other: int, n: int) -> str:
    if n_ev <= 2:
        return "FALSIFIED"
    if n_ev >= 6 and n_other <= 2 and n == 8:
        return "HELD"
    return "INCONCLUSIVE"


def verdicts(probes: list[RecordProbe]) -> dict:
    """Apply the pre-registered decision rules to a list of record probes."""
    spiky = [p for p in probes if p.spiky]
    n = len(spiky)
    h1 = sum(p.h1_evidence for p in spiky)
    h2 = sum(p.h2_evidence for p in spiky)
    out = {
        "spiky_records": n,
        "h1_evidence": h1,
        "h2_evidence": h2,
        "decoy_contaminated": sum(p.decoy_contaminated for p in spiky),
        # breakdowns (same rules, reported for transparency)
        "h1a_pwm_band": sum(p.bands["pwm16k"].significant for p in spiky),
        "h1b_current": sum(bool(p.current["evidence"]) for p in spiky),
        "h2_ignoring_decoys": sum(
            any(p.bands[k].significant for k in ("fr", "bpfo", "bpfi")) for p in spiky
        ),
        "H1": _count_verdict(h1, h2, n),
        "H2": _count_verdict(h2, h1, n),
        "filters": {},
    }
    for name in FILTERS:
        good = sum(p.filters[name]["headroom_db"] >= HEADROOM_TARGET_DB for p in spiky)
        silent = sum(p.filters[name]["silent_fail"] for p in spiky)
        rule_ok = all(
            p.filters[name]["rule_correct"] == p.filters[name]["cells"] for p in spiky
        )
        lost, testable = [], 0
        for p in probes:
            raw = p.raw["line_snr_db"]
            if raw is None or raw < LINE_MIN_DB:
                continue
            testable += 1
            if p.filters[name]["line_snr_db"] < raw - LINE_DROP_DB:
                lost.append(p.record)
        if good <= 4 or lost or silent:
            v = "FALSIFIED"
        elif good >= 7 and rule_ok:
            v = "HELD"
        else:
            v = "INCONCLUSIVE"
        out["filters"][name] = {
            "headroom_ok": good,
            "silent_fail": silent,
            "rule_all_correct": rule_ok,
            "lines_testable": testable,
            "lines_lost": lost,
            "verdict": v,
        }
    lp = [out["filters"][k]["verdict"] for k in ("LP10", "LP5")]
    if "HELD" in lp:
        out["H3"] = "HELD"
    elif all(v == "FALSIFIED" for v in lp):
        out["H3"] = "FALSIFIED"
    else:
        out["H3"] = "INCONCLUSIVE"
    return out


def run_probe(cache=None, *, download=False) -> list[RecordProbe]:
    """Probe all 12 pinned 64 kHz records (BEARINGS × CONDITIONS)."""
    return [
        probe_record(b, c, cache, download=download)
        for b in pb.BEARINGS
        for c in pb.CONDITIONS
    ]
