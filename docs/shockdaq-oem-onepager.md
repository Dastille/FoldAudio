# ShockDAQ — OEM one-pager (v0)

**Date:** 2026-10-04 (ET)  
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

Assumptions (named): λ = **5.0 V** models a ±5 V soft-sat rail (**not** a claim about a specific OEM chip). Soft-sat without flag ≡ hard clip for v0 math. Generators are numpy synthetics (gearbox chirp + impact ringing), sr = **51200**. Recovery uses Itoh unwrap + demo oracle offset vs original. Spectral bias is a simple HF-band RMS indicator — **not** an ISO vibration metric.

| Case | Peak (V) | Peak err clip | Peak err fold | SNR clip | SNR fold | Gain | Overload would flag | Itoh OK |
|------|----------|---------------|---------------|----------|----------|------|---------------------|---------|
| gearbox_startup | 12.82 | **7.82 V** | **~0** | 13.35 dB | ~∞ (120) | **+106.7 dB** | yes | yes |
| impact_transient | 8.27 | **3.27 V** | **~0** | 19.35 dB | ~∞ (120) | **+100.6 dB** | yes | yes |

Source: `artifacts/shockdaq/metrics.json` from `python -m foldcrypt shockdaq-demo`.

**Read for an OEM:** silent soft-clip lost multi-volt peaks; fold recovered them with negligible peak error and >100 dB SNR gain vs clip on these synthetic cases. The missing overload flag would have been **true** on both records.

## Honest limits

- **Synthetic only** — not yet proven on a real IEPE capture or named DAQ card.
- **Demo oracle** — absolute level uses the original waveform; live firmware needs a quiet-segment / known-bias prior.
- **Itoh slew limit** — consecutive samples must usually jump by less than λ; pathological single-sample glitches fail (same class as FoldAudio `harsh_kick`).
- **Spectral bias** is a toy HF RMS ratio, not order tracking / ISO 10816 acceptance math.
- FoldAudio remains the **public math proof**; ShockDAQ is the **company licensing bet**.

## Next ask

1. One design-win conversation: vibration/DAQ OEM firmware or AFE lead.
2. Weekday slices: listen/plot fail cases; absolute-level prior without original; one real WAV / IEPE capture if supplied.
3. Cost story vs dual-range / dual-gain on mid-tier nodes.

**Contact path:** Ashlynn via the FoldAudio repo maintainers (`Dastille`).
