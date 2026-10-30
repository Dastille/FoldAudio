# Is K001's own spike-free level below the KA04 bar? — pre-registered 2026-10-30 (NOTES #8k item d)

Written and committed before any despiked number was computed. CPU only, box, cached SHA-256-pinned files only
(no download, no new records).

## What is already seen (honest scope)

On 2026-10-29 (Table 18) the raw and LP10 headroom of all 60 records `K001`/`KA04`/`KI04` `_6`…`_10` were
computed and committed (`artifacts/paderborn/headroom-bar-metrics.json`). All five LP10 misses against the
condition bar B_c are on the healthy bearing `K001`: N09_M07_F10 `_6`, `_7`, `_8`; N15_M07_F10 `_10`;
N15_M01_F10 `_10`. This test is therefore **explanatory, not a fresh confirmation**: the miss pattern is known,
the despiked headroom is not.

## Hypothesis H_d

The misses happen because the healthy bearing's own spike-free signal has less headroom than the `KA04`
(outer-ring damage) records the bar was taken from, i.e. the named assumption of 2026-10-29 ("KA04's spike-free
level transfers to K001") is false for K001 — not because LP10 fails to remove the spikes.

## Method

Despike: find the isolated single-sample spikes with the unchanged detector (`spike_indices`, step in and step
out both > 0.5·peak, opposite signs); replace each with the mean of its two neighbours; repeat (peak is
recomputed each pass) until no spike is found or 50 passes. Despiked headroom DS = 20 log10(peak / max|Δx|) of
the result (unchanged `headroom_db`, `max_sample_jump`). No filter is applied, so DS is comparable with the
raw `KA04` headroom that defines B_c (3.31 / 3.94 / 2.95 / 1.60 dB).

## Predictions

**D0 — method control (gate).** Into each of the 20 `KA04` `_6`…`_10` records inject 300 single-sample
spikes (± 3 × record peak, alternating sign, positions drawn with seed 20261030, at least 4 samples apart and
away from the ends). Despiking must bring headroom back within 0.25 dB of the despiked uninjected record on
all 20, modifying ≤ 1 % of samples. If D0 fails, D1 and D2 are UNTESTABLE.

**D1 — the misses are explained by K001's own level.** On the five LP10 misses listed above: HELD if DS < B_c
on ≥ 4/5; FALSIFIED if ≤ 2/5; else INCONCLUSIVE.

**D2 — LP10 reaches the record's own spike-free level.** Set: the 40 spiky `K001`/`KI04` `_6`…`_10`.
HELD if LP10 headroom (committed value) ≥ DS on ≥ 87.5 % (35/40); FALSIFIED if ≤ 50 %; else INCONCLUSIVE.

**D3 — descriptive only (no verdict).** Per-condition median DS for `K001` and `KI04` next to the median raw
`KA04` `_6`…`_10`; count of K001 records with DS ≥ B_c; fraction of samples modified; passes used; LP10 misses
re-scored against each record's own DS (exploratory — the "own bar" was chosen after seeing the misses).

Exit status 0 whenever the run completes; verdicts are results, not errors.
