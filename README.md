# FoldCrypt

**Plain-language first.** Company licensing bet + public math proof. **Not** Sigil, **not** Regenamatron, **not** production crypto, **not** wet-lab DNA, **not** a claim about a specific OEM ADC chip.

## Company bet (2026-10-04) — ShockDAQ **BIG**

**Problem:** IEPE / vibration DAQ front-ends **soft-clip** (~±5 V rail, ASSUMPTION) **without an overload flag**. Startup shocks and impacts flat-top; acceptance tests understate the real transient.

**Fix:** fold at the soft-sat rail instead of saturating; unwrap later; emit an honest “would have overloaded” flag. OEM wedge: HDR vibration without a second channel.

**OEM one-pager:** [`docs/shockdaq-oem-onepager.md`](docs/shockdaq-oem-onepager.md) · **Scouts:** [`docs/company-adoption-scout.md`](docs/company-adoption-scout.md)

### How to run ShockDAQ

```bash
cd /workspace/foldcrypt
source .venv/bin/activate
python -m foldcrypt shockdaq-demo
python -m foldcrypt shockdaq-failmap   # where fold breaks + self-flags
python -m pytest -q
```

Artifacts → `artifacts/shockdaq/` (`.npy` + listening WAVs + `metrics.json`).

**Fail map:** [`docs/shockdaq-failmap.md`](docs/shockdaq-failmap.md) — fold recovers iff max slew < λ × sample rate (280/280 sweep cells); every failure flagged itself blind (0 silent).

### ShockDAQ v0 metrics (λ=5.0 V, sr=51200, synthetic — real run)

| case | peak V | pk err clip | pk err fold | SNR clip | SNR fold | gain dB | OLflag | Itoh |
|------|--------|-------------|-------------|----------|----------|---------|--------|------|
| gearbox_startup | 12.82 | 7.82 | ~0 | 13.35 | ~∞ (120) | **+106.7** | yes | yes |
| impact_transient | 8.27 | 3.27 | ~0 | 19.35 | ~∞ (120) | **+100.6** | yes | yes |
| impact_too_fast *(past slew limit, on purpose)* | 53.47 | 48.47 | 303 | 2.22 | −31.3 | −33.5 | yes | **NO** |

`UNREC` column (2026-10-08): blind self-check, no original. The two good cases read `no`; `impact_too_fast` reads `SLIP+EDGE`, so the firmware knows not to trust that record (and should fall back to the clipped value + overload flag).

---

## Public proof (2026-10-02) — FoldAudio **MID**

**Problem:** when sound gets too loud, normal recorders **hard-clip**. Peaks are gone forever.

**Fix:** at capture, **fold** (wrap) loud samples with central modulo \(M_\lambda\), keep recording, then **unwrap** later so peaks come back.

| Piece | Role |
|-------|------|
| **ShockDAQ** | **BIG company bet** — IEPE/vibration fold firmware / SDK path |
| **FoldAudio** | **MID public proof** — software fold → recover vs hard-clip |
| **WrapCancel / modulo / Itoh** | Engine (archived symbol-detect toys still in tree) |
| **Recovery shares** | Parked — Sigil constellation already covers seed/backup |

**Whitepaper:** [`docs/foldaudio-whitepaper.md`](docs/foldaudio-whitepaper.md) (v0.1).

**Repo:** https://github.com/Dastille/FoldAudio

```bash
python -m foldcrypt audio-demo
```

Artifacts land in `artifacts/foldaudio/` (original / clipped / folded / recovered WAVs + `metrics.json`).
Testdata (synthetic speech + music-like peaks + tone burst) in `testdata/`.

### v0 SNR results (λ=0.45, sr=48000, synthetic)

