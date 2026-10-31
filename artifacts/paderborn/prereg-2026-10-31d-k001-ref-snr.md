# K001 phase scatter vs current-reference SNR (pre-registered 2026-10-31d, NOTES #8k item a2)

Written and committed before any spike, phase, reference or null number was computed on the records below.
The 80 new records (`K001` and `KI04`, all four operating conditions, measurements `_11`…`_20`) were extracted
from the already MD5-verified cached archives and SHA-256-pinned in `foldcrypt/paderborn.py`
(`REF_SNR_MEASUREMENTS`) in the same commit as this file. Nothing else about them has been looked at.
CPU only, box. No download.

## Why (exploratory, from the 2026-10-28 confirm set `_6`…`_10`)

C1–C3 held, but K001 scattered (K001-only R_between 0.657 vs KI04 0.967). The K001 records off the common
phase were N15_M01 `_7`/`_8` (+95°/+111°, ref 25.1/22.5 dB), N15_M07_F04 `_8` (R_ref 0.17, ref 16.8 dB) and
`_9` (−147°, ref 21.4 dB), N15_M07_F10 `_8` (−119°, ref 25.8 dB). Every K001 record with ref ≥ 27.7 dB sat
within ~55° of −69°. Hypothesis H_ref: the K001 scatter is a weak-reference effect (a noisy 100 Hz ripple
phase), not a property of the spikes.

## Unchanged

Phase reference, reference validity (≥ 10 dB), edge trim, spiky definition, per-record statistics,
second-order Rayleigh, null B (2,000 shifts), α = 1e-3, N-scaled null-A gate (99th pct ≤ 1.2·√(ln100/N)) —
same functions as prereg-2026-10-28-phase-confirm.md (`phase_record`, `confirm_verdicts`, `null_a_bar`).
Seed **20261031**.

## Split (fixed in advance)

Reference SNR = `ref_line_db` (100 Hz line of |i_s| over 80–120 Hz median background), already computed by
the pipeline. **Fixed bar S = 26.0 dB** (between the highest off-phase K001 ref, 25.8 dB, and the lowest
on-phase K001 ref, 27.7 dB, on `_6`…`_10`). Low = valid ref and ref < S; high = ref ≥ S.
Fallback: if either K001 bin has < 4 usable records, use the K001 median ref_db as the split (stated in the log);
if a bin still has < 4, A1/A3 are UNTESTABLE.

Deviation d_i = circular distance between record μ_i and the grand mean of the **high** K001 records.

## Predictions

**A0 — pipeline control.** Null-A gate passes on every usable record (K001 and KI04). If not, A1–A3 UNTESTABLE.

**A1 — low-SNR K001 records deviate more.** HELD if median d(low) ≥ median d(high) + 20° **and** one-sided
Mann–Whitney p < 0.05. FALSIFIED if median d(low) ≤ median d(high). Else INCONCLUSIVE.
Secondary A1b (same records): Spearman ρ(ref_db, R_ref) on K001. HELD if ρ ≥ 0.3 and p < 0.05;
FALSIFIED if ρ ≤ 0; else INCONCLUSIVE.

**A2 — KI04 stays tight.** KI04 R_between (all usable KI04) ≥ 0.8 → HELD; < 0.5 → FALSIFIED; else INCONCLUSIVE.

**A3 — dropping low-SNR K001 tightens K001.** HELD if K001-high R_between ≥ 0.8 **and** > K001-all R_between.
FALSIFIED if K001-high R_between < 0.5 or ≤ K001-all R_between. Else INCONCLUSIVE.

**Reading.** H_ref supported only if A0 passes and A1 and A3 HELD. H_ref rejected if A1 FALSIFIED or A3
FALSIFIED. Anything else: not settled.

## Named confound

Reference SNR co-varies with operating condition (low-torque M01 and low-force F04 give a weaker ripple on
`_6`…`_10`). The per-condition table is reported; a HELD here cannot separate "weak reference" from
"condition" unless low and high records occur within one condition — that is reported as exploratory.
Same bench, same drive: fresh records, not fresh hardware.

## Reporting

Script `scripts/ref_snr_phase.py`; log `artifacts/paderborn/ref-snr-phase-2026-10-31d.log`;
metrics `artifacts/paderborn/ref-snr-phase-metrics.json`. Anything beyond this file is exploratory.
