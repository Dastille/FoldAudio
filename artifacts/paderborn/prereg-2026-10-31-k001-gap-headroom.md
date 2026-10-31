# K001 headroom on short spike-guarded tiles (L = 1024), raw and LP10 — pre-registered 2026-10-31 (second slice)

Written and committed before any headroom number of this method was computed. CPU only, box, cached
SHA-256-pinned Paderborn files only. Follows PR #10 (6400-sample tiles UNTESTABLE, 0 clean tiles on K001).

## Already seen before this prereg (honest scope)

- Table 18: all five LP10 misses are K001 (N09_M07_F10 `_6/_7/_8`, N15_M07_F10 `_10`, N15_M01_F10 `_10`).
- Feasibility check (tile COUNTS only, no headroom computed): with the PR #10 tile rule at L = 1024, K001
  `_6.._10` still has 0 clean tiles on 20/20 records (KI04 median 2, KA04 median 248). Debug on K001
  N09 `_6`: 53 tiles at L = 1024 pass the record-level spike guard; **all 53 are then rejected by the
  tile's own-peak detector** (`spike_indices(tile, 0.5)`); same at L = 512 (246 → 0).
- Diagnosis (method bug, not physics): the own-peak criterion is outcome-censoring. A hit needs two
  opposite steps > 0.5 × tile peak, i.e. it can only fire when the tile's raw headroom is < 6.02 dB, which is
  the very quantity being compared to bars of 1.60–3.94 dB. It removes exactly the low-headroom tiles. It is
  dropped. Shortening L alone would not have fixed the PR #10 UNTESTABLE.

## Method (fixed in advance)

L = 1024 samples (16 ms), non-overlapping tiles from sample 0, partial last tile dropped. A tile is
*guarded* iff no sample lies within G = 32 samples of a record-level spike (`spike_indices(x, 0.5)` on the whole
raw record). No tile-own-peak criterion. Record needs ≥ 5 guarded tiles, else UNTESTABLE (counts against HELD).

- SH_raw = median over guarded tiles of 20 log10(peak/max|Δx|) of the raw tile.
- SH_lp = same on the record filtered once with `apply_filter(x, "LP10")` (whole record, causal), tiled with
  the same guarded starts (guard from the raw record).
- Bars per condition from KA04 `_1.._5`: SB_c (raw) and LB_c (LP10) = min record value, floored to 0.01 dB.

## Predictions / verdicts

- **G0 control (gate)**: inject 300 K001_BURST bursts (`inject_bursts`, seed 20261030) into each KA04 `_6.._10`;
  |SH_raw(inj) − SH_raw(clean)| ≤ 0.25 dB and same for SH_lp, ≥ 5 guarded tiles, on 20/20. Fail → G1–G4 UNTESTABLE.
- **G1 (own level, raw)**: SH_raw < SB_c on ≥ 4/5 misses HELD; ≤ 2/5 FALSIFIED; else INCONCLUSIVE.
- **G2 (generalises, raw)**: SH_raw < SB_c on ≥ 15/20 K001 `_6.._10` HELD; ≤ 10 FALSIFIED.
- **G3 (own level after the LP10 front end)**: SH_lp < LB_c on ≥ 4/5 misses AND ≥ 15/20 K001 HELD;
  ≤ 2/5 or ≤ 10/20 FALSIFIED; else INCONCLUSIVE.
- **G4 (specificity: KI04 is not low)**: KI04 `_6.._10` SH_lp < LB_c on ≤ 5/20 HELD; ≥ 10/20 FALSIFIED.
- **G5 descriptive**: per-bearing median SH_raw, SH_lp, guarded tiles; fraction of guarded tiles the old
  own-peak rule would reject (sub-threshold spike prevalence) per bearing.

Prediction direction: K001 (healthy) has lower own-vibration headroom than KA04 → G1, G2, G3 HELD, G4 HELD.
"K001 explained (own spike-free level lower)" only if G0 PASS and G3 and G4 both HELD. If G1/G2 hold but G3
fails, the raw shortfall is high-frequency content above 10 kHz (sub-threshold spikes) and the LP10 misses are
NOT explained by own level. Kill: G0 FAIL, or G3 FALSIFIED → own-level hypothesis dropped for LP10 misses.
