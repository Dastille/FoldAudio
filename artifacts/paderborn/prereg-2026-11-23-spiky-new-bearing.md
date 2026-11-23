# Second new-bearing test of the ripple-depth lead, with a spike-count eligibility screen (pre-registered 2026-11-23)

Weekday slice 2026-11-23, NOTES #8k, whitepaper v1.25 Table 26 / Limitation 12. The 2026-11-16
test (`prereg-2026-11-16-new-bearing.md`) was UNTESTABLE: all three bearings were predicted LOCK,
and two of them (KA01, KI01) had no N15_M01 record with ≥ 10 spikes, so only KA05 could be
labelled. The whitepaper states the next test needs bearings that are spiky at N15_M01. This
run adds a **pre-declared spike-count eligibility screen** that picks the bearings before any
ripple-depth, reference or phase number is computed on them. **Exploratory** (at most four
bearings, damaged, one rig).

This file is committed before any record of a candidate bearing is downloaded or read. Order of
commits (provable from git history):

1. this file + archive MD5 pins + code + synthetic tests (no candidate-bearing number);
2. screen (`python scripts/new_bearing.py screen --run 2026-11-23`): spike counts only, plus the
   SHA-256 pins of every extracted record, committed as
   `artifacts/paderborn/spiky-screen-metrics.json` and log; the pins are added to
   `foldcrypt/paderborn.py` (`MAT_SHA256`) in the same commit;
3. stage 1 (`python scripts/new_bearing.py depth --run 2026-11-23`): refuses to run unless the
   screen metrics file is committed and unchanged; ripple depth per record, bearing median,
   predicted label for the selected bearings; committed as
   `artifacts/paderborn/new-bearing-2-depth-metrics.json` and log;
4. stage 2 (`python scripts/new_bearing.py phase --run 2026-11-23`): refuses to run unless the
   stage-1 metrics file is committed and unchanged; spikes, phases, labels, controls, verdict.

## Candidate pool and order (fixed)

Zenodo record 15845309 (CC BY 4.0) bearings never analysed in this repository (checked with
`rg -o 'K[ABI][0-9]{2}'` before this file was written: the codes below appear only in the
bearing list of the 2026-11-16 prereg). Excluded: K001–K006 (set the threshold), KA01, KA05,
KI01 (2026-11-16 test), KA04, KI04 (earlier runs). KA08 is not on the mirror.

Screen order (artificial damage first, then real accelerated-life damage, each in code order):

1. KA03, KA06, KA07, KA09, KI03, KI05, KI07, KI08
2. KA15, KA16, KA22, KA30, KB23, KB24, KB27, KI14, KI16, KI17, KI18, KI21

Archive MD5 pins are the values listed by the Zenodo API on 2026-11-23 and are added to
`foldcrypt/paderborn.py` (`EXTRA_BEARINGS`) in commit 1; every download is MD5-checked.

| Bearing | MD5 (Zenodo API) | Bearing | MD5 (Zenodo API) |
|---|---|---|---|
| KA03 | 0bba6927ac1732d23934a909af4c1fc6 | KA22 | 7a16a5bc88d5fe1d83d169f88f0709e8 |
| KA06 | be58a820fee4851b2c16a97a88c282cb | KA30 | 715c0cf7862a7ba83e7c6a6fb5c91a61 |
| KA07 | 185e3de688149ebabf20c51d80fd7dd8 | KB23 | bb87c72669baa9dbbefd10b5294ffcc8 |
| KA09 | de9392fdbf878171a429c2451d2696fd | KB24 | c60ce8867c824583540794ae00cce333 |
| KI03 | 26f0452f00ab698a4e657e27b7a249b3 | KB27 | 965dd4af26391d7def4638c8b31a87e7 |
| KI05 | c777459ddc7a1d38df7155f09e0ce782 | KI14 | 13603834975435ca10eb08de6d1840dc |
| KI07 | c26144f53ebcc34562bdc2e3a0ef1087 | KI16 | db14eae04a213afd0d1ca99d3d850342 |
| KI08 | f546b3481ffdcd80f0d14a797db48deb | KI17 | d1055fe5cc44948e5d3a39f2e0db9dbe |
| KA15 | db518f97ba5bcaedb09c648a317431e0 | KI18 | db5da511e9240dbc56ec1e850fd91699 |
| KA16 | ef848f5621f9c10523c313131d1a4c21 | KI21 | 911ce3e37a86d258818e3e93274752a2 |

Records per screened bearing (fixed): {N15_M01_F10, N09_M07_F10} × measurements 1–10, extracted
with 7-Zip 24.09 (`7zz`). Their SHA-256 values are recorded at extraction by the screen and pinned
in commit 2; stages 1 and 2 read only pinned files. Control records K001 measurements 11–20 at
both conditions are already pinned.

## Eligibility screen (spike count only)

Per record: load **only `vibration_1`** (no phase current, no reference, no phase); count
single-sample spikes with `ps.spike_indices` (the detector behind every earlier spike gate) and
keep those outside the 0.1 s edge trim (`ps.trim_indices`), i.e. exactly the `n_spikes` that the
stage-2 usable gate later tests. A record is **spiky** if that count is ≥ 10 (`SPIKY_MIN`).

