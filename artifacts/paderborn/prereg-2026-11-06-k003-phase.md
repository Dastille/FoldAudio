# K003 N15_M01 phase scatter check (pre-registered 2026-11-06, NOTES #8k optional)

Written and committed before any spike, phase, reference or null number was computed on the
records below. The 20 new records (`K003`, conditions N15_M01_F10 and N09_M07_F10, measurements
`_1`…`_10`) were extracted from the MD5-verified cached `K003.rar` (Zenodo 15845309, MD5
`08b61792e1058dc47dd21071666bca2c`) and SHA-256-pinned in `foldcrypt/paderborn.py`
(`K003_PHASE_MEASUREMENTS`, `K003_PHASE_CONDITIONS`, `EXTRA_BEARINGS["K003"]`) in the same
commit as this file. K003 has not been used in any prior FoldCrypt / ShockDAQ analysis. CPU
only, box. (Extraction used the 7-Zip 24.09 `7zz` binary because `unar` is not installable on
the box today; the SHA-256 pins are the integrity check, independent of the extractor.)

## Why

Table 19 (v1.19): K001 N15_M01_F10 scatters (R_between 0.490). Table 21 (v1.20): K002 does
**not** scatter at the same condition (R_between 0.983), so the scatter is not a property of
the N15_M01 condition, the drive, or reference SNR alone. This check asks whether any other
healthy bearing on the same rig scatters like K001 or locks like K002.

**Hypothesis.** K001's N15_M01 phase scatter is bearing-/record-specific. On fresh K003, using
the same original 100 Hz |i_s| ripple reference pipeline as `ps.phase_record` / confirmatory
phase (not the fundamental residual split), N15_M01 should lock (R_between ≥ 0.8) if the
scatter is unique to K001; if it scatters, the effect is not unique to K001 and a follow-up
is warranted.

## Method (fixed)

Unchanged from prereg-2026-10-28-phase-confirm.md / prereg-2026-10-31d-k001-ref-snr.md:
`spike_indices`, `current_magnitude`, edge trim `EDGE_TRIM_S`, 95–105 Hz 4th-order zero-phase
Butterworth band-pass, Hilbert phase, `ripple_line_db` validity ≥ 10 dB, spiky ≥ 10 spikes,
`circ_stats`, second-order Rayleigh on record mean phases (`between_stats`), N-scaled null A
(`null_a_bar`). Seed **20261106**. No fundamental residual / `fund_record` path today unless
Q3 SCATTERS **and** a disclosed amendment is committed before any residual number is computed.

Usable = spiky (≥ 10 spikes) AND reference line ≥ 10 dB (existing rules).

## Predictions (K003, fresh)

N_M01 = usable N15_M01 records, N_N09 = usable N09. If N_M01 < 8 or N_N09 < 8 → everything
below is **UNTESTABLE**.

**Q3 — N15_M01 scatters on K003.** R_between (second-order Rayleigh on record mean phases) at
N15_M01. **SCATTERS** if R_between < 0.8; **LOCKS** if ≥ 0.8 AND Rayleigh p < 1e-3; else
**INCONCLUSIVE**.

**C3n — N09 control locks.** N09 R_between ≥ 0.8 AND Rayleigh p < 1e-3 → **PASS**; else
**FAIL** (pipeline / control concern).

**Reading.**
- If Q3 LOCKS and C3n PASS → supports “scatter is K001-record-specific, not a property of
  healthy bearings / low-torque condition.”
- If Q3 SCATTERS and C3n PASS → scatter is not unique to K001; open a follow-up (do **not**
  silently run fund residual today unless time leftover AND amend prereg before computing
  residual numbers).
- If C3n FAIL → control failed; Q3 reported but marked as such.
- Otherwise → not settled.

## Named limits

- Third healthy bearing, same bench and drive. Not a second rig.
- Measurements `_1`…`_10` only (20 mats); enough for ≥ 8 usable / condition without the heavy
  `_11.._20` fund set used on K002.
- The cause of any scatter (or lock) is not identified by this test.
- Comparison to K001 (0.490) and K002 (0.983) is descriptive context only; those numbers were
  already published.

## Reporting

Script `scripts/k003_phase.py`; log `artifacts/paderborn/k003-phase-2026-11-06.log`;
metrics `artifacts/paderborn/k003-phase-metrics.json`. Anything beyond this file is
exploratory.
