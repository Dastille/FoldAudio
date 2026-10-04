# FoldCrypt bigger-problem scout

Date: 2026-10-02 (ET)  
Owner: FoldCrypt bot  
Bar: **bigger than FoldAudio** — more people hurt when it fails, clearer world-facing fix, not researcher-only.  
FoldAudio stays owned elsewhere (publish/CLI). This memo only answers: *what should FoldCrypt own next that is larger?*

**Hard exclusions (do not pitch):** Sigil `.sg1` / constellation, Regenamatron file regen, ChaosLog stocks, ID-bot SSI, thin Shamir-style recovery shares, plain AES vaults, RS repair clones.

**Method:** WebSearch + WebFetch of engineering / reliability sources (NERC PMU quality, bridge SHM saturation, IEPE soft-clip, wearable ECG clipping, Unlimited Sensing hardware) plus FoldCrypt DNA already in-tree (intentional fold, WrapCancel, defect-mask metaphor). Cold War flavor kept where it still maps to a mass harm (Boak fill / TEMPEST / burst cover scored below as NO/MID for this bar).

---

## Why FoldAudio is not big enough (for this bar)

FoldAudio fixes **ruined recordings** (music, podcasts, field takes). Real pain, real demo — but the failure mode is usually “redo the take” or “live with a bad file.” A bigger FoldCrypt problem should fail into **wrong safety calls, wrong medical therapy, or grid/forensic blindness** for lots of people who never chose to record music.

---

## Top 3 bigger problems

### 1) QuakePeak — fold vibration so bridges/buildings keep the shock peak — **BIG**

**Problem (plain):** Cheap vibration sensors on bridges and buildings are tuned for quiet everyday motion. When an earthquake, crash, or heavy shock hits, they **clip or soft-saturate**. The biggest peak — the thing that says “how hard did it hit?” — is flattened or distorted. After the event, engineers and cities may mis-read whether the structure is safe.

**Who hurts:** People who live/drive under instrumented bridges and mid/high-rises in seismic and heavy-traffic zones. Wrong after-event calls delay closures or reopenings; missing peaks also corrupt damage models for the next quake.

**Why bigger than FoldAudio:** Life-safety and public infrastructure, not a spoiled take. One bad sensor chain can affect thousands of users of one bridge.

**FoldCrypt DNA:** Same story as FoldAudio — **intentional fold instead of clip** at the ADC, then WrapCancel / never-unfold recover so ambient *and* shock share one sensor. Defect-mask optional as a tamper/integrity tag on the event archive.

**Evidence (real sources):**
- Bridge SHM shaking-table work: sensors optimized for ambient vibration **easily saturate** in earthquake-level motion; that can corrupt post-event modal estimates if the chain is not resilient. Lab validation paper (Liverpool / SHM 2018 lineage): https://livrepository.liverpool.ac.uk/3051506/1/SHM_2018.pdf
- Related: after strong shaking, saturation + settling time can make automated damage detection unreliable during seismic sequences (same research line; see also DOI-linked follow-ons on Imote2-class wireless loss).
- IEPE/ICP “soft clipping”: internal amp saturates (~±5 V) **without** a DAQ overload flag if the system accepts ±10 V — peaks look wrong, especially negative, and recovery takes seconds. PCB white paper: https://www.pcb.com/contentstore/MktgContent/whitepapers/WPL_96_Signal_Processing_Impacts.pdf · Hambric NC24 tutorial: https://hambricacoustics.com/NC24_Hambric_paper_final.pdf
- Missing/corrupt peaks in earthquake building response already force reconstruction methods (FaLRTC / low-rank completion) because wireless SHM loses data when it matters most: https://mdpi-res.com/d_attachment/sensors/sensors-21-07327/article_deploy/sensors-21-07327-v4.pdf?version=1636421071
- Hardware bridge: modulo / Unlimited Sensing ADC prototypes expand usable range without raising bit budget (e.g. FPGA-calibrated modulo ADC; wideband HDR ADC arXiv:2301.09609) — https://ar5iv.labs.arxiv.org/html/2301.09609

**Smallest test (no code in this scout — next weekday if chosen):**
1. Take a public bridge/building acceleration WAV or synthetic bandlimited shock train.
2. Hard-clip vs soft-fold at the same “ambient” full-scale.
3. Recover fold with existing WrapCancel / difference unwrap; score peak error + post-event modal error vs clip.
4. Gate: fold recovers peak within a stated % where clip permanently loses it on ≥3 event shapes (quake pulse, truck impact, blast-like transient).

**Risks:** Selling into civil infrastructure is slow; many SHM vendors already upsell dual-range sensors. Differentiator must be **one cheap sensor + fold firmware**, not another $ rack. Soft freeze: sim/replay first, no Parrot-only vanity grids.

