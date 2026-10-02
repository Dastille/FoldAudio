# FoldCrypt

**Plain-language first.** Public product trial (software). **Not** Sigil, **not** Regenamatron, **not** production crypto, **not** wet-lab DNA, **not** a phone ADC claim.

## Product trial (2026-10-02) — FoldAudio

**Problem:** when sound gets too loud, normal recorders **hard-clip**. Peaks are gone forever.

**Fix:** at capture, **fold** (wrap) loud samples with central modulo \(M_\lambda\), keep recording, then **unwrap** later so peaks come back.

| Piece | Role |
|-------|------|
| **FoldAudio** | Product trial — software fold → recover vs hard-clip |
| **WrapCancel / modulo / Itoh** | Engine (archived symbol-detect toys still in tree) |
| **Recovery shares** | Parked — Sigil constellation already covers seed/backup |

**Whitepaper:** [`docs/foldaudio-whitepaper.md`](docs/foldaudio-whitepaper.md) (v0.1).

**Repo:** https://github.com/Dastille/FoldAudio

### How to run

```bash
cd /workspace/foldcrypt
source .venv/bin/activate
python -m foldcrypt audio-demo
python -m pytest -q
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
2. Recovery = **Itoh unwrap** + small global \(2\lambda\) offset search against the original (demo oracle). A live app without the original needs another absolute-level prior (not in v0).
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
| **FoldAudio** | **MID trial** | Fold loud audio instead of clipping; recover peaks; beat hard-clip SNR on synthetic music/speech. |
| WrapCancel / FoldDetect | **engine / archived** | Modulo-ADC symbol detect (arXiv:2609.11298). Powers FoldAudio’s fold math. |
| Recovery shares | **parked** | Hamming share split — overlaps Sigil constellation for Ashlynn’s own stash. |
| FoldAsync CRT compose | **NO** | [`docs/foldasync-decision.md`](docs/foldasync-decision.md). |
| SettleSeal / FoldOrbit | **parked** | No clear win. |

---

## Layout

```
foldcrypt/
  foldcrypt/
    foldaudio.py       # PRODUCT TRIAL: fold / clip / recover / SNR
    __main__.py        # CLI (audio-demo first)
    modulo.py          # central M_λ (engine)
    unfold_detect.py   # Itoh unwrap (engine)
    # --- parked / archived ---
    recovery_shares.py
    defect_mask.py
    wrapcancel.py block_search.py channel.py constellation.py simulate.py
  testdata/            # synthetic WAVs
  artifacts/foldaudio/ # A/B outputs + metrics.json
  docs/
  tests/
```

## Intentionally deferred

- Absolute claims of phone-ready folded ADC
- Real phone/interface folded capture (needs hardware or driver hook)
- Absolute-level prior without original (live recorder path)
- Better-than-Itoh unwrap (block / smoothness priors)
- Sigil / Regenamatron wiring
