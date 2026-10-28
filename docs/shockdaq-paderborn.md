# ShockDAQ on a second measured dataset: Paderborn KAt, 64 kHz (NOTES #8g, 2026-10-23; spike-origin probe #8h, 2026-10-25; spike phase #8j, 2026-10-27)

## Purpose

The CWRU study ([`shockdaq-realdata.md`](shockdaq-realdata.md)) found that sample rate decides whether fold can recover an overload at all: 7.5–9.8 dB of extra range at 48 kHz, none at 12 kHz. This note tests that finding on a second test rig, sensor chain and higher rate: the Paderborn University KAt Bearing DataCenter [1], whose bearing-housing accelerometer channel (`vibration_1`) is sampled at 64 kHz.

## Data

Bearings K001 (healthy), KA04 (outer ring, fatigue pitting from an accelerated lifetime test) and KI04 (inner ring, fatigue pitting) [1, Table 5]. For each bearing, measurement `_1` at the four operating conditions N15_M07_F10, N09_M07_F10, N15_M01_F10 and N15_M07_F04 (12 records, 4 s, 256,001 samples each). Each record is also evaluated after plain 4:1 subsampling (64→16 kHz), as with CWRU 48→12 kHz. The archives come from the Zenodo mirror [2] (CC BY 4.0), are checked against Zenodo's MD5s, and only the 12 members are extracted (needs `unar`) and pinned by SHA-256 in `foldcrypt/paderborn.py`. Nothing is redistributed. The .mat files do not state the channel unit, so results are given as ratios and dB.

## Method

Identical to CWRU: the recorded signal is treated as the true input; overload is applied in software with $\lambda = r\cdot\text{peak}$, $r \in \{0.8, 0.6, 0.5, 0.4, 0.33, 0.25\}$; ideal fold; blind recovery; recovered means max error ≤ 10⁻⁶ · peak (`realdata.eval_record`). Four predictions were written down before any record was scored: [`artifacts/paderborn/prereg-2026-10-23.md`](../artifacts/paderborn/prereg-2026-10-23.md).

## Results

`python scripts/run_paderborn.py` → [`artifacts/paderborn/metrics.json`](../artifacts/paderborn/metrics.json), log [`artifacts/paderborn/run-2026-10-23.log`](../artifacts/paderborn/run-2026-10-23.log). 144 cells.

| Prediction | Outcome |
|---|---|
| P1: slew rule predicts every cell | **held**, 144/144 |
| P2: zero silent failures | **held**, 0 (140 failures, all flagged; 0 slip false alarms) |
| P3: every 64 kHz record has headroom, median ≥ 7.5 dB | **falsified**: 9/12 positive, median +0.38 dB, max +4.17 dB |
| P4: at 16 kHz, ≥ 7 of 12 records have no headroom | **held**, 12/12 none |

| Bearing | 64 kHz max\|Δx\|/peak | 64 kHz headroom | single-sample spikes per record (64 kHz) |
|---|---|---|---|
| K001 healthy | 0.999–1.027 | −0.23 to +0.01 dB | 176–845 |
| KA04 outer ring | 0.619–0.691 | +3.21 to +4.17 dB | 0–2 |
| KI04 inner ring | 0.917–1.071 | −0.60 to +0.75 dB | 49–194 |

Only 4 of 144 cells recovered (the four KA04 records at $r$ = 0.8).

