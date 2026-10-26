# Paderborn held-out confirmation — pre-registered (2026-10-26, NOTES #8i)

Written and committed before any spike, band, filter or headroom number was computed on the held-out files.
Done beforehand: the 48 held-out .mat files were extracted from the MD5-verified Zenodo archives already in the
cache and their SHA-256 pinned (`foldcrypt/paderborn.py`, `MAT_SHA256`). No file was loaded for analysis.

## Why

The 2026-10-25 probe (`prereg-2026-10-25.md`, measurement `_1` only) produced two findings this step re-tests on
data that played no part in forming them:
- the exploratory (post hoc) observation that spike times lock to 100 Hz on 8/8 spiky records, including the
  900 rpm records where the motor electrical frequency f_e = 4 f_r = 60 Hz is not locked (read then as
  supply-gated, 2 × 50 Hz, not motor); and
- the pre-registered results H1a (16 kHz inverter lock 8/8), H2 (mechanical falsified) and H3 via LP10 (causal
  4th-order Butterworth 10 kHz low-pass ahead of the fold restores ≥ 3 dB headroom and keeps fault lines).

## Held-out set (fixed)

Measurements `_2`, `_3`, `_4`, `_5` of the same 12 cells (K001, KA04, KI04 × N15_M07_F10, N09_M07_F10,
N15_M01_F10, N15_M07_F04) = 48 records. Measurement `_1` is excluded (it generated the hypotheses).
Every method, band, threshold and seed is unchanged from `prereg-2026-10-25.md` and `foldcrypt/paderborn_spikes.py`
at commit 9737369. "Spiky" = ≥ 10 `isolated_spikes` (frac 0.5). Bands: 100 Hz ± 3 %, 16 kHz ± 1 %,
f_e = 4 f_r ± 3 %; Rayleigh p with Bonferroni over ⌈BW·T⌉; α = 1e-3 per band. Let S = number of spiky records.

## Decision rules

**R1 — 100 Hz lock replicates.** 100 Hz band significant on ≥ 90 % of S → HELD; ≤ 50 % → FALSIFIED; else
INCONCLUSIVE.
**R1b — supply, not motor.** On spiky N09 records (f_e = 60 Hz): 100 Hz significant on ≥ 90 % AND f_e band
significant on ≤ 25 % → HELD; 100 Hz on ≤ 50 % or f_e on ≥ 50 % → FALSIFIED; else INCONCLUSIVE. Fewer than 4
spiky N09 records → UNTESTABLE. (At N15, f_e = 100 Hz coincides with the 100 Hz band, so N15 cannot separate
supply from motor.)
**R2 — 16 kHz lock replicates (H1a).** 16 kHz band significant on ≥ 90 % of S → HELD; ≤ 50 % → FALSIFIED.
**R3 — mechanical stays absent.** H2 evidence (f_r, BPFO or BPFI significant and no decoy band significant,
same rule as 10-25) on ≤ 25 % of S → HELD (still absent); ≥ 75 % → FALSIFIED (the 10-25 H2 verdict is
overturned); else INCONCLUSIVE.
**R4 — LP10 rule.** HELD if headroom ≥ 3.0 dB on ≥ 87.5 % of S (the 7-of-8 bar), the fault line is preserved
(filtered envelope line SNR ≥ raw − 3 dB) on every testable KI04 (BPFI) and KA04 (BPFO) record (raw ≥ 6 dB),
the full fold chain (`realdata.eval_record`, 6 ratios) on the filtered spiky records has 0 silent failures, and
the slew rule agrees in every cell. FALSIFIED if headroom ≥ 3.0 dB on ≤ 50 % of S, or any testable line is lost,
or any silent failure. Else INCONCLUSIVE.

LP5 and MED3 are reported for description only (no verdict).

## Deferred (not in this step)

K002 (second healthy bearing; needs a new ~170 MB download) and the phase of each spike against the 100 Hz
current ripple — left for a later slice to keep this one light.

CPU only, box. No GPU.