**Score:** **BIG** for harm + DNA fit. Go-to-market is MID until a partner (city/DOT lab, SHM vendor) exists.

---

### 2) GridFold — keep fault peaks on the power grid so blackouts don’t go blind — **BIG**

**Problem (plain):** The modern grid watches itself with PMUs (phasor measurement units) — fast voltage/current “snapshots.” During a real fault or big swing, signals can exceed the front-end range. If the ADC **clips**, the record of what actually happened is wrong or flagged unusable. Operators and automated tools then see a hole exactly when they need the truth. Bad data quality can delay instability detection and erode trust in synchrophasor apps — which NERC ties to bulk-power reliability for ~400 million people in North America.

**Who hurts:** Everyone on a bulk grid when a disturbance is mis-measured — homes, hospitals, industry. Not a hobby niche.

**Why bigger than FoldAudio:** Grid-scale reliability vs one session of audio. Failure mode is regional darkness / bad protection decisions, not a bad podcast.

**FoldCrypt DNA:** Fold the analog waveform (or a high-rate sample stream) so extreme swings wrap instead of saturate; recover with WrapCancel-class detectors for event forensics and RoCoF/frequency derivatives that hate clipped edges. Same “overflow beats clipping” thesis as USF, aimed at substations not studios.

**Evidence:**
- NERC (draft) *PMU Data Quality and System Maintenance Manual* (April 30, 2026): synchrophasor value depends entirely on data quality; poor quality can delay detection of instability, mislead controls, and compromise grid reliability. ~400M citizens cited in ERO framing. https://www.nerc.com/globalassets/who-we-are/standing-committees/rstc/0-rstc-agenda-links/8a-pmu-data-quality-manual_final-draft_march-10-2026.pdf
- PMUs digitize via A/D with input scaling “to keep the signal within range” — classic clip boundary under fault currents/voltages (same manual, measurement-chain chapters).
- Unlimited / modulo ADC literature for high dynamic range without throwing away LSB resolution: Bhandari et al. *Unlimited Dynamic Range Analog-to-Digital Conversion* arXiv:1911.09371 — https://ar5iv.labs.arxiv.org/html/1911.09371
- PSERC / DOE-era synchrophasor quality reports document accuracy + availability failures that break oscillation detection and model validation (e.g. PSERC S-71 real-time data quality work).

**Smallest test:**
1. Replay a public fault/oscillation waveform (or IEEE test case) through clip vs fold at tight full-scale.
2. Compare recovered magnitude/phase/RoCoF error and “would STATUS have marked invalid?”
3. Gate: fold keeps usable phasor/RoCoF through an event that clip marks dead or biases by >1% (IEC/IEEE 60255-118-1 ballpark accuracy target from NERC manual).

**Risks:** Utility procurement, IEEE C37.118 / 2664 integration, liability. FoldCrypt should aim at **offline forensic + PDC add-on prototype**, not “replace every PMU tomorrow.” Hardware partner required for a real product; software-only still proves the claim.

**Score:** **BIG** impact. **MID** near-term ship shape (regulated buyers). Worth owning as the “infrastructure FoldAudio.”

---

### 3) HeartFold — stop ambulatory ECG peaks from disappearing (wrong shocks / blind monitors) — **BIG harm / MID ship**

**Problem (plain):** Wearable and implantable heart monitors must watch a wide range of signal sizes. If the waveform **clips**, morphology changes. Devices can then treat a safe rhythm as dangerous (inappropriate shock) or miss what they should see. Clipping is often from gain too high, motion, or electrode issues — and once clipped, filtering cannot invent the lost peak.

**Who hurts:** People with ICDs, wearable defibrillators, and continuous ECG patches — millions globally in the cardiac-device / ambulatory-monitor population. Wrong therapy is direct bodily harm.

**Why bigger than FoldAudio:** Medical injury vs ruined audio. Same fold idea, higher stakes.

**FoldCrypt DNA:** Folding front-end (or soft-fold before quantize in the wearable SoC) so large QRS / paced spikes wrap instead of flatline; recover before morphology matching. Optional defect-mask as a signed “this sample was reconstructed” flag for clinicians (integrity, not encryption theater).

