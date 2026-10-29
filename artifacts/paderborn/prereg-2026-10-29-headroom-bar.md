# Paderborn headroom bar from the spike-free control — pre-registered 2026-10-29 (NOTES #8k item c)

Written and committed before any headroom, filter, line or cell number was computed on measurements `_6`…`_10`.
The 20 new `KA04` records (`_6`…`_10`, all four operating conditions) were extracted from the cached,
MD5-verified `KA04.rar` and SHA-256-pinned in `foldcrypt/paderborn.py` in the same commit as this file.
The 40 `K001`/`KI04` records `_6`…`_10` were pinned on 2026-10-28 and used only for spike phase
(no headroom, filter, envelope-line or fold-cell number was computed on them). CPU only, box. No download.

## Why

The LP10 rule ("a causal 4th-order Butterworth 10 kHz low-pass ahead of the fold restores ≥ 3 dB headroom and
keeps the fault line") used a fixed 3.0 dB bar taken from one spike-free `KA04` record (`_1`). On 2026-10-26 the
held-out spike-free `KA04` records themselves had raw headroom 1.60–5.04 dB, 5/16 below 3 dB, so the fixed
bar is unstable and R4 came out INCONCLUSIVE (27/32).

## Derivation (done on already-seen data before writing this file)

Raw headroom = 20 log10(peak / max|Δx|) of `vibration_1` (unchanged `headroom_db`, `max_sample_jump`).
On `KA04` `_1`…`_5` (20 records, 0–2 isolated spikes each) the values group by operating condition:

| condition | KA04 _1.._5 raw headroom (dB) | bar B_c = min, floored to 0.01 dB |
|---|---|---|
| N15_M07_F10 | 3.32, 3.99, 3.93, 4.05, 3.58 | **3.31** |
| N09_M07_F10 | 4.17, 4.49, 3.94, 4.98, 5.04 | **3.94** |
| N15_M01_F10 | 3.82, 3.74, 4.63, 2.95, 3.76 | **2.95** |
| N15_M07_F04 | 3.22, 1.64, 2.31, 2.49, 1.60 | **1.60** |

Pooled: median 3.79, 10th pct 2.24, min 1.60. The low radial force condition (F04, 400 N) sits ~2 dB lower;
a single pooled bar mixes conditions. New bar: **B_c = lowest spike-free control headroom in the same operating
condition** ("a filtered spiky record is as good as the worst normal record on that setting").
Named assumption: the spike-free level of `KA04` (outer-ring damage) transfers to `K001` (healthy) and `KI04`
(inner-ring damage) on the same rig and sensor; this is not tested here.

## Predictions

**B1 — the bar is stable on fresh spike-free records.** Set: `KA04` `_6`…`_10` with < 10 isolated spikes
(spiky ones excluded and reported). By exchangeability, a new record exceeds the minimum of 5 with
probability 5/6 ≈ 83 %. HELD if raw headroom ≥ B_c on ≥ 70 % of the set and on ≥ 3 of 5 in every condition.
FALSIFIED if ≤ 50 %. Else INCONCLUSIVE.

**B2 — LP10 with the condition bar.** Set S: spiky (≥ 10 isolated spikes) `K001`/`KI04` `_6`…`_10`.
HELD if LP10 headroom ≥ B_c on ≥ 87.5 % of S, no testable fault line lost (BPFI on `KI04`, BPFO on `KA04`,
testable if raw envelope line SNR ≥ 6 dB, lost if filtered < raw − 3 dB; all 60 records), 0 silent fold failures
and the slew rule agrees in every fold cell. FALSIFIED if ≤ 50 % of S, any testable line lost, or any silent
failure. Else INCONCLUSIVE.

**B3 — descriptive only (no verdict).** The same counts against the old fixed 3.0 dB bar; LP5 and MED3
numbers; retro-scoring of the already-seen `_1`…`_5` LP10 headrooms against B_c (labelled exploratory).

Everything else (spike detector, filters, envelope line, fold cells) is the unchanged code from 2026-10-25/26
(`paderborn_spikes.probe_record`). Exit status 0 whenever the run completes; verdicts are results, not errors.
