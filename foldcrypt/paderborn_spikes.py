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
    bearing: str, condition: str, cache=None, *, download=False, meas: int = 1
) -> RecordProbe:
    """Run every pre-registered measurement on one record (measurement ``meas``)."""
    path = pb.fetch(bearing, condition, cache, download=download, meas=meas)
    ch = load_channels(path, ("vibration_1", *CURRENT_CHANNELS))
    x = ch["vibration_1"]
    sr = pb.SR
    idx = spike_indices(x)
    fr = shaft_hz(condition)
    dur = len(x) / sr
    p = RecordProbe(
        record=pb.member(bearing, condition, meas),
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


# --- held-out confirmation (prereg-2026-10-26-heldout.md, NOTES #8i) ---------

#: R1/R1b/R2 "replicates" bar and "fails" bar, as fractions of spiky records
REPL_HELD_FRAC = 0.90
REPL_FAIL_FRAC = 0.50
#: R1b: motor band (f_e) must be significant on at most this fraction to hold,
#: and at least FE_FAIL_FRAC falsifies
FE_HELD_FRAC = 0.25
FE_FAIL_FRAC = 0.50
R1B_MIN_RECORDS = 4
#: R3: H2 evidence fraction that keeps / overturns the 10-25 verdict
H2_ABSENT_FRAC = 0.25
H2_PRESENT_FRAC = 0.75
#: R4: LP10 headroom pass fraction (the 7-of-8 bar) and fail fraction
LP_HELD_FRAC = 7 / 8
LP_FAIL_FRAC = 0.50


def _frac_verdict(k: int, n: int, held: float, fail: float) -> str:
    if n == 0:
        return "UNTESTABLE"
    if k >= held * n:
        return "HELD"
    if k <= fail * n:
        return "FALSIFIED"
    return "INCONCLUSIVE"


def _fe_band(p: RecordProbe) -> BandTest:
    return p.bands["fe"]


def heldout_verdicts(probes: list[RecordProbe]) -> dict:
    """Apply the 2026-10-26 held-out decision rules (R1, R1b, R2, R3, R4)."""
    spiky = [p for p in probes if p.spiky]
    s = len(spiky)
    m100 = sum(p.exploratory["mains100"].significant for p in spiky)
    pwm = sum(p.bands["pwm16k"].significant for p in spiky)
    h2 = sum(p.h2_evidence for p in spiky)
    n09 = [p for p in spiky if p.condition.startswith("N09")]
    n09_100 = sum(p.exploratory["mains100"].significant for p in n09)
    n09_fe = sum(_fe_band(p).significant for p in n09)
    if len(n09) < R1B_MIN_RECORDS:
        r1b = "UNTESTABLE"
    elif n09_100 >= REPL_HELD_FRAC * len(n09) and n09_fe <= FE_HELD_FRAC * len(n09):
        r1b = "HELD"
    elif n09_100 <= REPL_FAIL_FRAC * len(n09) or n09_fe >= FE_FAIL_FRAC * len(n09):
        r1b = "FALSIFIED"
    else:
        r1b = "INCONCLUSIVE"
    if s == 0:
        r3 = "UNTESTABLE"
    elif h2 <= H2_ABSENT_FRAC * s:
        r3 = "HELD"
    elif h2 >= H2_PRESENT_FRAC * s:
        r3 = "FALSIFIED"
    else:
        r3 = "INCONCLUSIVE"
    filters = {}
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
        if s == 0:
            v = "UNTESTABLE"
        elif good <= LP_FAIL_FRAC * s or lost or silent:
            v = "FALSIFIED"
        elif good >= LP_HELD_FRAC * s and rule_ok:
            v = "HELD"
        else:
            v = "INCONCLUSIVE"
        filters[name] = {
            "headroom_ok": good,
            "silent_fail": silent,
            "rule_all_correct": rule_ok,
            "lines_testable": testable,
            "lines_lost": lost,
            "verdict": v if name == "LP10" else f"descriptive ({v} under R4 bars)",
        }
    return {
        "records": len(probes),
        "spiky_records": s,
        "mains100_locked": m100,
        "pwm16k_locked": pwm,
        "h2_evidence": h2,
        "decoy_contaminated": sum(p.decoy_contaminated for p in spiky),
        "n09_spiky": len(n09),
        "n09_mains100_locked": n09_100,
        "n09_fe_locked": n09_fe,
        "R1": _frac_verdict(m100, s, REPL_HELD_FRAC, REPL_FAIL_FRAC),
        "R1b": r1b,
        "R2": _frac_verdict(pwm, s, REPL_HELD_FRAC, REPL_FAIL_FRAC),
        "R3": r3,
        "R4": filters["LP10"]["verdict"],
        "filters": filters,
    }


def run_heldout(cache=None, *, download=False) -> list[RecordProbe]:
    """Probe the 48 held-out records (BEARINGS × CONDITIONS × measurements 2–5)."""
    return [
        probe_record(b, c, cache, download=download, meas=m)
        for b in pb.BEARINGS
        for c in pb.CONDITIONS
        for m in pb.HELDOUT_MEASUREMENTS
    ]


# --- spike phase vs the 100 Hz current ripple (prereg-2026-10-27-phase.md, #8j) ---

RIPPLE_BAND_HZ = (95.0, 105.0)
REF_LINE_HZ = (98.0, 102.0)
REF_BG_HZ = (80.0, 120.0)
REF_MIN_DB = 10.0
EDGE_TRIM_S = 0.1
PHASE_SEED = 20261027
PHASE_NULL_DRAWS = 2000
#: R for spikes uniform within a ±90° window (half cycle)
R_BURST = 2 / math.pi
#: R ceiling for sinusoidal gating, probability ∝ 1 + a·cos θ with a ≤ 1
R_SPREAD = 0.5
P1_HELD_FRAC = 0.90
P1_FAIL_FRAC = 0.50
R_BETWEEN_HELD = 0.8
R_BETWEEN_FAIL = 0.5
P_BETWEEN_FAIL = 0.05
NULL_B_MAX_P = 0.01
NULL_A_MAX_R99 = 0.2
P3_HELD_DEG = 45.0
P3_FAIL_DEG = 90.0


def current_magnitude(i1: np.ndarray, i2: np.ndarray) -> np.ndarray:
    """Current space-vector magnitude |i_s| from two phase currents of a
    3-wire machine (i3 = −i1 − i2), each with its record mean removed."""
    a = np.asarray(i1, dtype=float) - float(np.mean(i1))
    b = np.asarray(i2, dtype=float) - float(np.mean(i2))
    beta = (a + 2 * b) / math.sqrt(3)
    return np.hypot(a, beta)


def ripple_line_db(m: np.ndarray, sr: float) -> float:
    """100 Hz line of ``m`` (Hann-windowed amplitude spectrum, max over
    REF_LINE_HZ) over the median of REF_BG_HZ outside that band, in dB."""
    m = np.asarray(m, dtype=float)
    spec = np.abs(np.fft.rfft((m - m.mean()) * np.hanning(len(m))))
    f = np.fft.rfftfreq(len(m), 1.0 / sr)
    in_line = (f >= REF_LINE_HZ[0]) & (f <= REF_LINE_HZ[1])
    bg_sel = (f >= REF_BG_HZ[0]) & (f <= REF_BG_HZ[1]) & ~in_line
    return float(20 * np.log10(spec[in_line].max() / np.median(spec[bg_sel])))


def ripple_phase(m: np.ndarray, sr: float) -> tuple[np.ndarray, float]:
    """Instantaneous phase (rad) of the zero-phase 95–105 Hz band-pass of
    ``m``; phase 0 is the ripple maximum. Also returns the ripple amplitude
    (median Hilbert envelope) over mean(m), i.e. the modulation depth."""
    from scipy.signal import butter, hilbert, sosfiltfilt

    m = np.asarray(m, dtype=float)
    sos = butter(4, RIPPLE_BAND_HZ, btype="bandpass", fs=sr, output="sos")
    r = sosfiltfilt(sos, m - m.mean())
    z = hilbert(r)
    depth = float(np.median(np.abs(z)) / max(float(np.mean(m)), 1e-12))
    return np.angle(z), depth


def circ_stats(theta: np.ndarray) -> tuple[float, float, float]:
    """(R, mean phase in rad, Rayleigh p = exp(−N R²)) for angles ``theta``."""
    theta = np.asarray(theta, dtype=float)
    if len(theta) == 0:
        return 0.0, 0.0, 1.0
    z = np.exp(1j * theta).mean()
    r = float(abs(z))
    return r, float(np.angle(z)), float(math.exp(-len(theta) * r * r))


def trim_indices(idx: np.ndarray, n: int, sr: float) -> tuple[np.ndarray, int, int]:
    """Drop indices within EDGE_TRIM_S of either end; returns (kept, lo, hi)
    with the usable window [lo, hi)."""
    edge = int(round(EDGE_TRIM_S * sr))
    lo, hi = edge, n - edge
    idx = np.asarray(idx)
    return idx[(idx >= lo) & (idx < hi)], lo, hi


def null_random_r(
    phase: np.ndarray, n_spk: int, lo: int, hi: int, rng, draws: int = PHASE_NULL_DRAWS
) -> np.ndarray:
    """Null A: R_ref for ``draws`` sets of ``n_spk`` uniform random indices in
    [lo, hi) (without replacement within a draw)."""
    out = np.empty(draws)
    for d in range(draws):
        k = rng.choice(hi - lo, size=n_spk, replace=False) + lo
        out[d] = abs(np.exp(1j * phase[k]).mean())
    return out


@dataclass
class PhaseRecord:
    """Spike phase against the 100 Hz current-magnitude ripple, one record."""

    record: str
    condition: str
    meas: int
    n_spikes: int
    ref_db: float
    ref_valid: bool
    depth: float
    r: float = 0.0
    mu: float = 0.0
    p: float = 1.0
    frac45: float = 0.0
    null_r99: float = 0.0
    #: phase of every kept spike (rad); used by the across-record shift null
    theta: np.ndarray = field(default_factory=lambda: np.zeros(0), repr=False)
    #: reference phase over the usable window and its offset, for null B
    _phase: np.ndarray | None = field(default=None, repr=False)
    _idx: np.ndarray | None = field(default=None, repr=False)
    _lo: int = 0
    _hi: int = 0

    @property
    def usable(self) -> bool:
        return self.ref_valid and self.n_spikes >= SPIKY_MIN


def phase_from_signals(
    name: str,
    condition: str,
    meas: int,
    x: np.ndarray,
    i1: np.ndarray,
    i2: np.ndarray,
    sr: float = pb.SR,
    *,
    rng=None,
) -> PhaseRecord | None:
    """Spike phase statistics for one record from its vibration and phase
    currents. Returns None if the record is not spiky (< SPIKY_MIN spikes)."""
    idx = spike_indices(x)
    if len(idx) < SPIKY_MIN:
        return None
    m = current_magnitude(i1, i2)
    ref_db = ripple_line_db(m, sr)
    phase, depth = ripple_phase(m, sr)
    kept, lo, hi = trim_indices(idx, len(x), sr)
    rec = PhaseRecord(
        record=name,
        condition=condition,
        meas=meas,
        n_spikes=int(len(kept)),
        ref_db=ref_db,
        ref_valid=ref_db >= REF_MIN_DB,
        depth=depth,
    )
    if len(kept) == 0:
        return rec
    theta = phase[kept]
    rec.r, rec.mu, rec.p = circ_stats(theta)
    d = np.angle(np.exp(1j * (theta - rec.mu)))
    rec.frac45 = float(np.mean(np.abs(d) <= math.pi / 4))
    rec.theta = theta
    rng = rng if rng is not None else np.random.default_rng(PHASE_SEED)
    if len(kept) >= SPIKY_MIN:
        rec.null_r99 = float(
            np.percentile(null_random_r(phase, len(kept), lo, hi, rng), 99)
        )
    rec._phase, rec._idx, rec._lo, rec._hi = phase, kept, lo, hi
    return rec


def between_stats(recs: list[PhaseRecord]) -> tuple[float, float, float]:
    """Second-order Rayleigh on per-record mean phases: (R_between, grand mean, p)."""
    return circ_stats(np.array([r.mu for r in recs]))


def null_shift_p(
    recs: list[PhaseRecord], observed: float, rng, draws: int = PHASE_NULL_DRAWS
) -> tuple[float, float]:
    """Null B: independent circular shift of each record's spikes within its
    usable window; returns (empirical p, 99th percentile of null R_between)."""
    null = np.empty(draws)
    for d in range(draws):
        mus = []
        for r in recs:
            w = r._hi - r._lo
            s = int(rng.integers(w))
            k = r._lo + (r._idx - r._lo + s) % w
            mus.append(np.angle(np.exp(1j * r._phase[k]).mean()))
        null[d] = abs(np.exp(1j * np.array(mus)).mean())
    p = (1 + int(np.count_nonzero(null >= observed))) / (draws + 1)
    return float(p), float(np.percentile(null, 99))


def phase_verdicts(
    recs: list[PhaseRecord],
    *,
    seed: int = PHASE_SEED,
    null_a_max_r99: float = NULL_A_MAX_R99,
) -> dict:
    """Apply the prereg-2026-10-27-phase.md rules (P1, P2, P3, null A/B) to the
    confirmation records (non-spiky records must already be filtered out).

    ``null_a_max_r99`` is the pre-registered null-A pipeline bar (0.2); other
    values are for clearly labelled exploratory re-reads only."""
    spiky = [r for r in recs if r.n_spikes >= SPIKY_MIN]
    use = [r for r in spiky if r.ref_valid]
    v = len(use)
    out: dict = {"spiky": len(spiky), "valid_reference": v}
    if v == 0 or v < 0.5 * len(spiky):
        out |= {"P1": "UNTESTABLE", "P2": "UNTESTABLE", "P3": "UNTESTABLE"}
        return out
    null_a_ok = all(r.null_r99 <= null_a_max_r99 for r in use)
    burst = sum(r.r >= R_BURST and r.p < ALPHA for r in use)
    spread = sum(r.r <= R_SPREAD for r in use)
    rb, mbar, pb_ = between_stats(use)
    rng = np.random.default_rng(seed + 1)
    p_null, null99 = null_shift_p(use, rb, rng)
    out |= {
        "null_a_ok": null_a_ok,
        "null_a_r99_max": max(r.null_r99 for r in use),
        "burst_count": burst,
        "spread_count": spread,
        "r_min": min(r.r for r in use),
        "r_max": max(r.r for r in use),
        "r_between": rb,
        "grand_mean_deg": math.degrees(mbar),
        "p_between": pb_,
        "null_b_p": p_null,
        "null_b_r99": null99,
    }
    if not null_a_ok:
        out |= {"P1": "UNTESTABLE", "P2": "UNTESTABLE", "P3": "UNTESTABLE"}
        return out
    if burst >= P1_HELD_FRAC * v:
        out["P1"] = "HELD"
    elif spread >= P1_FAIL_FRAC * v:
        out["P1"] = "FALSIFIED"
    else:
        out["P1"] = "INCONCLUSIVE"
    if rb >= R_BETWEEN_HELD and pb_ < ALPHA and p_null <= NULL_B_MAX_P:
        out["P2"] = "HELD"
    elif rb < R_BETWEEN_FAIL or pb_ >= P_BETWEEN_FAIL:
        out["P2"] = "FALSIFIED"
    else:
        out["P2"] = "INCONCLUSIVE"
    if out["P2"] != "HELD":
        out["P3"] = "UNTESTABLE"
    elif abs(out["grand_mean_deg"]) <= P3_HELD_DEG:
        out["P3"] = "HELD"
    elif abs(out["grand_mean_deg"]) > P3_FAIL_DEG:
        out["P3"] = "FALSIFIED"
    else:
        out["P3"] = "INCONCLUSIVE"
    return out


def phase_record(
    bearing: str, condition: str, meas: int, cache=None, *, rng=None
) -> PhaseRecord | None:
    """Load one pinned record (no download) and compute its spike phase stats."""
    path = pb.fetch(bearing, condition, cache, download=False, meas=meas)
    ch = load_channels(path, ("vibration_1", *CURRENT_CHANNELS))
    return phase_from_signals(
        pb.member(bearing, condition, meas),
        condition,
        meas,
        ch["vibration_1"],
        ch[CURRENT_CHANNELS[0]],
        ch[CURRENT_CHANNELS[1]],
        pb.SR,
        rng=rng,
    )


# --- Confirmatory phase re-run on fresh records (prereg-2026-10-28-phase-confirm.md, NOTES #8k)

CONFIRM_SEED = 20261028
#: null-A gate: 99th pct of random-time R ≤ NULL_A_SCALE · sqrt(ln 100 / N)
NULL_A_SCALE = 1.2
#: exploratory grand mean phase from 2026-10-27 (deg), the C3 target
C3_TARGET_DEG = -65.7
C1_HELD_FRAC = 0.80
C3_HELD_DEG = 30.0
C3_FAIL_DEG = 60.0


def null_a_bar(n_spikes: int) -> float:
    """N-scaled null-A pipeline bar, NULL_A_SCALE · sqrt(ln 100 / N)."""
    if n_spikes <= 0:
        return math.inf
    return NULL_A_SCALE * math.sqrt(math.log(100.0) / n_spikes)


def circ_dist_deg(a_deg: float, b_deg: float) -> float:
    """Absolute circular distance between two angles in degrees (0…180)."""
    return abs(math.degrees(np.angle(np.exp(1j * math.radians(a_deg - b_deg)))))


def confirm_verdicts(recs: list[PhaseRecord], *, seed: int = CONFIRM_SEED) -> dict:
    """Apply the prereg-2026-10-28-phase-confirm.md rules (C1, C2, C3) to
    spike-phase records. Non-spiky records (None) must already be removed."""
    spiky = [r for r in recs if r.n_spikes >= SPIKY_MIN]
    use = [r for r in spiky if r.ref_valid]
    v = len(use)
    out: dict = {"spiky": len(spiky), "valid_reference": v}
    if v == 0 or v < 0.5 * len(spiky):
        return out | {"C1": "UNTESTABLE", "C2": "UNTESTABLE", "C3": "UNTESTABLE"}
    ratios = [r.null_r99 / math.sqrt(math.log(100.0) / r.n_spikes) for r in use]
    null_a_ok = all(r.null_r99 <= null_a_bar(r.n_spikes) for r in use)
    burst = sum(r.r >= R_BURST and r.p < ALPHA for r in use)
    spread = sum(r.r <= R_SPREAD for r in use)
    rb, mbar, p_b = between_stats(use)
    p_null, null99 = null_shift_p(use, rb, np.random.default_rng(seed + 1))
    gm = math.degrees(mbar)
    out |= {
        "null_a_ok": null_a_ok,
        "null_a_ratio_range": [min(ratios), max(ratios)],
        "burst_count": burst,
        "spread_count": spread,
        "r_min": min(r.r for r in use),
        "r_max": max(r.r for r in use),
        "r_between": rb,
        "grand_mean_deg": gm,
        "c3_distance_deg": circ_dist_deg(gm, C3_TARGET_DEG),
        "p_between": p_b,
        "null_b_p": p_null,
        "null_b_r99": null99,
    }
    if not null_a_ok:
        return out | {"C1": "UNTESTABLE", "C2": "UNTESTABLE", "C3": "UNTESTABLE"}
    if burst >= C1_HELD_FRAC * v:
        out["C1"] = "HELD"
    elif spread >= P1_FAIL_FRAC * v:
        out["C1"] = "FALSIFIED"
    else:
        out["C1"] = "INCONCLUSIVE"
    if rb >= R_BETWEEN_HELD and p_b < ALPHA and p_null <= NULL_B_MAX_P:
        out["C2"] = "HELD"
    elif rb < R_BETWEEN_FAIL or p_b >= P_BETWEEN_FAIL:
        out["C2"] = "FALSIFIED"
    else:
        out["C2"] = "INCONCLUSIVE"
    d = out["c3_distance_deg"]
    if out["C2"] != "HELD":
        out["C3"] = "UNTESTABLE"
    elif d <= C3_HELD_DEG:
        out["C3"] = "HELD"
    elif d > C3_FAIL_DEG:
        out["C3"] = "FALSIFIED"
    else:
        out["C3"] = "INCONCLUSIVE"
    return out


# --- condition-matched headroom bar (prereg-2026-10-29-headroom-bar.md, NOTES #8k c) ---

#: Spike-free control measurements used to derive the bar (already seen).
BAR_DERIVE_MEASUREMENTS = (1, 2, 3, 4, 5)

#: Per-condition bar B_c (dB) = min raw headroom of KA04 ``_1.._5``, floored to 0.01 dB,
#: fixed in the prereg before any ``_6.._10`` headroom was computed.
HEADROOM_BAR_DB = {
    "N15_M07_F10": 3.31,
    "N09_M07_F10": 3.94,
    "N15_M01_F10": 2.95,
    "N15_M07_F04": 1.60,
}

B1_HELD_FRAC = 0.70
B1_MIN_PER_CONDITION = 3
B1_FAIL_FRAC = 0.50


def derive_bar_db(values: list[float]) -> float:
    """Bar rule from the prereg: lowest spike-free headroom, floored to 0.01 dB."""
    if not values:
        raise ValueError("need at least one spike-free headroom value")
    return math.floor(min(values) * 100.0) / 100.0


def bar_stability_verdict(
    controls: list[tuple[str, float]], bars: dict[str, float]
) -> dict:
    """B1: fraction of fresh spike-free records (condition, raw headroom dB) at or above B_c."""
    n = len(controls)
    per: dict[str, list[int]] = {}
    for cond, h in controls:
        ok, tot = per.setdefault(cond, [0, 0])
        per[cond] = [ok + int(h >= bars[cond]), tot + 1]
    k = sum(v[0] for v in per.values())
    if n == 0:
        verdict = "UNTESTABLE"
    elif k <= B1_FAIL_FRAC * n:
        verdict = "FALSIFIED"
    elif k >= B1_HELD_FRAC * n and all(
        v[0] >= B1_MIN_PER_CONDITION for v in per.values()
    ):
        verdict = "HELD"
    else:
        verdict = "INCONCLUSIVE"
    return {"n": n, "at_or_above": k, "per_condition": per, "B1": verdict}


def bar_lp10_verdict(probes: list[RecordProbe], bars: dict[str, float]) -> dict:
    """B2: LP10 headroom ≥ B_c on spiky records, plus line / silent / rule checks (all probes)."""
    spiky = [p for p in probes if p.spiky]
    s = len(spiky)
    lp = [p.filters["LP10"] for p in spiky]
    good = sum(f["headroom_db"] >= bars[p.condition] for p, f in zip(spiky, lp))
    good_fixed = sum(f["headroom_db"] >= HEADROOM_TARGET_DB for f in lp)
    silent = sum(f["silent_fail"] for f in lp)
    rule_ok = all(f["rule_correct"] == f["cells"] for f in lp)
    lost, testable = [], 0
    for p in probes:
        raw = p.raw["line_snr_db"]
        if raw is None or raw < LINE_MIN_DB:
            continue
        testable += 1
        if p.filters["LP10"]["line_snr_db"] < raw - LINE_DROP_DB:
            lost.append(p.record)
    if s == 0:
        v = "UNTESTABLE"
    elif good <= LP_FAIL_FRAC * s or lost or silent:
        v = "FALSIFIED"
    elif good >= LP_HELD_FRAC * s and rule_ok:
        v = "HELD"
    else:
        v = "INCONCLUSIVE"
    return {
        "spiky_records": s,
        "lp10_at_or_above_bar": good,
        "lp10_at_or_above_3db_descriptive": good_fixed,
        "silent_fail": silent,
        "rule_all_correct": rule_ok,
        "lines_testable": testable,
        "lines_lost": lost,
        "B2": v,
    }


# --- K001 own spike-free level (prereg-2026-10-30-k001-spike-free.md) -------

#: Despike stops after this many passes even if spikes remain.
DESPIKE_MAX_PASSES = 50
#: D0 method control: injected spikes per record, amplitude (× peak), seed, spacing.
D0_N_INJECT = 300
D0_AMP_X_PEAK = 3.0
D0_SEED = 20261030
D0_MIN_GAP = 4
D0_TOL_DB = 0.25
D0_MAX_MODIFIED_FRAC = 0.01
D1_HELD_MIN = 4
D1_FAIL_MAX = 2
#: The five LP10 misses of Table 18 (all K001), fixed in the prereg.
D1_MISSES = (
    "K001/N09_M07_F10_K001_6.mat",
    "K001/N09_M07_F10_K001_7.mat",
    "K001/N09_M07_F10_K001_8.mat",
    "K001/N15_M07_F10_K001_10.mat",
    "K001/N15_M01_F10_K001_10.mat",
)


@dataclass
class Despiked:
    """Result of :func:`despike`: the signal, samples changed and passes used."""

    y: np.ndarray
    n_modified: int
    passes: int
    converged: bool


def despike(
    x: np.ndarray, frac: float = 0.5, max_passes: int = DESPIKE_MAX_PASSES
) -> Despiked:
    """Replace each isolated single-sample spike (``spike_indices``) with the mean
    of its two neighbours; repeat with the peak recomputed until none is found
    or ``max_passes`` passes have run. The input is not modified."""
    y = np.array(x, dtype=float, copy=True)
    touched = np.zeros(len(y), dtype=bool)
    for k in range(max_passes):
        idx = spike_indices(y, frac)
        if len(idx) == 0:
            return Despiked(y, int(touched.sum()), k, True)
        y[idx] = 0.5 * (y[idx - 1] + y[idx + 1])
        touched[idx] = True
    converged = len(spike_indices(y, frac)) == 0
    return Despiked(y, int(touched.sum()), max_passes, converged)


def despiked_headroom_db(x: np.ndarray) -> float:
    """DS: raw headroom 20·log10(peak / max|Δx|) after :func:`despike` (no filter)."""
    y = despike(x).y
    return headroom_db(float(np.max(np.abs(y))), max_sample_jump(y))


def inject_spikes(
    x: np.ndarray,
    n: int = D0_N_INJECT,
    *,
    amp_x_peak: float = D0_AMP_X_PEAK,
    min_gap: int = D0_MIN_GAP,
    seed: int = D0_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """D0 control: set ``n`` samples to ±``amp_x_peak``·peak (alternating sign),
    at least ``min_gap`` apart and ``min_gap`` from the ends. Returns (signal, positions)."""
    x = np.asarray(x, dtype=float)
    span = len(x) - 2 * min_gap
    if n < 0 or span < n * min_gap:
        raise ValueError("record too short for the requested spikes")
    rng = np.random.default_rng(seed)
    # Draw n gaps on a compressed line, then re-expand: guarantees spacing.
    base = np.sort(rng.choice(span - (n - 1) * (min_gap - 1), size=n, replace=False))
    pos = base + np.arange(n) * (min_gap - 1) + min_gap
    y = x.copy()
    sign = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    y[pos] = sign * amp_x_peak * float(np.max(np.abs(x)))
    return y, pos


def d0_row(x: np.ndarray, *, seed: int = D0_SEED) -> dict:
    """D0 numbers for one spike-free control record."""
    ref = despiked_headroom_db(x)
    inj, _ = inject_spikes(x, seed=seed)
    d = despike(inj)
    h = headroom_db(float(np.max(np.abs(d.y))), max_sample_jump(d.y))
    return {
        "ds_clean_db": ref,
        "ds_injected_db": h,
        "abs_err_db": abs(h - ref),
        "modified_frac": d.n_modified / len(x),
        "converged": d.converged,
    }


def d0_verdict(rows: list[dict]) -> str:
    """D0 gate: every control within tolerance, converged, ≤ 1 % of samples modified."""
    if not rows:
        return "UNTESTABLE"
    ok = all(
        r["converged"]
        and r["abs_err_db"] <= D0_TOL_DB
        and r["modified_frac"] <= D0_MAX_MODIFIED_FRAC
        for r in rows
    )
    return "PASS" if ok else "FAIL"


def d1_verdict(ds_by_record: dict[str, float], bar_by_record: dict[str, float]) -> dict:
    """D1: DS < B_c on the five pre-listed LP10 misses."""
    below = [r for r in D1_MISSES if ds_by_record[r] < bar_by_record[r]]
    k = len(below)
    if k >= D1_HELD_MIN:
        v = "HELD"
    elif k <= D1_FAIL_MAX:
        v = "FALSIFIED"
    else:
        v = "INCONCLUSIVE"
    return {"misses": len(D1_MISSES), "ds_below_bar": k, "below": below, "D1": v}


def d2_verdict(pairs: list[tuple[float, float]]) -> dict:
    """D2: (LP10 headroom, DS) pairs on spiky records; LP10 ≥ DS on ≥ 87.5 %."""
    n = len(pairs)
    k = sum(lp >= ds for lp, ds in pairs)
    return {
        "n": n,
        "lp10_at_or_above_ds": k,
        "D2": _frac_verdict(k, n, LP_HELD_FRAC, LP_FAIL_FRAC),
    }
