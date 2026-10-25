# ShockDAQ on a second measured dataset: Paderborn KAt, 64 kHz (NOTES #8g, 2026-10-23; spike-origin probe #8h, 2026-10-25)

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

## Interpretation

1. The safety result transfers: on a second rig and sensor chain, the recovery condition predicted every cell and no failure was silent.
2. The benefit does not transfer. "Sample at 48 kHz or faster" (CWRU) is necessary but not sufficient: the waveform's largest single-sample step decides, and single-sample spikes remove the headroom completely. On spike-free records (KA04) fold bought 3.2–4.2 dB here, about half of what CWRU 48 kHz gave.
3. A fold front end for such signals needs the spikes removed before the fold or must treat them as overloads it cannot recover. Tested on 2026-10-25 (above): the spikes are electrical, and a causal 10 kHz low-pass ahead of the fold restores 3.1–6.3 dB on every spiky record while keeping the envelope fault lines. This is a software model of an analog filter acting on the recorded (already 30 kHz-filtered, digitised) signal, not a hardware result.

## Limitations

- 12 records from 3 bearings, one measurement per operating condition; not the full 32-bearing set.
- Overload applied in software to records captured within range, as with CWRU.
- The spike count threshold (half the peak) is a chosen convention.
- Spike origin (2026-10-25): electrical by the pre-registered criteria, but the physical coupling path is not identified, the 100 Hz gating result is exploratory (post hoc), and the probe used one measurement per condition from two bearings. The filter study applies a modelled filter to recorded data after the rig's own 30 kHz charge-amplifier filter and 64 kHz digitiser; a real filter in front of a modulo ADC would see the analog signal, including any content above 32 kHz that this recording cannot show.

## References

1. C. Lessmeier, J. K. Kimotho, D. Zimmer, and W. Sextro, "Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification," *PHM Society European Conference*, vol. 3, no. 1, 2016. doi:10.36001/phme.2016.v3i1.1577
2. J. van den Hoogen, "Paderborn Bearing Dataset," Zenodo, 2025. doi:10.5281/zenodo.15845309 (mirror of <https://groups.uni-paderborn.de/kat/BearingDataCenter/>, accessed 2026-10-23)
3. Schaeffler Technologies, bearinx-online catalogue, "6203-2Z basic frequency factors" (BPFO factor 3.0531, BPFI factor 4.9469), accessed 2026-10-25.
