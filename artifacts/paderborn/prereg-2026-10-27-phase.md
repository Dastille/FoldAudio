# Paderborn spike phase vs the 100 Hz supply-gated ripple — pre-registered (2026-10-27, NOTES #8j item 1)

Written and committed before any spike phase, current-ripple reference or null-control number was computed.
Inspected beforehand: only the committed 10-25 / 10-26 logs and metrics (spike counts, 100 Hz vector strength
R 0.40–0.98 on the 32 held-out spiky records, R1/R1b held) and the .mat channel layout (`vibration_1`,
`phase_current_1`, `phase_current_2` on the same 64 kHz raster, 256,001 samples). No new data are downloaded;
K002 is out of scope. CPU only, box.

## Question

The 10-25 (exploratory) and 10-26 (held-out, pre-registered R1/R1b) probes showed that the single-sample spikes on
`vibration_1` are phase-locked to 100 Hz = 2 × the 50 Hz supply, not to the motor. They did not say *where* in the
100 Hz cycle the spikes fall, because R(f) uses the arbitrary record start as the phase origin. Two readings:

- **Burst reading** (e.g. DC-link rectifier conduction bursts): spikes confined to a narrow part of each 100 Hz
  cycle, at the same place in the cycle on every record.
- **Weak-gating reading** (PWM edges whose coupling is only modulated by the supply ripple): spikes spread over the
  cycle with a sinusoidal preference, i.e. low concentration.

## Phase reference (fixed)

Per record, from the motor phase currents only (the vibration channel is never used to build the reference):
1. i1, i2 = `phase_current_1`, `phase_current_2`, each minus its record mean (removes sensor offset, which would
   otherwise put an f_e line into the magnitude).
2. Clarke transform, assuming a 3-wire machine (i1 + i2 + i3 = 0): i_α = i1, i_β = (i1 + 2 i2)/√3;
   current space-vector magnitude m(t) = √(i_α² + i_β²). For a balanced machine m(t) has no component at the motor
   electrical frequency f_e = 4 f_r; supply ripple on the DC link that reaches the current loop appears in m(t) at
   100 Hz. (Current-sensor gain mismatch gives 2 f_e = 120 Hz at 900 rpm, 200 Hz at 1500 rpm — outside the band.)
3. r(t) = zero-phase band-pass of m(t) − mean(m): 4th-order Butterworth 95–105 Hz, `sosfiltfilt` (no group delay).
4. φ(t) = angle of the analytic signal of r(t) (`scipy.signal.hilbert`). **Phase 0 = maximum of the 100 Hz ripple
   of the current magnitude**; ±180° = its minimum.

**Reference validity (per record, decided before looking at spikes):** amplitude spectrum of m − mean(m) (whole
record, Hann window); line = max over 98–102 Hz; background = median over 80–120 Hz excluding 98–102 Hz. Valid if
line ≥ 10 dB above background. Records with an invalid reference are excluded and counted. There is no fallback
reference. If fewer than half of the held-out spiky records have a valid reference, P1–P3 are UNTESTABLE.

**Edge trim:** spikes within 0.1 s (6,400 samples) of either record end are dropped (filter/Hilbert edge effects).
A record enters the analysis if it is spiky (≥ 10 `isolated_spikes`, frac 0.5, same as 10-23/10-25/10-26) and
still has ≥ 10 spikes after the trim.

## Records

- **Confirmation set:** the held-out measurements `_2`…`_5` (same 12 cells as 10-26), spiky records only —
  expected all 16 K001 and all 16 KI04 = 32 (KA04 has no spikes). These are used for every verdict.
  Note: these records were used on 10-26 to confirm the 100 Hz *frequency* lock, but their spike *phase* relative to
  any current reference has never been computed.
- **Seen set (descriptive only):** measurement `_1` spiky records (8). Reported in the log, labelled exploratory;
  they do not enter any verdict.
- **Subset check:** the 900 rpm (N09) confirmation records, where f_e = 60 Hz and 2 f_e = 120 Hz are both far from
  100 Hz so the reference cannot be motor-made. Same statistics reported separately.

## Statistics

Per record (k = 1…N spikes, θ_k = φ(n_k)):
- R_ref = |mean exp(iθ_k)| (Rayleigh vector strength against the current reference), mean phase μ = arg of that mean,
  Rayleigh p = exp(−N R_ref²) (single fixed reference, no frequency search, no Bonferroni).
- Across records: second-order Rayleigh on the per-record mean phases μ_j (unweighted): R_between, grand mean μ̄,
  p_between = exp(−J R_between²), J = number of records.

Concentration bars are tied to simple shapes: spikes uniform within a ±90° (half-cycle) window give R = 2/π = 0.637;
spike probability ∝ 1 + a cos θ (sinusoidal gating, 0 ≤ a ≤ 1) gives R = a/2 ≤ 0.5.

α = 1e-3.

## Hypotheses and decision rules (confirmation set, valid-reference records, count V)

**P1 — burst-like concentration.** HELD if R_ref ≥ 2/π and p < α on ≥ 90 % of V. FALSIFIED (spread / weak-gating
reading) if R_ref ≤ 0.5 on ≥ 50 % of V. Else INCONCLUSIVE.

**P2 — fixed phase across records.** HELD if R_between ≥ 0.8, p_between < α, AND the shift-null control (below)
gives empirical p ≤ 0.01. FALSIFIED if R_between < 0.5 or p_between ≥ 0.05. Else INCONCLUSIVE.

**P3 — near the current-ripple maximum.** Only tested if P2 HELD (else UNTESTABLE). HELD if |μ̄| ≤ 45°;
FALSIFIED if |μ̄| > 90°; else INCONCLUSIVE. Named assumption: the sign/phase relation between the DC-link voltage
ripple and the current-magnitude ripple is not known for this drive (current control may invert or shift it), so P3
is a statement about the *current* ripple maximum only, not proof of rectifier conduction.

**N09 subset:** same P1/P2 numbers reported. If the N09 grand mean differs from the N15 grand mean by > 45°, that is
recorded as a caveat (N15 reference possibly influenced by the motor), not a change of verdict.

## Null controls (fixed seed 20261027)

- **Null A — random times (per record):** 2,000 draws of N spike times uniform over the trimmed record (without
  replacement), R_ref against the same reference. Pipeline check: the 99th percentile of null R_ref must be ≤ 0.2 on
  every record. If not, the method is declared invalid and P1–P3 are UNTESTABLE.
- **Null B — independent circular shifts (across records):** 2,000 draws; in each, every record's spike train is
  circularly shifted by an independent uniform integer offset within the trimmed window (keeps spike count and
  within-record spacing, destroys any fixed relation to the reference). R_between recomputed; empirical
  p = (1 + #{null ≥ observed}) / 2,001. This detects a fake cross-record lock produced by the pipeline itself
  (e.g. filter delay or a reference artefact applied identically to every record).

## Reporting

Per record: N, reference line SNR (dB), ripple modulation depth (r amplitude / mean m), R_ref, μ, p, fraction of
spikes within ±45° of μ, null A 99th percentile. Anything computed beyond this file is labelled exploratory.
Code: `foldcrypt/paderborn_spikes.py` (phase functions), `scripts/probe_spike_phase.py`; log
`artifacts/paderborn/spike-phase-2026-10-27.log`, metrics `artifacts/paderborn/spike-phase-metrics.json`.