A bearing is **eligible** iff ≥ 8 of its 10 N15_M01 records **and** ≥ 8 of its 10 N09 records
are spiky (8 = the minimum usable count per condition in the stage-2 rules). Bearings are
screened in the order above; the screen **stops as soon as 4 bearings are eligible** (or the pool
is exhausted). The selected set is the eligible bearings, in screen order. The screen does not
compute or print any reference level, ripple depth, phase or R_between. Reference validity
(100 Hz line ≥ 10 dB) is not screened, so a selected bearing can still fail the stage-2 gate.

If fewer than 2 bearings are eligible after the whole pool, the run stops: verdict N =
UNTESTABLE, no stage 1 or 2.

Selection depends on spike count only, so it cannot use the predictor (depth) or the outcome
(phase). It can still correlate with them through the damage or the run; this is a named limit.

## Stage 1: ripple depth and prediction (unchanged from 2026-11-16)

Per record: `ps.ripple_depth_record` on the N15_M01_F10 measurements 1–10 of each selected
bearing (two phase-current channels only). Bearing value = median of its 10 records. Predicted
label (`ps.predict_label`): **SCATTER iff median > T = 0.0097**, else LOCK (T fixed in v1.24, not
changed). Within ±10 % of T is flagged "near T" (descriptive; the prediction stands).

## Stage 2: phase label (existing gate and rules, unchanged)

Exactly the 2026-11-16 pipeline (`ps.phase_record` + `ps.k003_phase_verdicts`): usable = ≥ 10
spikes after edge trim and reference valid (100 Hz line ≥ 10 dB). Per bearing: Q3 = LOCKS if
N15_M01 R_between ≥ 0.8 and p < 1e-3; SCATTERS if R_between < 0.8; else INCONCLUSIVE; UNTESTABLE
if fewer than 8 usable records at either condition. C3n = PASS iff N09 R_between ≥ 0.8 and
p < 1e-3. One RNG, seed **20261123**, consumed in the order K001 control (N15_M01 then N09,
measurements 11–20), then each selected bearing in screen order × (N15_M01, N09) × 1–10.
R_between does not depend on the RNG. A bearing is **valid** only with C3n PASS and a phase label
(SCATTER or LOCK).

## Verdict N (pass/fail rule, as 2026-11-16)

- **UNTESTABLE** if fewer than 2 bearings are valid (including the screen-stop case above).
- **FALSIFIED** if any valid bearing's phase label differs from its stage-1 prediction.
- **HELD** if every valid bearing's phase label equals its prediction. (HELD is the
  "confirmed" outcome of this test; it does not make the lead a confirmed result.)

Reported with the verdict: number of valid bearings, matches, whether both labels were predicted
among the valid bearings, and the chance of all-match under a coin-flip predictor (0.5^valid).
If all predictions are the same label, a HELD only shows the threshold does not mislabel that
class. This screen cannot steer the set toward a predicted-SCATTER bearing; if none is predicted
SCATTER, the report says so.

## Controls (fixed; any failure voids N)

- **P+a (depth reproducibility)**: K001 N15_M01 measurements 11–20 bearing median recomputed in
  stage 1 must equal 0.012714899518091804 (Table 24; rel. tol. 1e-9).
- **P+b (phase pipeline gives both labels)**: K001 measurements 11–20 recomputed in stage 2:
  N15_M01 R_between 0.49027188906199126 and N09 R_between 0.9992186644878709 (Table 19; rel. tol.
  1e-9), K001 Q3 SCATTERS with C3n PASS.
- **P− (negative)**: for each valid bearing, the 99th percentile of N15_M01 R_between under null B
  (each usable record's spikes circularly shifted at random in its window, 2000 draws, seed
  20261123 + 2) must be below 0.8.
- **S0 (screen consistency)**: for every selected bearing, the stage-2 trimmed spike count of
  each record must equal its screen count (same detector, same file). A mismatch voids N.
- Synthetic unit tests (`tests/test_new_bearing.py`) for the screen rule and stop rule.

## What a result means

- HELD: the threshold, set on six healthy bearings, predicted the low-torque phase label of new,
  spiky, damaged bearings before their phase was seen. A lead that survived a second prediction
  test, not a mechanism.
- FALSIFIED: the depth–label relation does not carry to these bearings on this rig (or damage
  breaks it).
- UNTESTABLE: no conclusion.

## Named limits

n ≤ 4 bearings; one rig, drive and supply; damaged, not healthy; damage type differs across the
set; labels are thresholded statistics; T was set from bearing medians of 10–15 records each;
selection by spikiness may correlate with the outcome through the damage.

## Reporting

`scripts/new_bearing.py` (`--run 2026-11-23`); `tests/test_new_bearing.py`; logs
`artifacts/paderborn/spiky-screen-2026-11-23.log`, `artifacts/paderborn/new-bearing-2-depth-2026-11-23.log`,
`artifacts/paderborn/new-bearing-2-phase-2026-11-23.log`; metrics
`artifacts/paderborn/spiky-screen-metrics.json`, `artifacts/paderborn/new-bearing-2-depth-metrics.json`,
`artifacts/paderborn/new-bearing-2-phase-metrics.json`. Anything beyond this file is labelled
exploratory.
