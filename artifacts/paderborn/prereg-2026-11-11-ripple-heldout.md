# Does 100 Hz ripple depth separate scatter from lock bearings on held-out records? (pre-registered 2026-11-11)

Weekday slice 2026-11-11 (soft freeze, light), NOTES #8k optional step "pre-register ripple
depth on held-out N15_M01 records". **Exploratory** (6 bearings). Written and committed, with
the 40 new SHA-256 pins, before any ripple-depth number was computed on a held-out record.

## Background (already published)

Table 24 (2026-11-10, `scatter-covariates-metrics.json`): on the label records, the bearing
median of the 100 Hz |i_s| ripple modulation depth (`ps.ripple_phase` → depth, same function as
the phase pipeline) was, non-blind:

| bearing | label (Tables 19–23) | training records | training median depth |
|---|---|---|---|
| K001 | SCATTER | N15_M01_F10 _11.._20 | 0.012715 |
| K002 | LOCK | _6.._20 | 0.006119 |
| K003 | LOCK | _1.._10 | 0.006678 |
| K004 | SCATTER | _1.._10 | 0.013697 |
| K005 | LOCK | _1.._10 | 0.005682 |
| K006 | SCATTER | _1.._10 | 0.015312 |

Direction seen: SCATTER > LOCK. Gap: lock max 0.006678 (K003), scatter min 0.012715 (K001).

## Held-out records (fixed)

All N15_M01_F10, measurements not used for the labels or Table 24:

- K001 _1.._10, K002 _1.._5 — already pinned.
- K003, K004, K005, K006 _11.._20 — 40 new SHA-256 pins added to `foldcrypt/paderborn.py` in
  this commit (extracted from the MD5-verified cached archives with 7-Zip; only file hashes were
  computed).

Total 55 records. `pb.RIPPLE_HELDOUT_MEASUREMENTS`.

## Honest disclosure: what is not blind

- **K001 _2.._10 depths are already printed** in `spike-phase-2026-10-27.log` (_2.._5:
  0.0114, 0.0122, 0.0148, 0.0072) and `spike-phase-confirm-2026-10-28.log` (_6.._10: 0.0152,
  0.0057, 0.0050, 0.0149, 0.0133). I saw these while writing this file. K001 held-out is
  therefore **non-blind**; results are reported with and without K001.
- K002 _1.._5 depths were never printed (`k002-check-2026-10-31d.log` has no depth column).
- K003–K006 _11.._20 were never extracted before today.

So the blind part is 5 bearings (2 scatter K004/K006, 3 lock K002/K003/K005).

## Predictions (direction pre-stated: SCATTER > LOCK)

Per-record depth → bearing value = median over that bearing's held-out records.

- **H1 (primary)**: on the held-out bearing medians, every SCATTER bearing (K001, K004, K006)
  has larger depth than every LOCK bearing (K002, K003, K005). Exact one-sided permutation p
  over the 20 labellings (statistic mean rank SCATTER − mean rank LOCK); with direction stated,
  the floor is 1/20 = 0.05. HELD iff all three scatter medians exceed all three lock medians;
  FALSIFIED otherwise.
- **H1b (blind-only)**: same rule on the 5 blind bearings (K004, K006 vs K002, K003, K005);
  C(5,2) = 10 labellings, one-sided floor 0.10.
- **H2 (fixed threshold)**: T = 0.0097 (midpoint of the training gap, 0.009696, rounded to two
  significant figures). Each held-out bearing median is classified SCATTER iff depth > T. HELD
  iff 6/6 bearings are classified correctly.
- **Descriptive (no verdict)**: per-record accuracy at T (55 records), and whether record
  ranges of the two groups overlap.

## Controls (fixed)

- **P+ (pipeline reproducibility)**: recompute the training bearing medians above from the
  65 training records with the same code; each must match the published value to relative
  tolerance 1e-9. If not, all verdicts are void.
- **P− (negative)**: the held-out bearing medians under the shuffled labelling from
  `ps.shuffled_labels` (seed 20261110, as Table 24) must read OVERLAPS (guaranteed for
  distinct values if the code is right). If not, all verdicts are void.
- Unit tests on synthetic currents with a known 100 Hz modulation depth must recover it.

## What a result means

- HELD on H1 and H1b: ripple depth is stable across records within a bearing and tracks the
  scatter label on these 6 bearings. It is still 6 bearings on one rig: correlation, not
  mechanism, and not a bearing-level confirmation (that needs a new bearing whose label is
  predicted from depth before its phase is computed).
- FALSIFIED: the Table 24 depth lead was record-selection noise; drop it.

## Named limits

n = 6 (5 blind); one rig, drive and supply; labels are thresholded statistics (K005 0.910 is
the closest lock); measurement-number ranges differ per bearing; K001 non-blind.

## Reporting

`ps.ripple_heldout_*`; `scripts/ripple_heldout.py`; `tests/test_ripple_heldout.py`; log
`artifacts/paderborn/ripple-heldout-2026-11-11.log`; metrics
`artifacts/paderborn/ripple-heldout-metrics.json`.
