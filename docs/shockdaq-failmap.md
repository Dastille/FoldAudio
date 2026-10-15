# ShockDAQ fail map — where fold breaks, and whether it tells you

Slice: 2026-10-07 weekday (NOTES #1). Code: `foldcrypt/failmap.py`. Run:
`python -m foldcrypt shockdaq-failmap` → `artifacts/shockdaq/failmap.json`, `failmap.svg`.

## Plain-language result

Fold recovery has one limit: the signal must move less than λ volts between
two samples. As a spec line for a DAQ buyer:

> **max slew rate < λ × sample rate** (λ = 5 V, 51.2 kHz → 256,000 V/s;
> for a pure sine, peak V × frequency Hz < ~40,700).

On a 56-cell sweep (ringing impact, peak 6–40 V, ring 0.5–12 kHz, blind
recovery with no original) that rule predicted success/failure in **56/56**
cells; across 5 noise seeds, **280/280**.

The sales-relevant part: **every failure flagged itself** (166/166 failures
across 5 seeds, 0 silent) using two checks that only need the capture:

1. **Slip check** — the quiet baseline before and after the event disagree by
   more than λ (a wrong unwrap leaves a 2λ step). Caught every failure; zero
   false alarms on good recoveries.
2. **Edge warning** — some folded step came within 10 % of λ, i.e. recovery
   ran at its limit. Also caught every failure; warned on 1 good-but-borderline
   cell (6 V at 6 kHz).

Neither flag fires on the shipped gearbox/impact demos.

So the honest pitch is: soft-clip fails silently; fold either recovers the
peak exactly or tells you it couldn't. The flag turns a corrupt acceptance
test into a "re-run this capture" event.

## Grid (λ = 5 V, sr = 51.2 kHz, seed 7)

```
peak V \ ring Hz    500   1000   2000   3000   4000   6000   8000  12000
               6     ok     ok     ok     ok     ok    ok~     F!     F!
               8     ok     ok     ok     ok     ok     F!     F!     F!
              10     ok     ok     ok     ok     F!     F!     F!     F!
              14     ok     ok     ok     F!     F!     F!     F!     F!
              20     ok     ok     F!     F!     F!     F!     F!     F!
              30     ok     ok     F!     F!     F!     F!     F!     F!
              40     ok     F!     F!     F!     F!     F!     F!     F!
```
ok = recovered blind (SNR ≥ 60 dB) · ok~ = recovered, edge warning ·
F! = failed and flagged · FS = failed silently (none).

## What this means for the OEM conversation

- Fold covers big, slower overloads (machine start-up, low/mid-frequency
  impacts) — the gearbox/structural band. It does **not** rescue sharp
  high-kHz ringing beyond the slew limit; raising the sample rate raises the
  limit linearly (2× sr → 2× allowed slew).
- The test burst carries a 0.4× harmonic at 2.1 f, so its limit is ~1.8×
  tighter than the pure-sine number.

## Named assumptions

Synthetic ringing burst only (not field data); main grid is ideal (no quantization — see below); λ = 5 V is a
demo rail, not a specific OEM part; 60 dB SNR threshold for "recovered".
Next proof still needed: one real IEPE capture (NOTES #3).

## Quantization (2026-10-09, NOTES #5)

Question: does a real N-bit ADC move the slew edge? Run
`python -m foldcrypt shockdaq-failmap --quant` → `artifacts/shockdaq/quantmap.json`.
The same 56-cell grid is passed through an N-bit modulo-ADC (step
Δ = λ/2^(N−1)); "ok" = every recovered sample within one LSB of the true input.

```
 bits  step(V)  ok  fail  rule  tight  flagged  SILENT  slipFA  edge-on-ok
ideal        -  23    33    56      -       33       0       0           1
    4   0.6250  23    33    56     54       33       0       0           1
    6   0.1562  23    33    56     56       33       0       0           1
   8-24  …      23    33    56     56       33       0       0           1
```

Plain-language result: **the slew edge does not move.** The rule max slew < λ·sr
predicted all 56 cells at every bit depth from 4 to 24, the same 33 cells fail
at every depth, and every failure still flags itself (0 silent, 0 slip false
alarms). The worst-case rule "max|Δx| < λ − Δ" is only needed to be that strict
at ≤4 bits, where it is actually slightly *worse* than the plain rule (54/56)
because rounding errors rarely line up adversely. Quantization costs
resolution (LSB-sized error), not range or honesty.

Caveats: single noise seed (7) in the CLI sweep (an ad-hoc 5-seed run for
3–24 bits showed the same pattern — 0 silent failures at every depth; plain rule
matched 280/280 from 4 bits up, 275/280 at 3 bits); quantizer is the ideal
mid-riser in `modulo.py`, no ADC nonlinearity, no thermal/clock noise.

## Non-ideal front end (2026-10-11 Sunday hard push, NOTES #6)

Question: with sensor noise and a sloppy modulo-ADC, does the slew rule still
predict failure, and do failures still announce themselves? Run
`python -m foldcrypt shockdaq-failmap --nonideal` →
`artifacts/shockdaq/nonidealmap.json` (24 configs × 56 cells × 5 seeds = 280 cells
per config, ~20 s CPU). **All synthetic**; the non-idealities are a toy model,
not a measured part:

| Effect | Model |
|---|---|
| sensor/electronic noise | white Gaussian before the fold, SNR vs the burst's RMS (σ = rms/10^(SNR/20)) |
| gain mismatch *g* | fold subtracts 2λ(1+g) per wrap, recovery assumes 2λ |
| wrap-threshold error *e* | wrap fires at λ(1−e); spill beyond the ADC rail clips |
| offset *o* | quantizer DC offset o·λ (excluded from the accuracy error — a plain ADC has it too) |
| INL *a* | smooth bow a·λ·sin(πy/λ) on the folded value |
| combo-mild / combo-bad | 60 dB + g .1 % + e .5 % + o .5 % + INL .2 % + 16-bit / 40 dB + g .5 % + e 1 % + o 1 % + INL 1 % + 12-bit |

"ok" = no unwrap slip (max error < λ). "accurate" = ok **and** max error ≤ 1 % of
the true peak.

### Results (280 cells per config; full table in the CLI output)

- **Unwrap failures stay loud: 0 silent failures and 0 slip false alarms in all
  24 configs** (every failure caught by the slip and/or edge check). No new
  silent-failure mode found.
- **Sensor noise does not break the slew rule; it moves the edge.** The rule
  applied to the input the fold actually saw (noise included) predicts 280/280
  at every noise level. But the *spec-sheet* rule on the noiseless signal
  degrades: 279/280 at 40 dB, 266/280 at 10 dB, 219/280 at 0 dB SNR. Rough
  numbers: a cell sitting right at the edge (max step 4.99 V of 5) flips at
  σ ≈ 5 mV (0.1 % of λ); cells with 4.3 V steps flip at σ ≈ 90–160 mV
  (2–3 % of λ). Noise costs slew margin only — the recovered waveform equals the noisy
  input exactly (0 V fold error).
  Practical line: derate the slew spec by several σ of the front-end noise
  (noise std σ → steps can grow by ~4–6 σ over a long record).
- **Fold/ADC errors cost accuracy, not honesty.** Recovery never slips because of
  them, but the recovered peaks carry a bounded, **unflagged** error:
  - wrap-threshold error *e* and offset *o*: max error = |e|·λ, |o|·λ
    (2 % → 0.1 V; 10 % → 0.5 V),
  - INL *a*: max error = a·λ,
  - gain mismatch *g*: staircase of 2λ·g per wrap crossed, so peak error ≈ g
    of the peak (1 % → ~1–2 % of peak, 5 % → up to ~10 %; −5 % worst 2.0 V on
    a 40 V burst).
  Thresholds for ≤ 1 % of peak: g ≲ 0.5 %, e ≲ 1 %, o ≲ 1 %, INL ≲ 1 % (combo-mild
  passes everywhere; combo-bad: 40/112 recovered cells within 1 %, worst 1.9 %).
  This is the same class as ordinary ADC gain/offset/INL specs — but only on
  overloaded samples — and the current blind checks **cannot see it**
  (a wrap-count-proportional error returns to zero at baseline). It needs
  factory calibration of the fold step, not a self-flag.
- **INL nudges the slew edge** (bow slope 1+π·a at mid-scale shrinks the limit
  by ~π·a): the plain rule says "ok" for 12 cells (of 6,720 non-ideal cells) that
  actually slipped — all in the INL / combo configs, all flagged. A derated rule
  λ·(1 − 2|g| − |e| − |o| − π·a) never called a failing cell "ok" (0 of 6,720) at
  the price of being conservative (69 cells that still recovered were called "no").
- Edge warnings on recovered cells rise with noise (up to 15/114 at 15 dB) —
  nuisance warnings, not slips; slip false alarms stay 0.

### New limits to state to an OEM

1. Spec the slew limit with margin for front-end noise σ and fold errors.
2. Fold-step gain error, wrap threshold and offset must be calibrated to ≲ 0.5–1 %
   for ≤ 1 %-of-peak overload accuracy; they are not self-detectable by the
   current blind flags.
3. Still no real IEPE capture; λ = 5 V and every number above is synthetic.

## Front-end calibration — fold-step gain + INL (2026-10-12 weekday slice)

`python -m foldcrypt shockdaq-calibrate` (`foldcrypt/calibrate.py`, artifact
`artifacts/shockdaq/calibration.json`). Closes NOTES #7: the unflagged accuracy
error left by fold-step gain mismatch (and, it turns out, INL).

**Method.** Inject a known 159.2 Hz test tone at 4λ peak for 1 s (electrical
injection at the DAQ input — the accelerometer is not in the loop). Itoh-unwrap it
with the nominal 2λ step and count wraps M. With gain error g the unwrap is
exactly r = x − 2λ·g·M, so one linear least-squares fit of
r ≈ a·sin + b·cos + c − 2λ·g·M + Σ α_k·sin(kπ·y/λ) (k = 1..3; rail-clipped
samples excluded) gives ĝ and the INL bow α. Recovery then undoes INL on the
folded samples and unwraps with the calibrated step 2λ(1+ĝ).

**Estimate accuracy** (worst |ĝ − g| over g = ±0.1…5 %, ideal/16/12-bit, 3 seeds;
target ≤ 1e-3): noiseless 3e-6, 80 dB 1e-5, **60 dB 3e-4 (meets)**, 40 dB 3e-2
(misses), 20 dB 1.0 (Itoh fails). INL estimate within 0.0002·λ of truth.
The INL terms matter: without them an INL bow of 5 % leaks into ĝ as +4.7 %.

**Burst grid before → after calibration** (280 cells per row = 56 × 5 seeds; 114
is the ceiling because the other 166 cells are past the slew limit):

| config | accurate (≤ 1 % of peak) | unflagged > 1 %-off cells with **no** rail-clipped sample |
|---|---|---|
| gain −1 % | 21 → **114** | 68 → 0 |
| gain −5 % | 5 → 89 | 75 → 0 |
| gain +1 % | 27 → 63 | 5 → 0 |
| gain +5 % | 7 → 5 (no help) | 0 → 0 |
| INL 2 % | 40 → **114** | 64 → 0 |
| INL 5 % | 15 → **114** | 84 → 0 |
| combo-mild | 113 → 113 | 0 → 0 |
| combo-bad | 40 → 36 (no help) | 3 → 0 |

Still 0 silent unwrap failures and 0 slip false alarms in every row.

**What it means.**
- Negative gain error and INL are fully fixable by a one-tone factory/service
  calibration. Across all rows, 304 truly invisible > 1 %-off cells become 0.
- What calibration can't fix is samples the gain error pushed **past the ADC
  rail** — their value is clipped and gone. For g > 0 that happens right after
  every wrap, so a +5 % fold step stays inaccurate. Those cells are not silent,
  though: the capture shows rail-clipped samples (`rail_hits`), so firmware can
  mark the overloaded peaks "bounded accuracy". The rail check is conservative
  (it also fires on many cells that were accurate, e.g. 43/46 in combo-mild).
- **Design rule for an OEM:** trim the fold step slightly *short* (g ≤ 0) and
  calibrate it; never long. Wrap-threshold and offset errors (combo-bad) also
  clip at the rails and are not helped by this calibration.
- Tried and rejected: estimating g blind from the impact burst itself (≈ 4 %
  bias — the signal moves too much per sample), and interpolating over
  rail-clipped samples (made fast bursts worse).
- Still synthetic; λ = 5 V is an assumption, not an OEM part.

**Reported per capture (2026-10-13).** `shockdaq-demo` now has a `RAIL`
column (`blind_level.rail_hits`, the same rail check the sweep counts). Ideal
fold cases read `no`; `gearbox_fold_long` (same gearbox through a fold step
+1 % long, synthetic) reads 92 rail-clipped samples, `UNREC` = `no`, blind SNR
42 dB (vs 13 dB for the silent clip), peak error 0.10 V of 12.8 V. Firmware
sketch: UNREC set → "unrecoverable" (unwrap may have slipped; fall back to the
clipped value); else RAIL set → "overload peak, bounded accuracy" (unwrap held,
some peak samples clipped at the rail); else overload → "recovered".


## Noise-aware slew rule + UNREC fallback (2026-10-15 weekday slice, NOTES #8)

### A. Noise-aware slew rule

`failmap.noise_aware_slew_ok(max_dx, lam, sigma, k=NOISE_K)` /
`failmap.slew_threshold(lam, sigma, k)`:

> **recovers iff max|Δx_signal| < λ − k·σ**, with k = 5 and the margin clamped to [0, λ]

Here max|Δx_signal| is the signal's own (noiseless, spec-sheet) per-sample step
and σ is the front-end noise RMS. The plain rule applied to the noisy samples
is already exact (280/280 at every SNR). This rule is for the situation a
datasheet or test plan is actually in: you know the signal's slew and the
noise floor, not the realised noisy samples. Do not apply it to an
already-noisy max|Δx|, because that counts the noise twice.

**Fit.** The fit set is the 9 noise rows of `--nonideal` (ideal, then 60 → 0 dB
SNR) × 56 cells × seeds 7–11 = 2,520 cells. σ is taken per cell. k was scanned
from 0 to 8 in steps of 0.25 (`failmap.fit_noise_k`, which reuses the swept
cells at no extra cost). The criterion: no "rule says ok but the unwrap
slipped" cell (false-ok, the dangerous miss), at the smallest k that achieves it.

| k | agree / 2520 | false-ok | false-no |
|---|---|---|---|
| 0 (plain spec-sheet rule) | 2401 | **119** | 0 |
| 3 (max agreement) | 2481 | 12 | 27 |
| 4 | 2472 | 4 | 44 |
| 4.75 (smallest with 0 false-ok) | 2439 | 0 | 81 |
| **5 (chosen)** | **2435** | **0** | 85 |

Cross-check: fitting on seeds 7–9 alone gives k = 4, but that k still leaves 4
false-ok cells on held-out seeds 10–11. k = 4.75 is 0/0 on both halves, and 5
rounds it up for margin. The 85 conservative cells are all at SNR ≤ 30 dB
(30 dB: 1, 20 dB: 8, 15 dB: 15, 10 dB: 25, 5 dB: 13, 0 dB: 23). The ideal,
60 dB and 40 dB rows are unchanged at 280/280. Rough physics: white noise adds
a per-step term of std √2·σ, so k = 5 is about 3.5 step-σ at the steepest step.

The sweep table now has an `n-aware` column (agreement) and a `falseOK c→n`
column (false-ok count, clean rule → noise-aware rule). JSON rows gain
`noise_aware_rule_agrees`, `noise_aware_false_ok` and `clean_rule_false_ok`;
`NonIdealCell` gains `noise_aware_ok`; sweep dicts gain `noise_k`. All of these
are additive. The rule covers noise only. INL rows keep 3–4 false-ok cells
(inl 1 %: 3, 2 %: 3, 5 %: 4; combo-mild 1, combo-bad 2 → 1), the same cells the
plain rule misses. They need the derated rule λ(1 − 2|g| − |e| − |o| − π·a), and
all of them are still flagged by slip/edge (0 silent).

### B. Real-time flag logic: `shockdaq.recover_or_clip`

`recover_or_clip(y_folded, lam)` turns the firmware status sketch into code:
blind recover → slip/edge/rail checks → a `CaptureOutput` with `signal`,
`status` (UNRECOVERABLE / BOUNDED_ACCURACY / RECOVERED / IN_RANGE), `fallback`,
an `untrusted` sample mask, and `peak_V` plus `peak_is_lower_bound`.

- **UNRECOVERABLE (slip or edge):** the unwrap is **discarded**. Output = the raw
  folded ADC samples. They equal the true input wherever |x| < λ, and are
  bounded in [−λ, λ) inside the event. `overload_event_mask` marks the event
  untrusted and the peak is reported as **≥ λ**. That is the honest content of a
  clipped capture with an overload flag. On `impact_too_fast` it emits 3,385
  untrusted samples (4.4 %), with SNR −0.1 dB vs the original instead of the
  slipped unwrap's −29.7 dB and its 300 V phantom peak.
- Rejected: clipping the unwrap at ±λ. After a slip its baseline sits 2λ off,
  so the clipped tail parks at the rail. On seven failing captures it scored
  −11 to −16 dB SNR vs a true hard clip, against −0.9 to +1.9 dB for the folded
  samples.
- `overload_event_mask` (wraps or wrapped steps ≥ 0.5λ, merged within 1,024
  samples, ±32 padding) covered every |x| ≥ λ sample in 168 burst cells
  (56 × seeds 7–9) and the 3 demo signals. Median masked fraction 4 %, gearbox
  8.6 %. Blind spot: isolated single-sample impulses (the `harsh_kick` class),
  as for slip/edge.
- BOUNDED_ACCURACY: recovered waveform, rail-clipped samples marked untrusted.
  RECOVERED / IN_RANGE is decided blind (did the unwrap apply any wrap?).
- `shockdaq-demo` prints a `firmware out` line and writes `fw_status`,
  `fw_fallback`, `fw_untrusted_samples` and `snr_fw_db` to `metrics.json`. The
  demo fails if `fw_status` disagrees with `capture_status` (it agrees on all 4
  cases).

Synthetic only; λ = 5 V is still an assumption, not an OEM part.
