# What separates N15_M01 phase-scatter bearings from lock bearings? (pre-registered 2026-11-10)

Weekday slice 2026-11-10 (soft freeze, light), NOTES #8k optional step "what separates
scatter from lock bearings". **Explicitly exploratory.** Written and committed before any
covariate number below was computed on any record.

## Labels (fixed, already published)

N15_M01_F10 spike-phase vs 100 Hz |i_s| ripple R_between (Tables 19, 21, 22, 23):

| bearing | label | R_between | label records (N15_M01_F10) | source |
|---|---|---|---|---|
| K001 | SCATTER | 0.490 | measurements 11–20 | Table 19, `ref-snr-phase-metrics.json` |
| K002 | LOCK | 0.983 | measurements 6–20 | Table 21 (original reference), `fundamental-phase-metrics.json` |
| K003 | LOCK | 0.989 | measurements 1–10 | Table 22, `k003-phase-metrics.json` |
| K004 | SCATTER | 0.649 | measurements 1–10 | Table 23, `healthy-set-phase-metrics.json` |
| K005 | LOCK | 0.910 | measurements 1–10 | Table 23 |
| K006 | SCATTER | 0.163 | measurements 1–10 | Table 23 |

Covariates are computed on exactly these label records (65 records, all already SHA-256
pinned in `foldcrypt/paderborn.py`; no new data). Per-record value → bearing value = median
over that bearing's label records.

## What has already been seen (honest disclosure)

- Reference SNR (`ref_db`) was already judged not the cause (Table 19; Table 23 K004/K006
  scatter with strong references).
- Per-record spike counts N and ripple modulation depth are printed in the published logs; I
  read the K004–K006 values in `healthy-set-phase-2026-11-08.log` while preparing this slice.
  They are therefore **not** blind and are **not** in the pre-registered covariate set. They are
  reported in an "already-published quantities" section, labelled non-blind.
- Run-in metadata: the only bearing metadata in the official documentation is Lessmeier et
  al., "Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor
  Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification",
  PHME 2016, Table 7 p. 8 "Operating parameter of healthy (undamaged) bearings during run-in
  period" (PDF linked from the official KAt download page
  <https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download>,
  file `20160703_PHME16_CM_bearing.pdf`, SHA-256
  `c1f75c79cfbcbcbfd24b32bf034cebb76d1c3ff7864827575d37387bb0955f84`, fetched 2026-11-10;
  the page text calls it "Table 6", the PDF numbers it Table 7). Values: run-in hours K001
  >50, K002 19, K003 1, K004 5, K005 10, K006 16; radial load 1000–3000 / 3000 × 5 N; run-in
  speed 1500–2000 / 2900 / 3000 / 3000 / 3000 / 2900 min⁻¹. I read this table while finding
  the citation, so run-in hours is **not blind** (by inspection it overlaps). It is reported as
  context R0, not counted among the pre-registered covariates and not counted in Bonferroni.

## Pre-registered covariates (k = 4, none computed before this commit)

All on the label records, each channel edge-trimmed by `EDGE_TRIM_S` = 0.1 s at its own rate
(64 kHz: 6400 samples; 4 kHz mech channels: 400 samples; temperature not trimmed, 5 samples).

- **C1 speed stability** — coefficient of variation std/mean of the `speed` channel (4 kHz).
  Why: the spikes are supply-synchronous bursts timed against the 100 Hz current ripple; at
  0.1 Nm the speed loop has little load to damp it, and a hunting speed loop moves the
  inverter's modulation relative to the supply, which could wander the burst phase between
  records.
- **C2 measured load torque** — mean of the `torque` channel (Nm, 4 kHz). Why: the nominal
  0.1 Nm is small enough that bearing drag (which differs with run-in) can be a large share of
  the actual load; a lower real load means a lower fundamental current and a different
  inverter operating point.
- **C3 spike amplitude** — median |x[k]| over the edge-trimmed spike indices k
  (`ps.spike_indices`, same detector as the phase pipeline) of `vibration_1`, raw channel units.
  Why: tests whether scatter bearings have a different (weaker / stronger) electrical burst
  coupling, which could change which part of the burst the detector picks.
- **C4 bearing-module temperature** — mean of `temp_2_bearing_module` (1 Hz, 5 samples, °C).
  Why: oil temperature changes friction and therefore real load at low torque; the
  documentation says 45–50 °C was the target, so a real spread here would be a rig fact.

## Test and verdict rules (fixed)

For each covariate c with bearing values v_b:

- **SEPARATES** if max over one label group < min over the other (perfect rank separation of
  3 vs 3, no tie across groups). Direction reported, not predicted.
- **OVERLAPS** otherwise.
- **UNTESTABLE** if any bearing has no finite value (e.g. a missing channel) — then the
  covariate is reported per record only.
- Descriptive extra (not a verdict): whether the record-level ranges (min–max over label
  records) also do not overlap ("ranges disjoint").
- Exact two-sided permutation p over all C(6,3) = 20 labellings, statistic |mean rank(SCATTER)
  − mean rank(LOCK)|, p = #{labellings with statistic ≥ observed}/20. No direction is
  pre-stated (no prior basis), so the smallest possible p is **2/20 = 0.10** (one-sided would be
  1/20 = 0.05). With Bonferroni over k = 4 the bar would be 0.0125. **Nothing can be confirmed
  by this test.** Under the null, any single covariate with distinct values SEPARATES with
  probability 2/20 = 10 %, so with 4 covariates at least one chance SEPARATES has probability
  about 1 − 0.9⁴ ≈ 34 % (if independent). A SEPARATES verdict here is a lead only.

## Controls (fixed)

- **Positive control P+**: the label quantity itself, R_between per bearing (values above, from
  the committed metrics files). Must read SEPARATES with p = 0.10. If not, the pipeline is
  broken and every covariate verdict is void.
- **Negative control P−**: the same R_between values under a shuffled labelling, drawn with
  `numpy.random.default_rng(20261110)` uniformly from the 18 labellings that are neither the
  true labelling nor its complement. Must read OVERLAPS (for distinct values only the true split
  and its complement can separate, so this is guaranteed if the code is right). If it reads
  SEPARATES, every verdict is void.
- Unit tests on synthetic data show the covariate functions recover known values (known speed
  CV, known torque mean, known spike amplitude, known temperature) and that the verdict function
  returns both SEPARATES and OVERLAPS.

## What would confirm a lead

A SEPARATES covariate is only a lead. To confirm it: (1) held-out records — recompute on the
unused N15_M01 measurements (K001 1–10, K002 1–5, K003–K006 11–20) and require the same
direction of separation with the median of the new records; this still has only 6 bearings,
so it tests record stability, not the bearing-level claim; (2) new bearings — any further
healthy bearing on this or another rig, with the scatter/lock label predicted from the
covariate *before* its phase is computed. Neither is run in this slice.

## Named limits

- n = 6 bearings, 3 vs 3; one rig, one drive, one supply.
- Labels are themselves thresholded statistics (R_between < 0.8); K005 (0.910) is the closest
  lock.
- Different measurement-number ranges per bearing (as published); measurement order effects
  not controlled.
- Correlation only; a separating covariate is not a mechanism.

## Reporting

`ps.scatter_covariates_record`, `ps.covariate_verdict`, `ps.SCATTER_COV_*`;
`scripts/scatter_covariates.py`; `tests/test_scatter_covariates.py`; log
`artifacts/paderborn/scatter-covariates-2026-11-10.log`; metrics
`artifacts/paderborn/scatter-covariates-metrics.json`. Anything beyond this file is
exploratory and labelled so.