**Evidence:**
- Clinical electrophysiology texts note clipped electrograms can make SVT fail a morphology template and get classified as VT → inappropriate ICD therapy; fix classically is reduce gain so signals stay in range — https://doctorlib.org/medical/color-atlas-synopsis-electrophysiology/68.html
- Patent art on **detecting** signal clipping in wearable ambulatory medical devices (recognition that clip must be flagged, not trusted): https://www.patents-review.com/a/20160051186-method-detecting-signal-clipping-wearable-ambulatory-device.html
- Right-leg-drive / low-voltage ECG monitor saturation as a known artifact class (PubMed 25181288).
- HDR ultrasound (related medical dynamic-range lesson): multi-exposure / extended range improves diagnosis when single range clips hyperechoic tissue — Degirmenci, Perrin, Howe, IJCARS 2018 — https://link.springer.com/article/10.1007/s11548-018-1729-3

**Smallest test:**
1. Public MIT-BIH or similar ECG strip; amplify until clip vs fold.
2. Run a dumb morphology / peak detector on clip vs recovered fold.
3. Gate: fold preserves R-peak amplitude/timing where clip causes false “flat” or template mismatch on ≥3 arrhythmia morphologies.

**Risks:** FDA/Health Canada path is the mountain. FoldCrypt alone will not ship a Class II/III device. Realistic product is **algorithm IP + OEM SDK** for a wearable vendor, or a research/forensic ECG tool first. Score stays **MID** for “we can ship soon,” **BIG** for “problem size if we get a partner.”

---

## Ranking for Ashlynn’s bar

| # | Name | Harm if unsolved | Unique vs roster | DNA fit | Near-term toy | Overall |
|---|------|------------------|------------------|---------|---------------|---------|
| 1 | QuakePeak (bridge/building fold) | City-scale safety | Yes | Strong | Strong (reuse WrapCancel) | **BIG — recommended default** |
| 2 | GridFold (PMU fault fold) | Regional blackouts | Yes | Strong | Medium (need grid traces) | **BIG impact / MID GTM** |
| 3 | HeartFold (ECG fold) | Wrong shocks / blind monitors | Yes | Strong | Medium (public ECG DBs) | **BIG harm / MID ship** |

**Recommendation:** Treat **QuakePeak** as the FoldCrypt product thesis after FoldAudio. It reuses the audio demo’s proof pattern (clip vs fold A/B), aims at a harm class Ashlynn’s bar cares about, and does not collide with Sigil/Regen/ChaosLog. Keep GridFold as the “if we get a utility intro” lane; HeartFold only with an OEM/clinical partner ask.

---

## Explicit NOs (kill list for this scout)

| Idea | Score | Why dead for “bigger than FoldAudio + unique” |
|------|-------|-----------------------------------------------|
| Recovery shares / Shamir-thin seed split | **NO** | Already overlaps Sigil constellation; Ashlynn rejected as non-unique |
| Radio-only WrapCancel SDK | **NO** | Researcher niche; fails world-facing bar |
| Boak constant-rate chat fill as mass app | **NO→MID niche** | Real Cold War COMSEC (Boak 1973); bandwidth/UX kills mass; Tor/mixnets own high-risk users |
| Ambient Burst / “secrets as sensor junk” | **NO** | Ethics + dual-use + tiny market; not “many people hurt” |
| Consumer TEMPEST / emission masking | **NO** | Cold War classic; not a safe mass product; dual-use |
| AV sun-glare “fold” | **NO** | Glare is mostly **optics**, not ADC fold; Tesla/Mobileye-scale buyers; FoldCrypt has no unique wedge |
| Post-hoc magic declip of already-clipped files | **NO** | Same lie FoldAudio already refused — can’t restore what was never kept |
| DNA archival defect codec as *immediate* consumer product | **NO→watch** | True FoldCrypt biology origin (Jiang / Wisna origami); StairLoop etc. advancing (Nature Comms 2025), but cost still ~orders of magnitude from tape — researcher/enterprise archive, not “people hurt today” |
| Hearing-aid FoldAudio clone | **NO as separate project** | Same product as FoldAudio with OEM path; EHIMA ~23M aids sold/year (2025) is big, but it is not a *new* bigger problem — it’s FoldAudio’s best vertical |
| SettleSeal / FoldOrbit product push | **NO** | Already parked (no clear win over ordinary hash / CollisionHull) |

---

## What this is not asking for (this turn)

- No new code  
- No GitHub  
- No FoldAudio publish changes (other agent owns that)  
- No Mathamatico ping unless Ashlynn picks QuakePeak/GridFold and wants a discrete math specialty piece later  

---

## If Ashlynn picks one

**QuakePeak next weekday slice (suggested):** public SHM/accel clip-vs-fold A/B using existing `/workspace/foldcrypt` recover path; one-page plain README “why bridges clip”; stop if peak recovery doesn’t beat clip on real-ish traces.

**GridFold only after:** one public fault waveform + written note on C37.118 STATUS interaction (when would fold still set invalid?).

**HeartFold only after:** explicit “talk to a device partner / stay research-only” decision — do not imply a medical product without that.
