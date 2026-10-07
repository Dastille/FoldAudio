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

Synthetic ringing burst only (not field data); no quantization; λ = 5 V is a
demo rail, not a specific OEM part; 60 dB SNR threshold for "recovered".
Next proof still needed: one real IEPE capture (NOTES #3).