| name | peak | maxΔ | fold% | SNR recovered | SNR clipped | gain dB | Itoh OK |
|------|------|------|-------|---------------|-------------|---------|---------|
| tone_burst | 1.80 | 0.10 | 71.7% | ~∞ (120) | 4.2 | +116 | yes |
| speech_like | 2.15 | 0.13 | 15.4% | ~∞ (120) | 4.1 | +116 | yes |
| music_peaks | 3.49 | 0.30 | 9.0% | ~∞ (120) | 3.3 | +117 | yes |
| harsh_kick | 2.50 | 2.51 | ~0% | 14.1 | 16.5 | **−2.4** | **NO** |

`harsh_kick` is an intentional fail (single-sample spikes). Music-like kicks at 48 kHz look **promising** when max sample jump stays under λ.


### Assumptions (named)

1. **Software** central-modulo capture — we simulate folded recording; we do not claim a phone ADC that folds today.
2. Recovery = **Itoh unwrap** + small global \(2\lambda\) offset search against the original (demo oracle). ShockDAQ also ships a blind level prior (`foldcrypt/blind_level.py`, AC-coupling zero-mean) that needs no original; FoldAudio WAVs still use the demo oracle.
3. Needs samples that usually jump by **less than \(\lambda\)** between ticks. Very fast spikes can unwrap wrong.
4. WrapCancel’s constellation Mahalanobis path is for *symbols*; FoldAudio reuses **modulo + Itoh** for waveforms.

### Honest fail cases

- Already-clipped old files — fold only helps if you **recorded folded on purpose**.
- Impulsive / single-sample spikes with max sample jump > λ — Itoh latches wrong (`harsh_kick`: recover **loses** to clip).
- Pro studios with careful gain staging — less need; home/mobile/field is the story.

---

## Scoreboard

| Lead | Score | One sentence |
|------|-------|--------------|
| **ShockDAQ** | **BIG company bet** | Fold inside IEPE/vibration DAQ front-ends; silent soft-clip corrupts acceptance; OEM HDR without second channel. |
| **FoldAudio** | **MID proof** | Fold loud audio instead of clipping; recover peaks; beat hard-clip SNR on synthetic music/speech. Public math proof. |
| WrapCancel / FoldDetect | **engine / archived** | Modulo-ADC symbol detect (arXiv:2609.11298). Powers fold math. |
| Recovery shares | **parked** | Hamming share split — overlaps Sigil constellation for Ashlynn’s own stash. |
| FoldAsync CRT compose | **NO** | [`docs/foldasync-decision.md`](docs/foldasync-decision.md). |
| SettleSeal / FoldOrbit | **parked** | No clear win. |

---

## Layout

```
foldcrypt/
  foldcrypt/
    shockdaq.py        # COMPANY BET: IEPE fold vs silent soft-clip
    foldaudio.py       # PUBLIC PROOF: fold / clip / recover / SNR
    __main__.py        # CLI (shockdaq-demo / shockdaq-failmap / audio-demo)
    failmap.py         # ShockDAQ fail map: slew rule + blind slip/edge flags
    modulo.py          # central M_λ (engine)
    unfold_detect.py   # Itoh unwrap (engine)
    # --- parked / archived ---
    recovery_shares.py
    defect_mask.py
    wrapcancel.py block_search.py channel.py constellation.py simulate.py
  testdata/            # synthetic audio WAVs
  artifacts/shockdaq/  # IEPE A/B + metrics.json
  artifacts/foldaudio/ # audio A/B + metrics.json
  docs/                # OEM one-pager + company scouts + whitepaper
  tests/
```

## Intentionally deferred

- Claims about a specific OEM IEPE/DAQ chip soft-sat rail (λ=5 V is an ASSUMPTION)
- Real IEPE field capture / named DAQ card validation
- ~~Absolute-level prior without original~~ — done for ShockDAQ (`blind_level.py`, 2026-10-06)
- Absolute claims of phone-ready folded ADC
- Better-than-Itoh unwrap (block / smoothness priors)
- Sigil / Regenamatron wiring
