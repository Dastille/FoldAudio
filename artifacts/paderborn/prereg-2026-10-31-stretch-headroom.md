# K001 headroom on spike-free stretches + why 22/40 burst D0 rows read 0 dB — pre-registered 2026-10-31

Written and committed before any stretch headroom was computed. CPU only, box, cached SHA-256-pinned
Paderborn files only (no download, no new records). Follows NOTES #8k / PR #9 (burst D0 FAIL, 18/40).

## Already seen (honest scope)

- Table 18 LP10 misses: all five on K001 (N09_M07_F10 `_6/_7/_8`, N15_M07_F10 `_10`, N15_M01_F10 `_10`).
- PR #9: neighbour-average despike failed the burst D0 (18/40 KA04 rows off by 2.6–5.7 dB; 22/40 exactly 0).
- Exploratory diagnosis of the 22 zeros was run on 2026-10-31 *before* this prereg (it uses no stretch number):
  in every zero row all 300 injected bursts were removed and the max-step sits outside any burst window; in every
  failing row 1–4 bursts survive as a two-sample plateau. Part B below locks this as a test; it is not a new
  confirmation.

## Part A — stretch headroom (the science step)

**Stretch length fixed a priori: L = 6400 samples (0.1 s at 64 kHz).** Fixed tiling: tiles start at 0, step L,
non-overlapping; the partial last tile is dropped. A tile is *spike-free* iff no sample of it lies within
G = 32 samples of a spike found by the unchanged detector `spike_indices(x, 0.5)` on the whole record, AND
`spike_indices(tile, 0.5)` (bar from the tile's own peak) is empty. Stretch headroom of a tile =
20 log10(peak/max|Δx|) of the raw tile (no filter, no despike). Record value SH = median over its spike-free
tiles; a record with < 5 spike-free tiles is UNTESTABLE (counted against HELD).

Stretch bar SB_c = min SH over KA04 `_1.._5` of condition c, floored to 0.01 dB (same rule as B_c).

- **S0 — method control (gate), real burst morphology.** Into each KA04 `_6.._10` record inject 300 K001_BURST
  bursts (`inject_bursts`, seed 20261030, 3 × peak). SH(injected) must be within 0.25 dB of SH(clean) on all
  20, with ≥ 5 spike-free tiles each. Fail → S1/S2 UNTESTABLE.
- **S1 — misses explained by K001's own level.** On the five misses: HELD if SH < SB_c on ≥ 4/5; FALSIFIED if
  ≤ 2/5; else INCONCLUSIVE.
- **S2 — generalises to K001.** On all 20 K001 `_6.._10`: HELD if SH < SB_c on ≥ 15/20; FALSIFIED if ≤ 10/20;
  else INCONCLUSIVE.
- **S3 — descriptive only.** Per-bearing median SH (K001, KA04, KI04 `_6.._10`), spike-free tile counts.

The K001 mystery is called "explained" only if S0 PASS and S1 and S2 both HELD.

## Part B — the 22/40 zeros (bug vs physics)

Prediction B1: the zero rows are complete removals, and the failures are a despike bug — the vectorised pass
replaces adjacent flagged samples simultaneously, so the small middle sample between the burst's two
same-sign lobes (K001_BURST[3], [5]) is "repaired" toward the unrepaired lobes, leaving a two-sample plateau
the single-sample detector never flags again. Test: with a fix that never replaces two adjacent samples in one
pass (keep the larger |x − neighbour mean| in each adjacent run; rest next pass), burst D0 must PASS on
≥ 38/40 KA04 rows (tol 0.25 dB, ≤ 1 % modified) and the single-sample D0 must stay PASS 40/40.
If it does, the old v1.14 D1/D2 numbers are re-run with the fixed despike and reported as-is.
