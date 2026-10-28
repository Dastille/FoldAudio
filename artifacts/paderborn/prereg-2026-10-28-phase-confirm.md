# Paderborn spike phase — confirmatory re-run on fresh records (pre-registered 2026-10-28, NOTES #8k item a)

Written and committed before any spike, phase, reference or null number was computed on the records below.
The 40 new records (`K001` and `KI04`, all four operating conditions, measurements `_6`…`_10`) were extracted
from the already MD5-verified cached archives and SHA-256-pinned in `foldcrypt/paderborn.py`
(`CONFIRM_MEASUREMENTS`) in the same commit as this file; nothing else about them has been looked at.
CPU only, box. No download.

## Why

On 2026-10-27 the pre-registered phase verdicts were UNTESTABLE because the fixed null-A pipeline bar
(99th percentile of random-time R ≤ 0.2) cannot be met for N < ~116 spikes. With the gate removed, the
exploratory read on measurements `_2`…`_5` was: 30/32 records burst-like (R ≥ 2/π), R_between 0.873,
grand mean phase −65.7° (1.83 ms before the maximum of the 100 Hz ripple of the current magnitude).
This file turns that exploratory read into fixed, falsifiable predictions on records never analysed.

## Unchanged from prereg-2026-10-27-phase.md

Phase reference (Clarke |i_s| of `phase_current_1/2`, means removed → zero-phase 4th-order Butterworth
95–105 Hz → Hilbert; 0° = ripple maximum), reference validity (line ≥ 10 dB over 80–120 Hz background),
edge trim (0.1 s), spiky definition (≥ 10 `isolated_spikes`, frac 0.5, and ≥ 10 after trim),
per-record statistics (R_ref, μ, Rayleigh p), second-order Rayleigh across records, null B (2,000 independent
circular shifts), α = 1e-3. Code paths are the same functions (`paderborn_spikes.phase_record`,
`between_stats`, `null_shift_p`). Seed for this run: **20261028**.

## Changed (the only changes)

1. **Null-A pipeline gate, N-scaled.** Per record, 2,000 random-time draws; the 99th percentile of null R_ref
   must be ≤ **1.2 × √(ln 100 / N)** on every valid record (Rayleigh tail P(R > r) ≈ exp(−N r²); on 10-27 the
   observed ratio was 0.959–1.049). If any valid record fails, C1–C3 are UNTESTABLE.
2. **Records:** confirmation set = spiky records among `K001`/`KI04` × 4 conditions × `_6`…`_10` (up to 40).
   `KA04` is not used (no spikes on `_1`…`_5`).
3. **Predictions now carry the 10-27 exploratory numbers as targets** (below).

## Predictions (valid-reference spiky records, count V; need V ≥ 0.5 × spiky, else UNTESTABLE)

**C1 — burst-like.** HELD if R_ref ≥ 2/π and p < α on ≥ 80 % of V. FALSIFIED if R_ref ≤ 0.5 on ≥ 50 % of V.
Else INCONCLUSIVE.

**C2 — one fixed phase across records.** HELD if R_between ≥ 0.8, p_between < α and null-B empirical p ≤ 0.01.
FALSIFIED if R_between < 0.5 or p_between ≥ 0.05. Else INCONCLUSIVE.

**C3 — same phase as the exploratory estimate.** Tested only if C2 HELD (else UNTESTABLE). Let
d = circular distance between the grand mean μ̄ and −65.7°. HELD if d ≤ 30°; FALSIFIED if d > 60°;
else INCONCLUSIVE. (Named assumption, unchanged: this is a statement about the current-magnitude ripple, not
proof of rectifier conduction; there is no DC-link channel.)

**N09 subset** (900 rpm, reference cannot be motor-made): same numbers reported; if its grand mean differs from
the N15 grand mean by > 45°, that is a recorded caveat, not a change of verdict.

## Named limitation

Measurements `_1`…`_20` of one Paderborn setting are successive recordings of the same bearing on the same
rig, so `_6`…`_10` are fresh records, not fresh hardware or a fresh drive. A HELD here says the phase is stable
within this test bench; it says nothing about other inverters.

## Reporting

Per record as on 10-27, plus null-A ratio (99th pct / √(ln100/N)). Anything beyond this file is labelled
exploratory. Script `scripts/confirm_spike_phase.py`; log `artifacts/paderborn/spike-phase-confirm-2026-10-28.log`;
metrics `artifacts/paderborn/spike-phase-confirm-metrics.json`.
