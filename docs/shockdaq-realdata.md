# ShockDAQ on measured bearing-fault recordings (CWRU)

**Date:** 2026-10-14 · **Command:** `python -m foldcrypt shockdaq-real [--cells]` · **Output:** `artifacts/realdata/metrics.json`

## Purpose

All earlier ShockDAQ results used synthetic waveforms. This study applies the same chain (ideal modulo fold → first-order unwrap → blind AC-coupling level prior → slip/edge self-checks) to measured accelerometer records from the Case Western Reserve University Bearing Data Center, a widely used public benchmark for rolling-element bearing diagnostics.

## Data

Drive-end accelerometer channel (units g), 0 hp motor load, 1796–1797 rpm. Thirteen records:

| Rate | Records |
|---|---|
| 48 kHz | 97 (normal baseline), 109 / 122 / 135 (inner race / ball / outer race @6, 0.007 in), 213 / 226 / 238 (same, 0.021 in) |
| 12 kHz | 105 / 118 / 130 (0.007 in), 209 / 222 / 234 (0.021 in) |

Each 48 kHz record is also evaluated after plain 4:1 subsampling (labelled `48→12k`), which shows the effect of sample rate on the same physical event. The files are fetched on demand from `engineering.case.edu` and verified against SHA-256 digests in `foldcrypt/realdata.py`; they are not redistributed in this repository. Reading `.mat` files requires SciPy (`pip install -e ".[real]"`).

## Method

The original CWRU acquisition did not overload. Overload is emulated in software by placing the fold threshold below the record peak, $\lambda = r\cdot\text{peak}$ with $r \in \{0.8, 0.6, 0.5, 0.4, 0.33, 0.25\}$. The recorded signal is used only for scoring. A cell counts as recovered when $\max\lvert\hat{x}-x\rvert \le 10^{-6}\cdot\text{peak}$. A failure that neither the slip nor the edge check flags is a silent failure. Kurtosis and crest factor, the two standard time-domain bearing-fault indicators, are reported for the true, clipped and fold-recovered signals.

## Results

**Totals (120 cells):** the exact-recovery condition $\max\lvert\Delta x\rvert < \lambda$ predicted the outcome in 120/120 cells. 26 cells recovered exactly and 94 failed. All 94 failures were flagged (0 silent failures), with 0 slip false alarms. The edge check fired conservatively on 3 cells that did recover (109 and 213 at $r$ = 0.4, 226 at $r$ = 0.33).

**Sample rate decides feasibility.** At 48 kHz the largest sample-to-sample step is 0.32–0.42 of the record peak, so fold can recover overloads with the rail set to 0.33–0.5 of peak (7.5–9.8 dB of extra input range, computed as $20\log_{10}(\text{peak}/\max\lvert\Delta x\rvert)$). At 12 kHz, whether recorded natively or subsampled from 48 kHz, the largest step is 1.03–1.61 times the peak. Since recovery needs $\lambda > \max\lvert\Delta x\rvert$ and overload needs $\lambda < \text{peak}$, no overload of these waveforms is recoverable at 12 kHz. Every such cell (78/78) failed and was flagged.

| Record (48 kHz) | Condition | max\|Δx\|/peak | Extra range | Lowest $r$ recovered | Clip SNR at $r$=0.5 | Kurtosis true / clipped at $r$=0.5 | Crest true / clipped at $r$=0.5 |
|---|---|---|---|---|---|---|---|
| 97 | normal | 0.42 | 7.5 dB | 0.5 | 23.2 dB | 2.8 / 2.5 | 4.2 / 2.2 |
| 109 | inner race 0.007 in | 0.38 | 8.3 dB | 0.4 | 19.5 dB | 6.0 / 4.7 | 6.1 / 3.2 |
| 122 | ball 0.007 in | 0.35 | 9.0 dB | 0.4 | 24.6 dB | 3.1 / 2.8 | 4.9 / 2.5 |
| 135 | outer race 0.007 in | 0.40 | 7.9 dB | 0.5 | 15.8 dB | 6.7 / 4.9 | 5.2 / 2.8 |
| 213 | inner race 0.021 in | 0.37 | 8.7 dB | 0.4 | 21.0 dB | 4.2 / 3.4 | 5.3 / 2.7 |
| 226 | ball 0.021 in | 0.32 | 9.8 dB | 0.33 | 29.7 dB | 3.2 / 3.0 | 5.6 / 2.8 |
| 238 | outer race 0.021 in | 0.40 | 7.9 dB | 0.5 | 19.6 dB | 20.8 / 15.9 | 11.5 / 6.0 |

Where fold recovers, it is exact, so kurtosis and crest factor are preserved exactly. Clipping at the same rail lowers both; on the 0.021 in outer-race record, kurtosis falls from 20.8 to 15.9 and crest factor from 11.5 to 6.0. Clipping therefore biases precisely the indicators used to detect bearing faults.

## Interpretation

1. The recovery condition and the blind self-checks, which were developed on synthetic data, hold on measured bearing-impact waveforms: no silent failures, no slip false alarms.
2. The usable gain is modest and rate-dependent: about 8–10 dB at 48 kHz for these records, none at 12 kHz. Bearing-fault impacts excite structural resonances in the kHz range, so the per-sample step is large. A fold front end for bearing monitoring should sample at 48 kHz or faster, or band-limit ahead of the fold.
3. Low-cost condition-monitoring nodes that sample at 10–25.6 kHz should not assume fold recovery on impact-rich signals; they still benefit from the flag, which reports the overload instead of passing a silently clipped record.

## Limitations

- Overload is applied in software to records that were acquired within range; no folding hardware was used.
- Ideal fold only; front-end errors (Section 3.7 of the technical report) were not applied to this set.
- One channel (drive end), one motor load (0 hp), one data set. CWRU is a laboratory test rig with seeded faults; field machines differ. Known issues with some CWRU records are discussed by Smith and Randall (2015).
- The `48→12k` rows use subsampling without an anti-alias filter. A filtered decimation would lower both peaks and steps.

## References

- Case Western Reserve University Bearing Data Center. <https://engineering.case.edu/bearingdatacenter>
- W. A. Smith and R. B. Randall, "Rolling element bearing diagnostics using the Case Western Reserve University data: A benchmark study," *Mechanical Systems and Signal Processing*, vol. 64–65, pp. 100–131, 2015.
