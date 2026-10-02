# FoldCrypt Cold War pivot scout

Date: 2026-10-02 (ET)  
Bar: unique + solves a real problem for more than radio researchers.  
Not allowed to duplicate: Sigil constellation, Regenamatron file regen, ChaosLog, thin Shamir-style recovery shares, plain AES vaults, RS repair.

## Method

WebSearch + WebFetch of declassified / classic sources (NSA Boak COMSEC lectures 1973, SIGSALY WWII brochure, Filby traffic-analysis collection, Baran RAND RM-3765 1964, DTIC FH jamming 1978) plus modern bridges that reuse FoldCrypt’s existing fold/WrapCancel / defect-mask thinking (Guo–Bhandari USF-Audio / Unlimited Sampling; CoSI-Fold lineage already in FoldCrypt NOTES).

---

## Top 3 product-shaped pitches

### 1) FoldAudio — “Never clip by folding” — **BIG**

**Problem (plain):** Loud peaks on a phone, podcast mic, bodycam, or field recorder get **clipped**. Once the ADC saturates, those peaks are gone forever. Software “declippers” guess; they don’t restore what was erased. People ruin interviews, concerts, evidence audio, and voice notes every day.

**Who hurts without it:** Journalists, podcasters, indie filmmakers, security/bodycam users, anyone who can’t babysit gain knobs.

**Cold War / classic cites:**
- NSA Center for Cryptologic History, *The Start of the Digital Revolution: SIGSALY* (Boone & Peterson; WWII secure digital voice) — first practical quantized / companded speech, bounded levels, key-synchronized recovery. PDF: https://www.nsa.gov/portals/75/documents/about/cryptologic-heritage/historical-figures-publications/publications/wwii/sigsaly.pdf (mirror: https://media.defense.gov/2021/Jul/13/2002761542/-1/-1/0/SIGSALY.PDF)
- Bell Labs patents declassified 1976 (e.g. US 3,967,066 / 3,967,067 “Secret Telephony”) — speech → discrete levels → combine with key → reconstruct. Historical ancestor of “encode into a bounded domain, recover later.”

**Modern bridge (fold math we already own):**
- Guo & Bhandari, *Digital Audio via Unlimited Sensing: Overflow Overcomes Clipping and Overflow*, EUSIPCO 2026 — https://eurasip.org/Proceedings/Eusipco/Eusipco2026/pdfs/0000411.pdf — intentional modulo fold instead of clip; hardware-validated; beats post-hoc declipping by a large margin. Explicitly funded under **CoSI-Fold** (same FoldAsync family Mathamatico flagged).
- Zaxcom “NeverClip” exists but is **dual conventional ADC** pro hardware — not modulo fold, not a phone/consumer software path: https://zaxcom.com/learn/what-is-neverclip/

**Why unique vs Sigil / Regen:** Sigil locks files at rest; Regen repairs known erasure patterns in files. Neither changes how sound is *captured*. FoldAudio is an acquisition product.

**How FoldCrypt math helps:** WrapCancel / Block-Mahalanobis / never-unfold residual thinking is the same family as USF fold recovery. Soft-freeze research (WrapCancel SER, block search) becomes the core of a decoder; defect-mask stays optional integrity tag on recovered takes.

**Smallest v0 toy (no new hardware yet):**
1. Take a clean WAV → digitally fold peaks (simulate modulo) → recover with difference / block search → A/B score vs hard-clipped + vs a public declipper.
2. Optional second demo: strip MSBs from a 16-bit WAV (wrap-around overflow) and recover them (USF-Audio Experiment 1 style).
3. Success gate: clear audible + measurable win on ≥3 clipped field recordings Ashlynn cares about (interview, outdoor voice, music transient).

**Risks:** Full “fold in the analog mic path” needs hardware partners later. Software-first still ships value (recover overflowed files; DSP soft-fold before quantize where the stack allows; offline lab → plugin).

---

### 2) Boak Fill — constant-rate cover pipe for messengers — **MID** (clear niche, not mass)

**Problem (plain):** Even when chat content is encrypted, **when you talk and how much** still leaks. Bosses, ISPs, and governments do traffic analysis. “Nothing to hide” content crypto doesn’t hide activity.

**Who hurts without it:** Journalists, activists, high-risk professionals, anyone whose *schedule* of messaging is sensitive.

**Cold War / classic cites:**
- David G. Boak, *A History of U.S. Communications Security* (NSA lectures, 1973) — **traffic-flow security** via continuous one-time-tape fill: the link always sends random characters so real messages don’t create start/stop patterns. PDFs: https://governmentattic.org/18docs/Hist_US_COMSEC_Boak_NSA_1973u.pdf · https://navy-radio.com/crypto/Python-Boak_NSA_1973u-2.pdf
- Vera R. Filby (ed.), *A Collection of Writings on Traffic Analysis*, NSA Center for Cryptologic History, 1993 — https://www.governmentattic.org/8docs/NSA-TrafficAnalysisMonograph_1993.pdf
- Paul Baran, *On Distributed Communications: IX. Security, Secrecy, and Tamper-Free Considerations*, RAND RM-3765-PR, 1964 — design assuming spies *inside* the network; raise the price of espied info. https://www.rand.org/pubs/research_memoranda/RM3765.html

**Why unique vs Sigil / Regen:** Sigil doesn’t mask live messaging metadata. Regen doesn’t. This is about **timing/volume cover**, not file encryption or repair.

