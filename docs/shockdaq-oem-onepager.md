# ShockDAQ — OEM one-pager (v0)

**Date:** 2026-10-04 (ET); refreshed 2026-10-11 (ET) with fail-map, quantization and non-ideal numbers  
**Ask:** design-win conversation with a vibration / DAQ OEM  
**Public proof:** [Dastille/FoldAudio](https://github.com/Dastille/FoldAudio) (FoldAudio math)  
**Company scout:** [`company-adoption-scout.md`](company-adoption-scout.md)

---

## Problem (plain language)

IEPE / ICP accelerometer front-ends often **soft-clip near ±5 V** while the rest of the system still expects a wider rail (sometimes ±10 V). The clip is **silent**: no overload flag, flat-topped peaks, acceptance software still says “pass.”

Startup shocks and impact transients are exactly the events that matter for endurance / gearbox / SHM acceptance — and those are the peaks that get destroyed. Labs re-run expensive tests or ship bad data. Dual-gain / second-channel is the expensive incumbent fix.

## Who pays

**DAQ and vibration-test OEMs** (and SHM recorder vendors) who sell the digitizer box. End customers (auto / aerospace / gearbox OEMs) feel re-test cost; the OEM sells the feature.

See [`company-adoption-scout.md`](company-adoption-scout.md) — ShockDAQ scored **BIG** (recommended company bet).

## Wedge

**HDR vibration capture without a second channel:** fold at the soft-sat rail instead of saturating; unwrap offline (or in firmware) so true peaks come back; emit an honest overload-style flag when |x| > λ.

Ship path: SDK / firmware reference for the digitizer → later silicon IP for IEPE AFE makers. Not a solo GitHub CLI sold to plant engineers.

## v0 demo numbers (synthetic, real run 2026-10-04)

Assumptions (named): λ = **5.0 V** models a ±5 V soft-sat rail (**not** a claim about a specific OEM chip). Soft-sat without flag ≡ hard clip for v0 math. Generators are numpy synthetics (gearbox chirp + impact ringing), sr = **51200**. Recovery uses Itoh unwrap; the absolute level now comes from a blind AC-coupling prior (IEPE signals are zero-mean), and it matches the oracle exactly on every synthetic case. Spectral bias is a simple HF-band RMS indicator — **not** an ISO vibration metric.

| Case | Peak (V) | Peak err clip | Peak err fold | SNR clip | SNR fold | Gain | Overload would flag | Itoh OK |
|------|----------|---------------|---------------|----------|----------|------|---------------------|---------|
| gearbox_startup | 12.82 | **7.82 V** | **~0** | 13.35 dB | ~∞ (120) | **+106.7 dB** | yes | yes |
| impact_transient | 8.27 | **3.27 V** | **~0** | 19.35 dB | ~∞ (120) | **+100.6 dB** | yes | yes |
| impact_too_fast *(deliberately past slew limit)* | 53.47 | 48.47 V | 303 V | 2.22 dB | −31.3 dB | −33.5 dB | yes | **NO** — self-flagged `SLIP+EDGE` |

Source: `artifacts/shockdaq/metrics.json` from `python -m foldcrypt shockdaq-demo`.

**Read for an OEM:** silent soft-clip lost multi-volt peaks; fold recovered them with negligible peak error and >100 dB SNR gain vs clip on these synthetic cases. The missing overload flag would have been **true** on both records.

## Where fold breaks and whether it tells you (synthetic, refreshed 2026-10-11)

All numbers below are **synthetic** ringing-impact bursts (peak 6–40 V, ring 0.5–12 kHz, sr 51.2 kHz, λ = 5 V *assumed*, blind recovery with no original). **No real IEPE capture yet.** Detail: [`shockdaq-failmap.md`](shockdaq-failmap.md).

| Question | Result (synthetic) |
|---|---|
| Spec line for the limit | **max slew < λ × sample rate** (5 V, 51.2 kHz → 256,000 V/s; pure sine: peak V × Hz < ~40,700). Predicted 280/280 cells (56 cells × 5 seeds). Doubling sr doubles the allowed slew. |
| When it fails, is it silent? | **No: 166/166 failures self-flagged** (slip + edge checks, capture-only, no original), 0 silent, 0 slip false alarms. |
| ADC resolution 4–24 bit | **Does not move the slew edge**; same cells fail at every depth, 0 silent. Costs one LSB of resolution, not range. |
| Sensor noise (SNR 60→0 dB vs burst RMS) | Rule on the noisy input still 280/280; **0 silent**. Noise eats slew margin: a noiseless-spec rule drops to 266/280 at 10 dB and 219/280 at 0 dB SNR. Derate the slew spec by several σ of front-end noise. |
| Fold/ADC non-idealities (wrap gain mismatch, threshold error, offset, INL; 24 configs × 280 cells) | **0 silent unwrap failures, 0 slip false alarms.** But these cost **unflagged accuracy on overloaded peaks**: error ≈ g of peak for gain mismatch g; e·λ, o·λ, a·λ for threshold / offset / INL. ≤ 1 % of peak needs each ≲ 0.5–1 % (calibration). |
| One-tone calibration (2026-10-12): 159.2 Hz test tone, 1 s, ≥ 60 dB | Estimates fold-step gain to ±0.0003 and INL bow. After it, gain −1 %, INL 2 % and INL 5 % are accurate in every recoverable cell (114/114); **0 invisible > 1 % errors in any config** (was 304). Remaining error only where the fold step pushed samples past the ADC rail — visible in the capture. Design rule: trim the fold step short (g ≤ 0), never long. |

**Honest read:** fold is exact inside its slew limit, loud outside it, and ADC bit depth and sensor noise do not break that honesty. The one thing the self-checks cannot see is a slightly mis-calibrated fold step (small, bounded peak error) — and a one-tone factory calibration now removes it (synthetic), leaving only rail-clipped samples that the capture itself shows.

## Honest limits

- **Measured records, software overload (2026-10-14).** On 13 public CWRU bearing-fault accelerometer records, with the rail set below the record peak in software, the slew rule predicted 120/120 cells and every failure was flagged (0 silent). Fold gave 7.5–9.8 dB of extra range at 48 kHz and **none at 12 kHz** (impacts step by more than their peak per sample). Clipping at half the peak cut kurtosis 20.8 → 15.9 on the worst outer-race record; fold kept it exact. Detail: [`shockdaq-realdata.md`](shockdaq-realdata.md). Still no overload captured on real folding hardware or a named DAQ card.
- **Blind level prior (2026-10-06)** — no original needed. Uses IEPE AC coupling (zero-mean / quietest-window baseline). Fixes captures that start mid-overload (naive k=0 gives −14 to −24 dB; blind gives ~120 dB). Fails honestly if the signal is DC-shifted by ≳ λ (not AC-coupled).
- **Past the slew limit fold is WORSE than clip** (impact_too_fast: −31 dB vs +2 dB), but it is never silent: the demo's `UNREC` column (blind slip/edge self-check, 2026-10-08) flags it. Firmware rule: when UNREC is set, report overload and fall back to the clipped value.
- **RAIL ≠ UNREC (2026-10-13).** If the fold step is mis-trimmed long (or threshold/offset errors), some folded samples clip at the ADC rail. The capture shows it: the demo's `RAIL` column counts them (synthetic +1 % long step: 92 samples, unwrap still fine, peak error 0.10 V of 12.8 V). Firmware tags those overload peaks **"bounded accuracy"** instead of "recovered" — still not silent.
- **Itoh slew limit** — consecutive samples must usually jump by less than λ; pathological single-sample glitches fail (same class as FoldAudio `harsh_kick`).
- **Spectral bias** is a toy HF RMS ratio, not order tracking / ISO 10816 acceptance math.
- FoldAudio remains the **public math proof**; ShockDAQ is the **company licensing bet**.

## Next ask

1. One design-win conversation: vibration/DAQ OEM firmware or AFE lead.
2. Slices: ~~fail cases~~, ~~absolute-level prior~~, ~~quantization~~, ~~noise + non-ideal ADC~~, ~~fold-step calibration~~ (done); one real WAV / IEPE capture if supplied.
3. Cost story vs dual-range / dual-gain on mid-tier nodes.

**Contact path:** Ashlynn via the FoldAudio repo maintainers (`Dastille`).
