# New-bearing test of the ripple-depth lead: predict the phase label from 100 Hz ripple depth before computing phase (pre-registered 2026-11-16)

Weekday slice 2026-11-16, NOTES #8k, whitepaper v1.24 Table 25 / Limitation 12 ("for a
bearing-level claim, predict the label of a new bearing from its ripple depth before computing
its phase"). **Exploratory** (three bearings). This file and the 60 new SHA-256 pins are
committed before any ripple-depth, spike, reference or phase number is computed on the new
bearings. Order of commits (provable from git history):

1. this file + pins + code + synthetic tests (no new-bearing number);
2. stage 1 (`python scripts/new_bearing.py depth`): ripple depth per record, bearing median,
   predicted label, committed as `artifacts/paderborn/new-bearing-depth-metrics.json` and log;
   stage 1 loads only the two phase-current channels (no vibration, no spikes, no phase);
3. stage 2 (`python scripts/new_bearing.py phase`): refuses to run unless the stage-1 metrics
   file is committed and unchanged; computes spikes, phases, labels, verdict.

## Bearing choice (fixed)

The dataset's healthy set (K001–K006) is exhausted: all six set the threshold. Every other
bearing is damaged, so a new bearing is necessarily a damaged one. Zenodo record 15845309
lists 31 archives: K001–K006, artificial damage KA01, KA03, KA05, KA06, KA07, KA09, KI01, KI03,
KI05, KI07, KI08 (KA08 is not on the mirror), and real (accelerated-life) damage KA04, KA15,
KA16, KA22, KA30, KB23, KB24, KB27, KI04, KI14, KI16, KI17, KI18, KI21.

Already analysed in this repository (not blind, excluded): K001–K006, KA04, KI04 (KI04 phase
and depth at N15_M01 printed in `spike-phase-*.log`; KA04 is spike-free in every earlier run,
whitepaper Section 6.6 v1.9/v1.13). No other bearing code appears anywhere in the repository (checked with
`rg 'K[AI][0-9]{2}'` before this file was written: only KA04 and KI04).

Chosen: **KA01** (outer ring, EDM trench, level 1), **KA05** (outer ring, electric engraver,
level 1), **KI01** (inner ring, EDM trench, level 1) — Lessmeier et al., PHME 2016, Table 3.
Reasons: artificial single-point damage of the smallest extent class (level 1, ≤ 2 mm on the
6203), so the closest available to the healthy set; EDM on both rings gives an outer/inner pair
with the same method, and KA05 adds a second method on the outer ring. Real-damage bearings were
not chosen because their damage is larger, repeated or combined, and two of them (KA04, KI04)
are already used. Three bearings keep the download to about 0.5 GB (archives 163–175 MB each;
MD5 from the Zenodo API, checked).

**Damage is a confound.** A damaged bearing can change drag, vibration and spike behaviour. A
mismatch could mean the lead fails, or that damage changes the relation; a match on damaged
bearings is weaker evidence for healthy bearings than a new healthy bearing would be (none
exists in this dataset). Also: the artificial-damage bearings have no documented run-in
comparable to Table 24 R0.

## Records (fixed)

KA01, KA05, KI01 × {N15_M01_F10, N09_M07_F10} × measurements 1–10 (60 records), extracted with
7-Zip 24.09 (`7zz`) from the MD5-verified archives and pinned in `foldcrypt/paderborn.py`
(`EXTRA_BEARINGS`, `NEW_BEARINGS`, `NEW_BEARING_MEASUREMENTS`, `NEW_BEARING_CONDITIONS`,
`MAT_SHA256`). Same record numbers and conditions as the K003–K006 label runs (Tables 22–23).
Control records K001 measurements 11–20 at both conditions are already pinned.

## Stage 1: ripple depth and prediction

Per record: `ps.ripple_depth_record` (median Hilbert envelope of the 95–105 Hz zero-phase
4th-order Butterworth band of |i_s| over mean |i_s|; the function behind Tables 24–25) on the
N15_M01_F10 measurements 1–10. Bearing value = median of its 10 records. Predicted label
(`ps.predict_label`): **SCATTER iff median > T = 0.0097**, else LOCK (T fixed in v1.24 and not
changed). A median within ±10 % of T is flagged "near T" (descriptive; the prediction stands).

