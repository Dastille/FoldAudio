# ShockDAQ on a second measured dataset: Paderborn KAt, 64 kHz (NOTES #8g, 2026-10-23)

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

**Why P3 failed.** In the healthy and inner-ring records the peak itself is a single-sample spike: the signal jumps to near its peak for one sample and straight back (for example K001 N15_M07_F10 around sample 232,125: −0.09, −4.93, 0.07). `paderborn.isolated_spikes` counts samples whose step in and step out both exceed half the peak with opposite signs: 49–845 per 64 kHz record for K001 and KI04, 0–2 for KA04, and 0 on all seven CWRU 48 kHz records (same function, same log). A spike makes max|Δx| about equal to the peak, so $\lambda > \max\lvert\Delta x\rvert$ and $\lambda < \text{peak}$ cannot both hold. The higher sample rate does not help against content that is one sample wide at any rate. **Not established:** whether these spikes are mechanical (impacts with content above the sampled band) or electrical (the rig's inverter switches at 16 kHz [1]); this note makes no claim either way.

## Interpretation

1. The safety result transfers: on a second rig and sensor chain, the recovery condition predicted every cell and no failure was silent.
2. The benefit does not transfer. "Sample at 48 kHz or faster" (CWRU) is necessary but not sufficient: the waveform's largest single-sample step decides, and single-sample spikes remove the headroom completely. On spike-free records (KA04) fold bought 3.2–4.2 dB here, about half of what CWRU 48 kHz gave.
3. A fold front end for such signals would need the spikes removed before the fold (analog band-limiting, if they are out-of-band content) or would have to treat them as overloads it cannot recover. This is speculative until tested.

## Limitations

- 12 records from 3 bearings, one measurement per operating condition; not the full 32-bearing set.
- Overload applied in software to records captured within range, as with CWRU.
- Spike origin not determined; the spike count threshold (half the peak) is a chosen convention.

## References

1. C. Lessmeier, J. K. Kimotho, D. Zimmer, and W. Sextro, "Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification," *PHM Society European Conference*, vol. 3, no. 1, 2016. doi:10.36001/phme.2016.v3i1.1577
2. J. van den Hoogen, "Paderborn Bearing Dataset," Zenodo, 2025. doi:10.5281/zenodo.15845309 (mirror of <https://groups.uni-paderborn.de/kat/BearingDataCenter/>, accessed 2026-10-23)