**How FoldCrypt math helps (optional spice, not required):** Real messages as sparse “defects” injected into a continuous random fill stream (defect-mask metaphor). Core product is Boak-style constant-rate pipe; fold math is branding/bridge, not the only engine.

**Smallest v0 toy:**
- Local two-peer pipe: fixed-size packet every N ms (dummy or real, indistinguishable).
- Inject a few real payloads; run a dumb timing classifier (“are they chatting?”) — must fail when fill is on.
- Success gate: classifier accuracy → chance under cover; battery/bandwidth cost measured honestly.

**Risks:** Mixnets / cover-traffic research products already exist for cypherpunks (hard market). Differentiator must be ruthlessly simple UX (“one toggle: hide when I message”) or a plugin into an existing messenger — not another chat app. Score stays **MID** until a distribution partner is real.

---

### 3) Ambient Burst — short secrets that look like boring telemetry — **MID**

**Problem (plain):** In locked-down networks, anything that *looks like crypto* gets blocked. People need a way to pass a short vital message that looks like sensor junk, white noise, or dull logs — existence hidden, not just content.

**Who hurts without it:** People under censorship / monitoring who can’t use obvious VPN/chat apps; niche whistleblowing / field ops. **Not** a mass consumer default.

**Cold War / classic cites:**
- Numbers-station / one-way broadcast tradition (short fixed-format traffic to hide patterns) — modern explainer: https://warontherocks.com/explaining-the-mystery-of-numbers-stations/
- Cold War **burst transmitters** (e.g. GRA-71 class): compress minutes of Morse into seconds so DF can’t fix the emitter (period commentary summarizing both sides’ practice).
- Boak COMSEC Vol. II — LPI options (minimum power, hop, narrow beam) as intercept resistance, not just cipher strength.
- Rowland & Irvine lineage / OSI covert channels survey: *Hiding data in the OSI network model* (1996 PDF commonly cited) — https://faculty.kfupm.edu.sa/COE/mimam/Papers/96%20Hiding%20Data%20in%20the%20OSI%20Network%20Model.pdf

**Why unique vs Sigil / Regen:** A `.sg1` (or any sealed blob) *advertises* crypto. Ambient Burst’s bar is **looks like nothing special**. Regen repairs known files; it doesn’t hide presence on the wire.

**How FoldCrypt math helps:** Defect-mask becomes the product metaphor — intentional sparse anomalies in a cover stream (fake CSV telemetry, audio noise bed, timing jitter). Passphrase recovers; wrong key → cover looks untouched.

**Smallest v0 toy:**
- Embed ≤32 bytes into a synthetic “sensor log” or noise WAV as sparse defects.
- Extract with passphrase; run a simple statistical smoke test (does the cover still pass as boring?).
- Success gate: human + naive detector can’t tell cover-only vs cover+payload on a blind A/B.

**Risks:** Stego arms race; ethics/legal; crowded hobby tools. Keep **MID**, not BIG. Only pursue if Ashlynn wants a censorship-resistance lane and accepts niche buyers.

---

## Recommendation

**Pursue #1 FoldAudio first.** It:
- clears the “world can use this” bar (clipping is universal),
- reuses WrapCancel / fold work already in `/workspace/foldcrypt`,
- has a direct 2026 paper + WWII SIGSALY story Ashlynn asked for,
- does **not** collide with Sigil / Regen / ChaosLog,
- has a software-only v0 success gate before any hardware ask.

Keep #2 as a Sunday memo / optional second lane. Park #3 unless she explicitly wants covert-existence tools.

---

## Explicit NO list (scout kills)

| Idea | Why NO |
|------|--------|
| k-of-N recovery shares / Shamir-shaped backup | Duplicates Sigil constellation + classic secret sharing |
| WrapCancel-only radio/SDR SDK as the *product* | Real but niche; fails Ashlynn’s “more than radio researchers” bar |
| AES / Signal / WhatsApp clone | Solved commodity; no FoldCrypt uniqueness |
| RS / PinSketch file repair product | Regenamatron lane |
| SettleSeal / FoldOrbit as products | Parked invent dumps; no clear win over ordinary hash / CollisionHull vocab |
| OTP pad PDF generator / “unbreakable pad” app | Logistics solved poorly for civilians; Venona-style reuse risk; novelty only |
| Tourist frequency-hop / SINCGARS toys | Cool Cold War tech, no civilian product without radio stack |
| Pure post-hoc AI declipper | Crowded; paper shows fold-at-capture beats repair — don’t become another guesser |
| ChaosLog / stock / trading crypto mashup | Wrong teammate / proprietary |

---

## Sources checklist (fetched or confirmed reachable)

- SIGSALY NSA brochure (PDF) — fetched
- USF-Audio / Overflow Overcomes Clipping (EUSIPCO 2026 PDF) — fetched
- Boak COMSEC lecture PDFs — linked (governmentattic / navy-radio); continuous fill synthesis confirmed via secondary summaries
- Filby Traffic Analysis monograph — linked (governmentattic)
- Baran RM-3765 — RAND abstract page fetched (full PDF web-only / paywalled at RAND)
- DTIC ADA067299 *Frequency Hopping in a Jamming Environment* (1978) — linked; useful background, not a product pitch
- Zaxcom NeverClip — commercial dual-ADC prior art noted

---

## Next action if Ashlynn green-lights FoldAudio

Weekday soft-freeze slice: software-only fold→recover WAV demo + 3-clip A/B table; archive WrapCancel as the *engine*, rebrand README toward FoldAudio product story; leave shares-demo parked.