## Stage 2: phase label (existing gate and rules, unchanged)

Exactly the K003 / healthy-set pipeline (`ps.phase_record` + `ps.k003_phase_verdicts`,
Tables 22–23): spike gate = record is spiky (≥ 10 single-sample spikes, `SPIKY_MIN`), reference
valid (100 Hz line ≥ 10 dB), edge trim 0.1 s; usable = spiky and valid reference. Per bearing:
Q3 = LOCKS if N15_M01 R_between ≥ 0.8 and p < 1e-3; SCATTERS if R_between < 0.8; else
INCONCLUSIVE; UNTESTABLE if fewer than 8 usable records at either condition. C3n (control) =
PASS iff N09 R_between ≥ 0.8 and p < 1e-3. One RNG, seed **20261116**, consumed in the order
K001 control (N15_M01 then N09, measurements 11–20), then KA01, KA05, KI01 × (N15_M01, N09) ×
1–10. R_between does not depend on the RNG.

Phase label: SCATTER (Q3 SCATTERS) or LOCK (Q3 LOCKS); a bearing is **valid** only with
C3n PASS and a phase label.

## Verdict N (pass/fail rule)

- **UNTESTABLE** if fewer than 2 bearings are valid (e.g. the spike gate fails; KA04, a damaged
  bearing, was spike-free, so this is a real risk).
- **FALSIFIED** if any valid bearing's phase label differs from its stage-1 prediction.
- **HELD** if every valid bearing's phase label equals its prediction.

Reported with the verdict: number of valid bearings, matches, whether both labels were
predicted among the valid bearings, and the chance of all-match under a coin-flip predictor
(0.5^valid: 0.125 for 3, 0.25 for 2). If all predictions are the same label, a HELD only shows
the threshold does not mislabel that class.

## Controls (fixed; any failure voids N)

- **P+a (depth reproducibility)**: K001 N15_M01 measurements 11–20 bearing median recomputed in
  stage 1 must equal the published Table 24 value 0.012714899518091804 (rel. tol. 1e-9).
- **P+b (phase pipeline gives both labels)**: K001 measurements 11–20 recomputed in stage 2:
  N15_M01 R_between must equal the published 0.49027188906199126 and N09 R_between
  0.9992186644878709 (Table 19, `ref-snr-phase-metrics.json`; rel. tol. 1e-9), and K001 must
  read Q3 SCATTERS with C3n PASS.
- **P− (negative)**: for each valid new bearing, the 99th percentile of N15_M01 R_between under
  null B (each usable record's spikes circularly shifted at random in its window, 2000 draws,
  RNG seed 20261116 + 2) must be below 0.8, i.e. random spike timing does not produce a lock.
- Synthetic unit tests (`tests/test_new_bearing.py`) for the prediction, label and verdict rules
  and for null B on locked synthetic spikes.

## What a result means

- HELD: the ripple-depth threshold, set on six healthy bearings, predicted the low-torque phase
  label of new (damaged) bearings before their phase was seen. Still a handful of bearings on one
  rig, damage confounded: a lead that survived a prediction test, not a mechanism.
- FALSIFIED: the depth–label relation does not carry to new bearings on this rig (or damage
  breaks it); drop the claim that ripple depth predicts the label.
- UNTESTABLE: the new bearings cannot be labelled with this gate; no conclusion.

## Named limits

n = 3 bearings; one rig, drive and supply; damaged, not healthy; labels are thresholded
statistics; T was set from bearing medians of 10–15 records each.

## Reporting

`scripts/new_bearing.py`; `tests/test_new_bearing.py`; logs
`artifacts/paderborn/new-bearing-depth-2026-11-16.log`, `artifacts/paderborn/new-bearing-phase-2026-11-16.log`;
metrics `artifacts/paderborn/new-bearing-depth-metrics.json`,
`artifacts/paderborn/new-bearing-phase-metrics.json`. Anything beyond this file is labelled
exploratory.
