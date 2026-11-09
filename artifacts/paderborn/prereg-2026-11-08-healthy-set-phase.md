# N15_M01 phase scatter on the remaining healthy bearings K004–K006 (pre-registered 2026-11-08)

Sunday hard push 2026-11-08, NOTES #8k optional (closes the healthy-bearing set).

Written and committed before any spike, phase, reference or null number was computed on the
records below. The 60 new records (`K004`, `K005`, `K006`; conditions N15_M01_F10 and
N09_M07_F10; measurements `_1`…`_10`) are extracted from the MD5-verified `K004.rar`
(`5b9fde1c6d754806539f9a890ee6bbdd`), `K005.rar` (`28d91412ad14583fbdfda958b64a8267`) and
`K006.rar` (`b36389294fc5a21539d9fcfacfa3604a`) — MD5s as listed by the Zenodo API for record
15845309 on 2026-11-08 — and SHA-256-pinned in `foldcrypt/paderborn.py`
(`EXTRA_BEARINGS`, `HEALTHY_SET_BEARINGS`, `HEALTHY_SET_MEASUREMENTS`,
`HEALTHY_SET_CONDITIONS`) in the same commit as this file. K004, K005 and K006 have not been
used in any prior FoldCrypt / ShockDAQ analysis. CPU only, box. Extraction with 7-Zip 24.09
(`7zz`, via the new `pb.extractor()` fallback, since `unar` is still not installable); the
SHA-256 pins are the integrity check, independent of the extractor.

## Why

K001 N15_M01_F10 scatters (R_between 0.490, Table 19). K002 (0.983, Table 21) and K003
(0.989, Table 22) lock at the same condition. Paderborn has six healthy bearings (K001–K006);
this run tests the last three, so the claim "the scatter is specific to K001" is checked
against every healthy bearing the dataset has, not just two.

**Hypothesis H_set.** Among healthy bearings on this rig, N15_M01 phase scatter is a K001
property. Measurable prediction: each of K004, K005, K006 LOCKS at N15_M01 under the Q3 rule.

## Method (fixed)

Per bearing, exactly the K003 pipeline and rules (`prereg-2026-11-06-k003-phase.md`,
`ps.phase_record` + `ps.k003_phase_verdicts`): original 100 Hz |i_s| ripple reference,
`spike_indices`, `current_magnitude`, edge trim, 95–105 Hz 4th-order zero-phase Butterworth
band-pass, Hilbert phase, reference valid ≥ 10 dB, spiky ≥ 10 spikes, second-order Rayleigh on
record mean phases (`between_stats`), N-scaled null A. No fundamental-residual path.
One RNG, seed **20261108**, consumed in the fixed order K004, K005, K006 × (N15_M01_F10,
N09_M07_F10) × measurements 1..10.

Per bearing b: Q3_b ∈ {LOCKS (R_between ≥ 0.8 and p < 1e-3), SCATTERS (R_between < 0.8),
INCONCLUSIVE, UNTESTABLE (< 8 usable records in either condition)}; C3n_b ∈ {PASS, FAIL}
(N09 R_between ≥ 0.8 and p < 1e-3).

A bearing is **valid** if C3n_b = PASS and Q3_b ∉ {UNTESTABLE}.

## Set verdict S (H_set)

- **UNTESTABLE** if fewer than 2 of the 3 bearings are valid.
- **FALSIFIED** if any valid bearing has Q3 = SCATTERS.
- **HELD** if every valid bearing has Q3 = LOCKS.
- Otherwise (a valid bearing INCONCLUSIVE, none SCATTERS) **NOT SETTLED**.

Reading if HELD: with K002–K006 all locking (5/5 other healthy bearings), the N15_M01
scatter is specific to K001's records on this rig. If FALSIFIED: scatter is a recurring
healthy-bearing behaviour at low torque, and the K001-specific wording in whitepaper Tables
21–22 must be withdrawn.

## Named limits

- Same bench, drive and supply; not a second rig. Six bearings is the whole healthy set.
- Measurements `_1`…`_10` only.
- The cause of K001's scatter is not identified by this test.
- K001/K002/K003 numbers are context only (already published).

## Reporting

`scripts/healthy_set_phase.py`; log `artifacts/paderborn/healthy-set-phase-2026-11-08.log`;
metrics `artifacts/paderborn/healthy-set-phase-metrics.json`. Anything beyond this file is
exploratory and labelled so.
