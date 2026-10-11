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
