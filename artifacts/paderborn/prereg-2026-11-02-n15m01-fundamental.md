# K001 low-torque phase scatter: motor fundamental inside the reference band (pre-registered 2026-11-02, NOTES #8k)

Written and committed before any spike, phase, reference or null number was computed on the records below.
The 30 new records (`K002`, conditions N15_M01_F10 and N09_M07_F10, measurements `_6`…`_20`) were extracted
from the MD5-verified cached `K002.rar` (Zenodo 15845309, MD5 `88631bc0081a6470846d18189d46381d`) and
SHA-256-pinned in `foldcrypt/paderborn.py` (`FUND_MEASUREMENTS`, `FUND_CONDITIONS`) in the same commit as this
file. K002 `_1`…`_5` were probed on 2026-10-31d (spike counts, 16 kHz / 100 Hz vector strength, headroom) but
never phase-referenced; `_6`…`_20` have not been looked at at all. CPU only, box. No further download.
(Extraction used the 7-Zip 24.09 `7zz` binary because `unar` is not installable on the box today; the
SHA-256 pins are the integrity check, independent of the extractor.)

## Why (exploratory, on already-used K001 `_11`…`_20`)

Table 19 (v1.19): K001 N15_M01_F10 scatters (R_between 0.490, record mean phases −153° to +26°) with 9/10
references ≥ 27 dB, while N09_M07_F10 agrees at 0.999. The Paderborn motor has 4 pole pairs
(`ps.POLE_PAIRS`), so at 1500 rpm its electrical fundamental is ~100 Hz and lies inside the 95–105 Hz
reference band; at 900 rpm it is ~60 Hz, outside. An exploratory look on K001 `_11`…`_20` (script not
committed; numbers reproduced in the log of this run for transparency only, not as evidence):
- the current-vector electrical frequency is 99.96–99.97 Hz at N15 and 59.98–59.99 Hz at N09;
- the share of the 95–105 Hz band of |i_s| that is coherent with the electrical angle was 0.57–0.94 at
  N15_M01 and 0.00 at N09;
- after removing that coherent part, N15_M01 R_between rose 0.490 → 0.987 (mean phases −64° to −37°), N09
  stayed 0.999.

**Hypothesis H_fund.** At 1500 rpm the 100 Hz |i_s| reference is dominated by a component locked to the
motor's electrical angle (not to the supply). Its phase relative to the supply-locked spikes changes from
record to record, so record mean phases scatter. Removing the electrical-angle-coherent component leaves a
supply-side residual against which the spikes share one phase, the same phase as at 900 rpm.

## Method (fixed)

Unchanged from prereg-2026-10-31d-k001-ref-snr.md: `spike_indices`, `current_magnitude`, edge trim
`EDGE_TRIM_S`, 95–105 Hz 4th-order zero-phase Butterworth band-pass, Hilbert phase, `ripple_line_db` validity
≥ 10 dB, spiky ≥ 10 spikes, `circ_stats`, second-order Rayleigh, N-scaled null A (`null_a_bar`), null B
(2,000 independent circular shifts, `null_shift_p`). Seed **20261102**.

New (`ps.electrical_angle`, `ps.fundamental_split`):
- electrical angle θ_el(t) = unwrapped atan2(β, α) of the mean-removed current space vector (same α/β as
  `current_magnitude`); f_el = total unwrapped angle / (2π · duration).
- band signal r(t) = the existing 95–105 Hz band-pass of |i_s| − mean. Least-squares fit
  r ≈ a·cos θ_el + b·sin θ_el over the whole record; fit = coherent part, residual = r − fit.
- fundamental share F = var(fit) / var(r).
- residual reference phase = Hilbert phase of the residual. Spike statistics as before against it.

## Predictions (K002, fresh)

Usable = spiky and original reference valid (as before). N_M01 = usable N15_M01 records, N_N09 = usable N09.
If N_M01 < 8 or N_N09 < 8, everything below is UNTESTABLE.

**F0 — pipeline control.** Null A (N-scaled bar) passes on every usable record, for **both** the original
and the residual reference. Control share: median F at N09 ≤ 0.05 (the fundamental is out of band, so the
fit must find ~nothing). If F0 fails, F1–F4 are UNTESTABLE.

**Q — scatter replicates on K002 (descriptive precondition).** Original-reference R_between at N15_M01 < 0.8.
Reported as "replicated" / "not replicated"; if not replicated, F3 is UNTESTABLE (nothing to repair).

**F1 — coherent component dominates the low-torque band.** HELD if median F at N15_M01 ≥ 0.5; FALSIFIED if
< 0.25; else INCONCLUSIVE.

**F2 — residual reference gives one phase at N15_M01.** Residual R_between at N15_M01: HELD if ≥ 0.8 **and**
second-order Rayleigh p < 1e-3 **and** null-B p ≤ 0.01; FALSIFIED if < 0.5 or Rayleigh p ≥ 0.05; else
INCONCLUSIVE.

**F3 — residual is tighter than the original at N15_M01** (only if Q replicated). HELD if residual
R_between ≥ original + 0.2; FALSIFIED if residual ≤ original; else INCONCLUSIVE.

**F4 — same phase as 900 rpm.** Circular distance between the N15_M01 residual grand mean and the N09
original grand mean: HELD if ≤ 30°; FALSIFIED if > 60°; else INCONCLUSIVE. (UNTESTABLE unless F2 HELD and
N09 original R_between ≥ 0.8.)

**F5 — control: removal is harmless at 900 rpm.** N09 residual R_between ≥ 0.8 and residual grand mean within
10° of the N09 original grand mean → PASS; else FAIL. (A FAIL means the decomposition changes a reference
it should leave alone; then F2–F4 are reported but marked "control failed".)

**Reading.** H_fund supported if F0 passes, F1 and F2 HELD, F5 PASS, and F3 HELD or UNTESTABLE. H_fund
rejected if F1 or F2 FALSIFIED. Anything else: not settled.

## Named limits

- Residual within-record R is expected to be lower than the original (the residual is a small signal);
  per-record significance is not a pass criterion, only null A.
- At 1500 rpm f_el (≈ 99.97 Hz) and twice the mains frequency are within ~0.1 Hz; over a 4 s record the
  fit can absorb part of a true supply component. F2/F4 test whether what is left still carries one phase.
- The cause of the coherent component (current-sensor offset, rotor eccentricity, back-EMF harmonics) is not
  identified by this test, and no claim is made about why low torque makes it worse.
- Second healthy bearing, same bench and drive. Not a second rig.

## Reporting

Script `scripts/fundamental_phase.py`; log `artifacts/paderborn/fundamental-phase-2026-11-02.log`;
metrics `artifacts/paderborn/fundamental-phase-metrics.json`. Anything beyond this file is exploratory.