**Why P3 failed.** In the healthy and inner-ring records the peak itself is a single-sample spike: the signal jumps to near its peak for one sample and straight back (for example K001 N15_M07_F10 around sample 232,125: −0.09, −4.93, 0.07). `paderborn.isolated_spikes` counts samples whose step in and step out both exceed half the peak with opposite signs: 49–845 per 64 kHz record for K001 and KI04, 0–2 for KA04, and 0 on all seven CWRU 48 kHz records (same function, same log). A spike makes max|Δx| about equal to the peak, so $\lambda > \max\lvert\Delta x\rvert$ and $\lambda < \text{peak}$ cannot both hold. The higher sample rate does not help against content that is one sample wide at any rate. **Not established on 2026-10-23:** whether these spikes are mechanical (impacts with content above the sampled band) or electrical (the rig's inverter switches at 16 kHz [1]). The 2026-10-25 probe below addresses this.

## Spike-origin probe (NOTES #8h, 2026-10-25)

**Question.** Are the single-sample spikes electrical (inverter switching coupling into the vibration channel) or mechanical (bearing kinematics, shaft angle), and would a filter in front of the fold restore headroom without removing fault content?

**Pre-registration.** Hypotheses, statistics, thresholds and the seed were committed before any spike timing, current-channel, filter or envelope result was computed: [`artifacts/paderborn/prereg-2026-10-25.md`](../artifacts/paderborn/prereg-2026-10-25.md). Rig facts used are from [1]: 6203 bearing with 8 balls, ball diameter 6.75 mm, pitch diameter 28.55 mm, contact angle 0° (Table 1), giving BPFO = 3.0543 f_r and BPFI = 4.9457 f_r (Schaeffler's 6203-2Z catalogue lists 3.0531 / 4.9469 [3]); PMSM with 4 pole pairs; inverter switching frequency 16 kHz; PCB 336C04 accelerometer with a Kistler 5015A charge amplifier low-passed at 30 kHz; currents and vibration sampled synchronously at 64 kHz (the .mat files store them on the same raster, so they are sample-aligned).

**Method.** `foldcrypt/paderborn_spikes.py`, `python scripts/probe_paderborn_spikes.py` → [`artifacts/paderborn/spike-probe-metrics.json`](../artifacts/paderborn/spike-probe-metrics.json), log [`artifacts/paderborn/spike-probe-2026-10-25.log`](../artifacts/paderborn/spike-probe-2026-10-25.log) (about 25 s CPU). Spikes are the `isolated_spikes` samples of the 10-23 sweep; the 8 records with ≥ 10 spikes (K001 and KI04, all four conditions) are analysed and KA04 is the control. Phase locking of spike times to a frequency band is measured by the vector strength R (1 = every spike at the same phase, ≈ 1/√N for random times) with a Rayleigh p-value Bonferroni-corrected across the band, α = 10⁻³. H1 (electrical): the 16 kHz ± 1 % band is locked (H1a), or ≥ 50 % of spikes fall within ±2 samples of a phase-current step above its 99th percentile and at ≥ 3 × the rate at 2,000 random samples (H1b). H2 (mechanical): f_r, BPFO or BPFI (± 3 %) locked, provided none of three non-kinematic decoy bands (1.37, 3.71, 5.53 f_r) is. H3: causal 4th-order Butterworth low-pass at 10 kHz (LP10) or 5 kHz (LP5) before the fold gives ≥ 3.0 dB headroom on ≥ 7 of 8 spiky records, keeps the envelope-spectrum fault line (BPFI on KI04, BPFO on KA04) within 3 dB, and the full fold chain stays at 0 silent failures. A 3-point median (MED3) is reported as a bound only: no analog filter is a median, and a digital median would sit behind a conventional ADC, not in front of a modulo one.

**Results (pre-registered).**

| Hypothesis | Verdict | Key numbers |
|---|---|---|
| H1 electrical | **held** | 16 kHz band locked in 8/8 spiky records (R 0.296–0.886, p 6.3·10⁻⁴⁸ to 2.3·10⁻⁴); current coincidence (H1b) met in 1/8: 28–56 % of spikes vs 3.9–6.3 % at random samples (5.0–14.2 × chance), below the 50 % bar in 7 records |
| H2 mechanical | **falsified** | evidence in 1/8 (KI04 N09, BPFO, p 7.1·10⁻⁴); 2/8 with the decoy rule ignored (adds K001 N09, healthy, BPFO band, p 8.3·10⁻¹⁶). BPFI never reached p < 10⁻³ on the inner-ring records (lowest p 1.0·10⁻³). Shaft frequency f_r locked in 0/8 |
| H3 pre-fold filter | **held** (via LP10) | LP10: headroom 3.13–6.30 dB on 8/8 spiky records (raw −0.60 to +0.75 dB); fault line change −0.46 to +2.02 dB on all 8 KI04/KA04 records; 14/48 fold cells recovered (raw 0/48), 0 silent, rule 48/48 |

Per-filter detail (spiky records unless stated):

| Filter | Headroom | Recovered fold cells | Fault-line change, KI04 + KA04 | Pre-registered verdict |
|---|---|---|---|---|
| none (raw) | −0.60 to +0.75 dB | 0/48 | — | — |
| LP10 (causal Butterworth, 10 kHz) | +3.13 to +6.30 dB | 14/48, 0 silent | −0.46 to +2.02 dB | held |
| LP5 (causal Butterworth, 5 kHz) | +8.58 to +10.86 dB | 35/48, 0 silent | −3.09 to +1.59 dB (KI04 N15_M07_F04: 24.2 → 21.1 dB) | falsified (one line lost by 0.09 dB past the 3 dB bar) |
| MED3 (digital bound only) | −0.41 to +2.24 dB | 1/48, 0 silent | −0.16 to +2.48 dB | falsified (0/8 reach 3 dB) |

On KA04 (control, spike-free) LP10 gives 3.33–6.42 dB (raw 3.21–4.17 dB) and LP5 9.63–16.14 dB. Kurtosis falls with filtering (K001 13.1–20.2 → 5.0–8.5 with LP10; KI04 5.2–16.5 → 3.9–5.2). On the healthy K001 records the raw kurtosis is set by the spikes, so the drop there is the spike being removed, not fault content; the envelope fault lines, which are the pre-registered criterion, are kept.

**Descriptive and exploratory findings.** Spike height is a median 7.0–39.3 × the larger neighbouring sample, and no spike appears on either current channel at the same sample (0 coincident `isolated_spikes`). A 30 kHz low-pass charge amplifier should not pass a genuine accelerometer signal that rises and returns within one 15.6 µs sample at this height, which also points to entry after that filter (an argument, not a test). Two checks were added **after** the pre-registered run and are labelled exploratory in the log: (i) every spiky record is phase-locked to 100 Hz (R 0.74–0.96, p ≤ 7.1·10⁻¹⁹), including the 900 rpm records, where the motor electrical frequency is 60 Hz and is not locked (R 0.119 and 0.148); 100 Hz is twice the 50 Hz supply, which suggests bursts gated by the supply (for example DC-link rectifier charging), not by the motor. (ii) Equal-width control bands at 8, 12, 20 and 24 kHz are locked in 0/32 record-bands (lowest p 2.3·10⁻³), so the 16 kHz result is specific to the switching frequency rather than an artefact of clustered spike times. The spike index modulo 4 (one 16 kHz period) is flat, so the carrier is not locked to the DAQ clock; the best-locking frequency varies from 15,844.7 to 16,139.4 Hz between records, which this probe does not explain.

**Caveat on the decoy rule.** The pre-registered decoy bands fired on 6 of 8 records, mostly decoy 2 (3.71 f_r = 92.75 Hz ± 3 % at 1,500 rpm), whose band edge lies 4.5 Hz from the strong 100 Hz locking. The decoys were chosen to avoid shaft harmonics and bearing lines but were not checked against 100 Hz. The H2 verdict does not depend on this: with the decoy rule ignored, H2 evidence is 2/8, which is still in the falsified range.

**Conclusion.** The spikes are electrical in origin to the standard set in advance: locked to the 16 kHz inverter switching frequency on every spiky record, not locked to shaft speed or bearing kinematics, and (exploratory) gated at 100 Hz, independent of shaft speed. They are a property of this rig's electrical environment, not of the bearing vibration. The mechanism (radiated or conducted switching EMI, ground loop, rectifier-related bursts) is not determined. For a fold front end the practical consequence is that the anti-alias stage matters: a causal 10 kHz 4th-order low-pass ahead of the fold restored 3.1–6.3 dB of headroom on every spiky record without losing the envelope fault lines; 5 kHz bought 8.58–10.86 dB but cost one inner-ring line 3.09 dB. A real front end must also keep the EMI out of the analog path; filtering only helps because the spike energy is broadband and short.

## Held-out confirmation (NOTES #8i, 2026-10-26)

**Question.** Do the 2026-10-25 findings hold on measurements that played no part in forming them? Measurement `_1` generated the hypotheses (including the post hoc 100 Hz observation); this step re-runs the unchanged probe on measurements `_2`…`_5` of the same 12 bearing × condition cells (48 records, extracted from the MD5-verified archives already cached, SHA-256 pinned in `foldcrypt/paderborn.py` before analysis).

**Pre-registration.** [`artifacts/paderborn/prereg-2026-10-26-heldout.md`](../artifacts/paderborn/prereg-2026-10-26-heldout.md), committed (3b4c938) before any held-out number was computed. Methods, bands, α = 10⁻³ and seed are those of 10-25. R1: 100 Hz locked on ≥ 90 % of spiky records. R1b: on the 900 rpm spiky records (motor electrical frequency f_e = 60 Hz), 100 Hz locked on ≥ 90 % and f_e locked on ≤ 25 % (supply, not motor). R2: 16 kHz locked on ≥ 90 %. R3: mechanical evidence (same H2 rule) on ≤ 25 %. R4: LP10 gives ≥ 3.0 dB headroom on ≥ 87.5 % of spiky records, loses no testable fault line, 0 silent failures, rule agrees in every cell.

**Method.** `ps.run_heldout` / `ps.heldout_verdicts`, `python scripts/heldout_paderborn.py` → [`artifacts/paderborn/heldout-metrics.json`](../artifacts/paderborn/heldout-metrics.json), log [`artifacts/paderborn/heldout-2026-10-26.log`](../artifacts/paderborn/heldout-2026-10-26.log) (about 75 s CPU).

**Results (pre-registered).** 32 of 48 records are spiky (all 16 K001 and all 16 KI04; 24–493 spikes); KA04 again has none (0–1).

| Rule | Verdict | Key numbers |
|---|---|---|
| R1 100 Hz lock | **held** | 32/32 (R 0.40–0.98, every p ≤ 9.2·10⁻⁹) |
| R1b supply, not motor | **held** | 900 rpm spiky records: 100 Hz 8/8, f_e (60 Hz) 1/8 (K001 N09 `_5`, p 3.2·10⁻⁵) |
| R2 16 kHz lock | **held** | 30/32; not locked on KI04 N15_M01_F10 `_2` (p 0.15) and `_5` (p 0.015) |
| R3 mechanical absent | **held** | 3/32, all healthy K001 at 900 rpm (`_3`, `_4`, `_5`), each in the BPFO band with the peak at 47.19 Hz, the band's upper edge |
| R4 LP10 rule | **inconclusive** | headroom ≥ 3.0 dB on 27/32 (84 %, bar 87.5 %); range 2.13–6.58 dB (raw −0.60 to +1.16 dB); 32 fault lines testable, 0 lost, change −1.79 to +1.55 dB; 50/192 fold cells recovered, 0 silent, rule 192/192 |

The five LP10 shortfalls are 2.13–2.99 dB (four K001 records and KI04 N09 `_4`). Described, not judged: LP5 reached ≥ 3 dB on 32/32 (8.46–11.48 dB) but again lost the BPFI line on KI04 N15_M07_F04, now on `_2` (22.4 → 18.5 dB) and `_3` (22.3 → 19.0 dB), the same condition where it failed on `_1`; MED3 reached 3 dB on 1/32.

**Exploratory (post hoc, not pre-registered).** (i) The 3.0 dB bar was taken from the spike-free KA04 `_1` records. On the held-out KA04 records, which have no spikes, raw headroom is 1.60–5.04 dB and 5 of 16 are below 3.0 dB, so the bar is not a property of spike-free data on this rig; LP10's 27/32 should be read against that. (ii) The three R3 hits sit at the BPFO band edge on a healthy bearing, which looks like leakage from a line just above the band rather than bearing kinematics; this is a reading, not a test. (iii) At 900 rpm the 6 f_e band (360 Hz) is strongly locked on the K001 records (p ≤ 1.9·10⁻²⁸), consistent with a motor-drive electrical source but not separated from it here.

**Conclusion.** The electrical origin replicates on held-out data: 16 kHz switching lock 30/32, 100 Hz lock 32/32, and at 900 rpm the lock follows the supply (100 Hz) rather than the motor (60 Hz, 1/8). The 100 Hz gating is now a confirmed (pre-registered, held-out) result rather than exploratory. Mechanical origin stays absent (3/32). The LP10 design rule is weaker than `_1` suggested: it keeps every fault line and never fails silently, but clears 3 dB on 84 % of spiky records, short of the pre-registered 87.5 %, so it is recorded as inconclusive, not held. The `_1` "3.13–6.30 dB on 8/8" result should not be quoted without this.

## Spike phase against the 100 Hz current ripple (NOTES #8j, 2026-10-27)

**Question.** The spikes lock to 100 Hz (held-out R1, above), but R(f) measures phase from the arbitrary record start, so it does not say where in the 100 Hz cycle they fall. Burst-like timing at one fixed point of the supply cycle (for example rectifier conduction) and switching edges whose coupling is only weakly modulated by the supply would both lock at 100 Hz.

**Pre-registration.** [`artifacts/paderborn/prereg-2026-10-27-phase.md`](../artifacts/paderborn/prereg-2026-10-27-phase.md), committed (de4d54f) before any phase number was computed. Phase reference, built from the currents only: the two phase currents (means removed) → Clarke transform (3-wire assumption) → current space-vector magnitude |i_s| → zero-phase 4th-order Butterworth band-pass 95–105 Hz → Hilbert phase; 0° = maximum of the 100 Hz ripple of |i_s|. In a balanced machine |i_s| carries no component at the motor frequency, and at 900 rpm neither f_e (60 Hz) nor 2 f_e (120 Hz) is near 100 Hz. The reference is valid if the 100 Hz line of |i_s| is ≥ 10 dB above the 80–120 Hz background. Spikes within 0.1 s of either record end are dropped. Confirmation set: the 32 held-out spiky records (`_2`…`_5`); `_1` is descriptive only. P1 (burst-like): R_ref ≥ 2/π (the value for spikes uniform over half a cycle) with p < 10⁻³ on ≥ 90 %; falsified if R_ref ≤ 0.5 (the ceiling for sinusoidal gating) on ≥ 50 %. P2 (same phase on every record): second-order Rayleigh on the per-record mean phases, R_between ≥ 0.8, p < 10⁻³, and a circular-shift null (2,000 draws, each record shifted independently) with empirical p ≤ 0.01. P3 (near the ripple maximum): grand mean within ±45°; falsified beyond ±90°. Pipeline control (null A): 2,000 uniform random spike sets per record; the 99th percentile of their R_ref must be ≤ 0.2 on every record, else P1–P3 are untestable. Seed 20261027.

**Method.** `ps.phase_record` / `ps.phase_verdicts` in `foldcrypt/paderborn_spikes.py`, `python scripts/probe_spike_phase.py` → [`artifacts/paderborn/spike-phase-metrics.json`](../artifacts/paderborn/spike-phase-metrics.json), log [`artifacts/paderborn/spike-phase-2026-10-27.log`](../artifacts/paderborn/spike-phase-2026-10-27.log) (about 10 s CPU). Synthetic tests (`tests/test_spike_phase.py`) recover spikes placed at a known ripple phase to within 5° and give R < 0.2 for uniform spikes.

**Results (pre-registered): P1, P2, P3 untestable.** The reference was valid on 32/32 records (100 Hz line 21.6–37.1 dB above background; ripple depth 0.27–1.48 % of mean |i_s|). The null-A pipeline bar failed: the 99th percentile of random-set R_ref exceeded 0.2 on 7 records (up to 0.439). This is a design error in the pre-registration, not a pipeline fault: those 7 records have only 22–112 spikes, and for N random phases the 99th percentile of R is about √(ln 100 / N), which is above 0.2 for N < 116. The observed null percentiles are 0.959–1.049 × that analytic value on all 32 records, i.e. the reference adds no concentration of its own. By the rule as written, no verdict is issued.

**Exploratory (post hoc, not pre-registered).** With the null-A gate removed (all other rules unchanged): R_ref 0.39–0.95; 30/32 records meet the burst bar (R_ref ≥ 2/π, p < 10⁻³) and 1/32 is at or below 0.5 (KI04 N15_M07_F10 `_3`, 0.391); the per-record mean phases agree (R_between 0.873, p 2.6·10⁻¹¹; circular-shift null p 5.0·10⁻⁴, the smallest value 2,000 draws can give, null 99th percentile 0.368); grand mean −65.7°, which is 1.83 ms before the |i_s| ripple maximum — between the ±45° "near the maximum" window and the ±90° falsification limit. On the 25 records that do pass the 0.2 bar the same reading holds (23/25 burst-like, R_between 0.841, grand mean −66.7°). The 900 rpm subset, where the reference cannot be motor-made, gives R_ref 0.735–0.949 on 8/8, R_between 0.999 and grand mean −60.7°, 7.1° from the 1500 rpm subset (−67.7°), so the 1500 rpm reference does not appear to be shifted by the motor. Per-record mean phases range from −148.7° to +14.3°. The seen `_1` records give the same picture (R_ref 0.484–0.928, grand mean −68.8°).

**Reading.** If the null-A bar is set by sample size, as it should have been, the spikes behave like bursts at a fixed point of the supply cycle, about 60–70° (1.7–1.9 ms) ahead of the maximum of the current-magnitude ripple, rather than like switching edges weakly modulated by the ripple. That is consistent with rectifier-related bursts, but the relation between the DC-link voltage ripple and the |i_s| ripple of this drive is not known, so the phase cannot be mapped onto rectifier conduction from these data. A confirming run needs a fresh pre-registration with an N-scaled null-A bar on records not used here.

## Confirmatory spike phase on fresh records (NOTES #8k, 2026-10-28)

**Pre-registration.** [`artifacts/paderborn/prereg-2026-10-28-phase-confirm.md`](../artifacts/paderborn/prereg-2026-10-28-phase-confirm.md), committed (4ce52fb) together with the SHA-256 pins of the 40 new records before any number was computed on them. Records: K001 and KI04 × 4 operating conditions × measurements `_6`…`_10` (`pb.CONFIRM_MEASUREMENTS`), extracted from the cached MD5-verified archives. Reference, edge trim, spiky rule, statistics and shift null as on 10-27; seed 20261028. Changes: null-A gate scaled with spike count (99th pct ≤ 1.2·√(ln 100/N)); C1 burst bar ≥ 80 % of records; C3 asks whether the grand mean is within 30° of the 10-27 exploratory −65.7° (falsified beyond 60°).

**Method.** `ps.confirm_verdicts` / `ps.null_a_bar` in `foldcrypt/paderborn_spikes.py`, `python scripts/confirm_spike_phase.py` → [`artifacts/paderborn/spike-phase-confirm-metrics.json`](../artifacts/paderborn/spike-phase-confirm-metrics.json), log [`artifacts/paderborn/spike-phase-confirm-2026-10-28.log`](../artifacts/paderborn/spike-phase-confirm-2026-10-28.log) (~9 s CPU). Synthetic rule checks: `tests/test_spike_phase_confirm.py`.

**Results (pre-registered): C1, C2, C3 held.** 40/40 records spiky (14–657 spikes after trim), reference valid 40/40 (16.8–34.5 dB; ripple 0.22–1.52 %). Null-A gate passed on every record (0.952–1.044 × √(ln 100/N)). C1: 38/40 burst-like (R_ref 0.17–0.94; one record ≤ 0.5). C2: R_between 0.805, p 5.5e-12, shift-null p 5.0e-4 (the floor of 2,000 draws). C3: grand mean −68.9°, 3.2° from −65.7° (1.91 ms before the ripple maximum). N09 subset: 10/10 burst-like, R_between 0.999, −62.1°; N15 subset: R_between 0.744, −71.9°; difference 9.8° (no motor caveat).

**Exploratory (post hoc).** C2 passed narrowly; the N15 subset alone would be inconclusive. By bearing: KI04 R_between 0.967 (−62.8°), K001 0.657 (−77.9°). K001 N15_M01_F10 `_7`/`_8` sit at +94.9°/+110.6°, and the only non-concentrated record (K001 N15_M07_F04 `_8`, R_ref 0.172) has the weakest reference in the set (16.8 dB, depth 0.22 %). Whether the healthy-bearing scatter is a weak-reference effect or a real second timing mode is not tested here.

**Reading.** The fixed-phase, supply-synchronous burst reading now holds as a pre-registered result on fresh records of the same rig. It still does not identify the coupling (no DC-link channel), and successive measurements of one bench are not independent hardware.

## Interpretation

1. The safety result transfers: on a second rig and sensor chain, the recovery condition predicted every cell and no failure was silent.
2. The benefit does not transfer. "Sample at 48 kHz or faster" (CWRU) is necessary but not sufficient: the waveform's largest single-sample step decides, and single-sample spikes remove the headroom completely. On spike-free records (KA04) fold bought 3.2–4.2 dB here, about half of what CWRU 48 kHz gave.
3. A fold front end for such signals needs the spikes removed before the fold or must treat them as overloads it cannot recover. Tested on 2026-10-25 (above): the spikes are electrical, and a causal 10 kHz low-pass ahead of the fold restores 3.1–6.3 dB on every spiky record while keeping the envelope fault lines. This is a software model of an analog filter acting on the recorded (already 30 kHz-filtered, digitised) signal, not a hardware result.

## Limitations

- 12 records from 3 bearings, one measurement per operating condition (spike probe re-tested on 4 more measurements per condition, 2026-10-26); not the full 32-bearing set.
- Overload applied in software to records captured within range, as with CWRU.
- The spike count threshold (half the peak) is a chosen convention.
- Spike origin (2026-10-25): electrical by the pre-registered criteria, but the physical coupling path is not identified, the 100 Hz gating result is exploratory (post hoc), and the probe used one measurement per condition from two bearings. The filter study applies a modelled filter to recorded data after the rig's own 30 kHz charge-amplifier filter and 64 kHz digitiser; a real filter in front of a modulo ADC would see the analog signal, including any content above 32 kHz that this recording cannot show.
- Spike phase (2026-10-27): the pre-registered verdicts are untestable because the null-A bar did not scale with spike count; the burst-like, fixed-phase reading is exploratory. The phase reference is the current-magnitude ripple (assumes a 3-wire, near-balanced machine), not the DC-link voltage, which the dataset does not record.

## References

1. C. Lessmeier, J. K. Kimotho, D. Zimmer, and W. Sextro, "Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification," *PHM Society European Conference*, vol. 3, no. 1, 2016. doi:10.36001/phme.2016.v3i1.1577
2. J. van den Hoogen, "Paderborn Bearing Dataset," Zenodo, 2025. doi:10.5281/zenodo.15845309 (mirror of <https://groups.uni-paderborn.de/kat/BearingDataCenter/>, accessed 2026-10-23)
3. Schaeffler Technologies, bearinx-online catalogue, "6203-2Z basic frequency factors" (BPFO factor 3.0531, BPFI factor 4.9469), accessed 2026-10-25.
