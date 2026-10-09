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
