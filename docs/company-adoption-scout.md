# FoldCrypt company-adoption scout

Date: 2026-10-02 (ET)  
Owner: FoldCrypt  
Bar: **a company would fight to license this** — clipping already costs money, liability, or failed acceptance; named buyer who ships ADCs/recorders.

FoldAudio stays public proof ([Dastille/FoldAudio](https://github.com/Dastille/FoldAudio)). This memo answers: who pays, and would they really want it?

Hard exclusions: Sigil, Regen, ChaosLog, thin recovery shares, FDA-first medical as solo ship.

---

## Honest gate

Companies do **not** fight for “cool fold math.” They fight when:

1. Clipping / soft-sat already fails a paid acceptance test, a warranty claim, or a regulator audit, **and**
2. Today’s fix is expensive (second sensor channel, higher-g part, re-test campaign), **and**
3. FoldCrypt ships as **SDK / firmware / silicon IP** inside gear they already sell — not a solo GitHub CLI.

If the industry already priced the pain away with dual-range sensors or huge full-scale ranges, adoption is **MID→NO** unless we undercut that cost.

---

## Top 3 company bets

### 1) ShockDAQ — fold inside vibration/DAQ front-ends — **BIG (recommended)**

**Problem:** IEPE/ICP accelerometers soft-clip (~±5 V) without a DAQ overload flag when systems accept ±10 V. Startup shocks and impacts flat-top; RMS/spectral acceptance then understates the real transient. Labs re-run expensive endurance tests or ship bad “pass” data.

**Who pays:** DAQ / vibration-test OEMs and SHM recorder vendors (think NI/cDAQ-class, Siemens LMS-class, PCB/Brüel & Kjær front-ends, industrial predictive-maintenance gateways) — they sell the box; end customers (auto/aerospace/gearbox OEMs) feel the re-test cost.

**Why they’d want it badly:** Silent soft-clip is a known reliability landmine; dual-gain or re-ranging is the incumbent fix. One firmware path that **folds instead of saturates** and unfolds offline is cheaper than a second channel on every node and sells as a product feature (“HDR vibration capture”).

**Evidence:**
- IEPE soft-clip / no-flag saturation: https://exa.ai/library/publication/v9tmvl9x9rg
- Gearbox endurance case study — clipped startup corrupted acceptance: https://atlasofengineering.com/engineering-physics/piezoelectric-accelerometer-charge-amplifier-saturation-case-study/
- Seismic/SHM: conventional sensors clip on large nearby events; vendors already ship dual MEMS “XGM” as the paid fix: https://www.imseismology.org/sensors/

**Wedge:** Firmware/SDK for the digitizer (fold + recover + overload-honest flags), demo on synthetic + public vibration WAVs; later silicon IP for IEPE AFE makers.

**Blockers:** Need one OEM design win; prove peak recovery beats dual-range on cost for mid-tier nodes.

**Score:** **BIG** for “company fights” — money is re-tests and feature differentiation, buyer is reachable via SDK, DNA matches FoldAudio.

---

### 2) MineMotion / strong-motion single-channel OEM — **BIG impact / MID GTM**

**Problem:** Mine and strong-motion networks must hear tiny events *and* survive large nearby blasts/quakes. Geophones/IEPE clip; ADC sat adds more distortion. Big events are exactly the ones you need for hazard work — and they get ruined.

**Who pays:** Seismic OEM / mining monitoring vendors competing with IMS-style dual-sensor packages; mine operators who buy monitoring contracts.

**Why they’d want it:** Dual MEMS is the paid incumbent answer. A **single cheap sensor + fold** that recovers strong-motion peaks undercuts dual-channel BOM and wins mid-tier RFPs.

**Evidence:** IMS documents clip/sat as “serious problem” and sells XGM dual MEMS as the solution: https://www.imseismology.org/sensors/ · clipped seismic restoration literature: https://www.nature.com/articles/srep39056 · multi-ADC range extension: http://www.geophy.cn/en/article/doi/10.6038/cjg20160424

**Wedge:** Offline recover demo → firmware reference for mid-tier seismic recorders.

**Blockers:** Incumbents already sell dual-range; must beat on cost/simplicity with hard peak-error numbers.

**Score:** **BIG** pain, **MID** until cost story beats XGM.

---

### 3) GridForensics fold plugin for DFR/PMU vendors — **MID→BIG (slow)**

**Problem:** Faults and swings can drive DFRs/PMUs into ADC rails or CT saturation; the forensic waveform is wrong exactly when operators need it. NERC ties synchrophasor value to data quality for bulk-grid reliability.

**Who pays:** Relay/DFR OEMs (SEL/GE/ABB-class) and chip vendors selling DFR AFEs (e.g. TI DFR reference designs), not Ashlynn selling to a utility alone.

**Why they’d want it:** Feature differentiation + fewer “unusable event” tickets. Utilities adopt only through those OEMs.

**Evidence:** IEEE PES DFR phenomena report: https://www.pes-psrc.org/kb/report/050.pdf · TI DFR AFE: https://www.ti.com/lit/ug/tiduat7a/tiduat7a.pdf · CT sat compensation (incumbent software path): many IEEE papers — fold must beat or complement CT algorithms, not ignore them.

**Wedge:** Offline forensic recover on public fault traces → license as PDC/DFR analysis plugin; later AFE IP.

**Blockers:** Regulated buyers, long sales cycles, CT saturation ≠ ADC fold (different physics) — don’t overclaim.

**Score:** **BIG** if inside an OEM; **NO** as a solo utility SaaS.

---

## Explicit NO / weak for “company fights”

| Idea | Why NO for this bar |
|------|---------------------|
| FoldAudio consumer alone | Nice proof; redo-the-take; no OEM fighting unless inside phone/SoC audio |
| HeartFold solo | Real harm; FDA/OEM implant path — not a solo first customer |
| WrapCancel radio hobby | Niche research; no mass buyer |
| Auto airbag fold | OEMs already ship ±50–500 g ranges (NXP NXLS95 etc.); problem sized away in silicon |
| Recovery shares / Sigil-overlap | Ashlynn parked — not unique |

---

## Recommended single bet

**ShockDAQ (IEPE/DAQ fold firmware)** — same math as FoldAudio, but the buyer is a company that already sells vibration boxes and already loses money/reputation when soft-clip silently corrupts acceptance tests. Pitch: *HDR vibration without a second channel.*

First demo (weekday-slice sized): hard-clip vs fold on gearbox-style startup + impact synthetics; report peak error, spectral bias, and “would overload have flagged?”; one-pager aimed at a DAQ OEM, not consumers.

FoldAudio stays the public math receipt. QuakePeak/MineMotion is the vertical story once ShockDAQ numbers exist; GridFold only with an OEM partner.
