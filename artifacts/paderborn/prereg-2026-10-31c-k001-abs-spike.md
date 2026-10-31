# K001 headroom with an absolute small-spike guard and a same-tile control — pre-registered 2026-10-31 (third slice)

Written and committed before any headroom number of this method was computed. CPU only, box, cached
SHA-256-pinned Paderborn files only. Follows PR #11 (G0 FAIL → UNTESTABLE; sub-threshold spikes fill gaps).

## Already seen before this prereg (honest scope)

- PR #11: K001 below both 1024-tile bars 20/20 (exploratory); KI04 LP10 below 10/20; old own-peak rule would
  reject 100 % (K001) / 98 % (KI04) of guarded tiles vs 0.6 % on KA04.
- PR #11 G0 design bug: clean and injected records were tiled separately (guard taken from each record), so the
  0.51/0.62 dB errors were tile-subset noise (0.00 dB when the same tiles are used).
- Threshold calibration (KA04 `_1.._5` only, no K001/KI04 headroom seen): spike score
  s_i = min(|x_i − x_{i−1}|, |x_{i+1} − x_i|) where the two steps have opposite sign; per-record max on KA04
  `_1.._5` is 0.90–1.34 (signal units). T_c = max over the five records of condition c:
  N15_M07_F10 1.337, N09_M07_F10 1.132, N15_M01_F10 1.315, N15_M07_F04 1.077.

## Method (fixed in advance)

- **Absolute detector**: flag sample i iff s_i > T_c (T_c above, from KA04 spike-free records; not record peak).
  By construction 0 flags on KA04 `_1.._5`.
- **Tiles**: L = 1024, non-overlapping from 0, partial last dropped. A tile is *abs-guarded* iff no flag in
  [s0 − 32, s0 + L + 128) (128-sample post guard for the causal LP10 tail) AND no record-level spike
  (`spike_indices(x, 0.5)`) within 32 samples. ≥ 5 tiles needed, else UNTESTABLE (counts against HELD).
- AH_raw / AH_lp = median tile headroom 20 log10(peak/max|Δx|) on raw / whole-record LP10, same tiles.
- Bars RB_c / LB_c = min over KA04 `_1.._5` of AH_raw / AH_lp, floored to 0.01 dB.
- Also per record: AH_lp_flagged = median LP10 tile headroom over tiles that pass the record-level guard but
  FAIL the absolute guard (small-spike tiles); coverage = abs-guarded / total tiles.

## Controls (gate)

- **A0 same-tile**: inject 300 K001_BURST bursts (seed 20261030, 3× peak) into KA04 `_6.._10`; tiles chosen
  ONCE from the injected record; AH on clean x vs injected on THOSE tiles; |Δ| ≤ 0.25 dB raw and LP10, ≥ 5 tiles,
  20/20.
- **A0s small-spike sensitivity**: inject 300 bursts with max |sample| = 0.75·T_c (steps ≈ 1.5·T_c) into the same
  records; the absolute detector must flag ≥ 95 % of injected bursts (any flag within the burst span) on 20/20.
- A0 or A0s FAIL → A1–A3 UNTESTABLE.

## Predictions / verdicts

- **A1 (K001 own level low after LP10)**: AH_lp < LB_c on ≥ 4/5 Table 18 misses AND ≥ 15/20 K001 `_6.._10` HELD;
  ≤ 2/5 or ≤ 10/20 FALSIFIED; else INCONCLUSIVE.
- **A2 (KI04 is not low)**: KI04 `_6.._10` AH_lp < LB_c on ≤ 5/20 HELD (low level K001-specific); ≥ 10/20 FALSIFIED.
- **A3 (small spikes explain the misses)**: on ≥ 4/5 misses, AH_lp ≥ LB_c AND AH_lp − AH_lp_flagged ≥ 1.0 dB → HELD;
  ≤ 2/5 → FALSIFIED; else INCONCLUSIVE (a miss without both tile sets counts against HELD).

## Outcomes for question (d)

- "K001 own level lower" only if gate PASS, A1 HELD, A2 HELD.
- "Small spikes explain the misses" only if gate PASS and A3 HELD.
- **CLOSE (d) as "not separable on this rig"** if gate PASS and any of: K001 UNTESTABLE (< 5 tiles) on ≥ 10/20;
  A2 FALSIFIED (KI04 equally low → K001 ≈ KI04-class EMI level, not a bearing property); or A1 and A3 both not HELD.
- Gate FAIL → method UNTESTABLE; (d) stays open (no closure from a broken control).

## Amendment A (written after the first run; disclosed)

First run (`abs-spike-v1-2026-10-31.log`, `abs-spike-v1-metrics.json`): A0 PASS (0.00 dB, 20/20); **A0s FAIL**
(0 % detected) → A1–A3 UNTESTABLE, outcome "gate FAIL; (d) stays open". Diagnosis (control bug, not detector):
the K001_BURST samples alternate around zero (2.255, 0.134, −2.286), so the normalised burst's largest spike
score is 1.005 × amplitude, not ≈ 2 ×; amplitude 0.75·T_c gives score ≈ 0.75·T_c < T_c, undetectable by
design. The text's intent ("steps ≈ 1.5·T_c") is restored by amplitude **1.5·T_c**. Also: three KA04 `_1.._5`
records have 1 flag each because T_c was rounded to 3 decimals (not exactly 0 by construction); bars unaffected
(KA04 coverage ~1.0).

Seen before this amendment: the v1 K001/KI04 tile counts and AH values (K001 0 abs-guarded tiles 20/20; KI04
LP10 below LB 10/20). The amendment changes only the A0s amplitude; detector, T_c, tiles, bars, A1–A3 thresholds
and the closure rules are unchanged. v1 stays the primary result; the amended run decides whether the gate
failure was the control's fault.
