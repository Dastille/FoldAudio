# FoldAudio: Intentional Modulo Fold Instead of Hard Clip

**Working whitepaper (v0.1)**  
**Author:** Ashlynn (Dastille)  
**Date:** 2026-10-02 (America/New_York)  
**Repo:** https://github.com/Dastille/FoldAudio  
**Status:** Software product trial + reproducible synthetic benchmarks. **Not** a claim of a shipping phone ADC.

---

## Abstract

Hard clipping permanently destroys audio peaks above the converter’s range. FoldAudio records those peaks by **folding** (central modulo wrap) into a bounded interval, then **unwraps** them later. On synthetic speech- and music-like waveforms at 48 kHz with fold threshold \(\lambda = 0.45\), Itoh recovery restores peaks at ~∞ SNR (capped at 120 dB in our metrics) while hard clip sits near 3–4 dB — a >100 dB measurable gain under named assumptions. An intentional fail case (`harsh_kick`: single-sample spikes with sample-to-sample jumps \(>\lambda\)) shows recover **losing** to clip, so the trial stays honest.

FoldAudio is an **acquisition** idea: it changes how sound is captured, not how files are sealed (Sigil) or repaired after known erasures (Regenamatron).

---

## 1. Problem

When a microphone / ADC path saturates, conventional capture **hard-clips**:

\[
c_i = \mathrm{clip}(x_i, [-\lambda, \lambda]).
\]

Everything outside \([-\lambda, \lambda]\) is gone. Post-hoc “declippers” guess missing peaks; they do not restore what was erased. Field interviews, podcasts, concerts, bodycam / evidence audio, and phone voice notes are ruined daily by this.

**Who hurts:** journalists, podcasters, indie filmmakers, security / bodycam users, anyone who cannot babysit gain.

**Not the product:** another AI declipper on already-clipped archives. Fold only helps if you **recorded folded on purpose** (or can recover from wrap-style overflow that preserved residue).

---

## 2. Idea

At capture, apply the **central modulo** (same family as WrapCancel / modulo-ADC literature):

\[
M_\lambda(x) \triangleq \bmod(x + \lambda,\ 2\lambda) - \lambda \in [-\lambda, \lambda).
\]

Loud samples wrap instead of flattening. The recording stays in a fixed range (phone-friendly bit depth), but the wrap history is recoverable when consecutive true samples usually jump by less than \(\lambda\).

Recovery (v0):

1. **Itoh unwrap** on the folded stream (first-order phase-style unwrap).
2. Resolve global \(2\lambda\) level ambiguity with a small integer offset search.
3. In demos, pick the offset with best SNR vs a known original (**oracle prior**). A live recorder without the original needs another absolute-level prior (e.g. quiet-segment anchor) — **not in v0**.

Compare against hard clip on the same \(\lambda\).

---

## 3. Related work (honest lineage)

| Source | Role |
|--------|------|
| Guo & Bhandari, *Digital Audio via Unlimited Sensing: Overflow Overcomes Clipping and Overflow*, EUSIPCO 2026 | Modern fold-at-capture vs clip; hardware-validated USF-Audio; CoSI-Fold family. |
| WrapCancel / FoldDetect (arXiv:2609.11298) | Modulo-ADC **symbol** detect; FoldAudio reuses **modulo + Itoh** for waveforms, not constellation Mahalanobis. |
| NSA / SIGSALY history (Boone & Peterson brochure) | Historical “bounded digital speech → recover later” ancestor; storytelling, not a claim of crypto parity. |
| Zaxcom NeverClip | Dual conventional ADC pro hardware — prior art for “never clip,” **not** modulo fold, not a phone software path. |

FoldAudio’s bar is a **software-first trial** anyone can run: fold → recover → A/B vs clip. Hardware partners (true folded mic path) are later.

---

## 4. Method (v0 implementation)

Package layout (Python, NumPy):

- `foldcrypt.modulo.central_modulo` — \(M_\lambda\)
- `foldcrypt.unfold_detect.itoh_unwrap` — first-order unwrap
- `foldcrypt.foldaudio` — `fold_capture`, `hard_clip`, `recover_itoh`, synthetic generators, WAV I/O, SNR table, `audio-demo` CLI

**Default parameters:** \(\lambda = 0.45\), \(f_s = 48000\) Hz (phone/music rate; keeps music-kick slew under \(\lambda\) more often than 16 kHz).

**Synthetic suite:**

| Name | Intent |
|------|--------|
| `tone_burst` | Clean sinusoid with controlled peaks |
| `speech_like` | Formant-ish bursts |
| `music_peaks` | Transient kicks / peaks at 48 kHz |
| `harsh_kick` | **Intentional fail** — single-sample spikes, \(\max|\Delta x| > \lambda\) |

Listening WAVs may be peak-normalized for int16 PCM; **metrics always use unscaled float arrays**.

---

## 5. Results (v0, 2026-10-02)

\(\lambda=0.45\), \(f_s=48000\), synthetic:

| name | peak | maxΔ | fold% | SNR recovered | SNR clipped | gain dB | Itoh OK |
|------|------|------|-------|---------------|-------------|---------|---------|
| tone_burst | 1.80 | 0.10 | 71.7% | ~∞ (120) | 4.2 | +116 | yes |
| speech_like | 2.15 | 0.13 | 15.4% | ~∞ (120) | 4.1 | +116 | yes |
| music_peaks | 3.49 | 0.30 | 9.0% | ~∞ (120) | 3.3 | +117 | yes |
| harsh_kick | 2.50 | 2.51 | ~0% | 14.1 | 16.5 | **−2.4** | **NO** |

Reproduce:

```bash
cd FoldAudio   # or /workspace/foldcrypt
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m foldcrypt audio-demo
python -m pytest -q
```

Artifacts: `artifacts/foldaudio/` (original / clipped / folded / recovered WAVs + `metrics.json`).

---

## 6. Named assumptions (do not drop)

1. **Software** central-modulo capture — we simulate folded recording; we do **not** claim a phone ADC that folds today.
2. Demo recovery uses an **oracle original** for \(2\lambda\) offset search. Live capture needs a different absolute-level prior.
3. Needs samples that usually jump by **less than \(\lambda\)** between ticks. Impulsive / single-sample spikes can unwrap wrong (`harsh_kick`).
4. WrapCancel’s constellation path is for *symbols*; FoldAudio reuses modulo + Itoh for *waveforms*.
5. Not Sigil, not Regenamatron, not production mastering, not wet-lab DNA.

---

## 7. Fail cases (product honesty)

- **Already-clipped old files** — fold cannot resurrect erased peaks.
- **Impulsive spikes** with \(\max|\Delta x| > \lambda\) — Itoh latches wrong; recover can **lose** to clip.
- **Pro studios** with careful gain staging — less need; home / mobile / field is the story.
- Claiming “phone-ready folded ADC” — out of scope until hardware / driver path exists.

---

## 8. Roadmap (weekday-sized slices)

1. Listen / plot fail cases; document \(\lambda\) vs peak / slew tradeoff.
2. Absolute-level prior **without** original (quiet-segment anchor) for live capture demos.
3. One real WAV (phone clip or CC music) when supplied.
4. Optional: better-than-Itoh unwrap (block / smoothness priors) — after soft-freeze Monte Carlo budget allows.
5. Hardware / interface partners only after software story is boringly solid.

Parked / NO (see also `docs/coldwar-pivot-scout.md`, `docs/foldasync-decision.md`): recovery-shares product (Sigil overlap), FoldAsync CRT compose, SettleSeal / FoldOrbit as products, pure post-hoc AI declipper as the pitch.

---

## 9. What this paper is / is not

**Is:** a short, reproducible product trial + math sketch tying FoldAudio to modulo-fold capture literature and an honest fail case.

**Is not:** a peer-reviewed journal submission, a hardware datasheet, a crypto paper, or a claim that synthetic ∞-SNR generalizes to every live mic path.

---

## References (URLs as of 2026-10-02)

1. Guo & Bhandari, *Digital Audio via Unlimited Sensing…*, EUSIPCO 2026 — https://eurasip.org/Proceedings/Eusipco/Eusipco2026/pdfs/0000411.pdf  
2. WrapCancel / FoldDetect — arXiv:2609.11298  
3. NSA Center for Cryptologic History, *The Start of the Digital Revolution: SIGSALY* — https://www.nsa.gov/portals/75/documents/about/cryptologic-heritage/historical-figures-publications/publications/wwii/sigsaly.pdf  
4. Zaxcom NeverClip overview — https://zaxcom.com/learn/what-is-neverclip/  

Internal memos in-repo: `docs/coldwar-pivot-scout.md`, `docs/foldasync-decision.md`.

---

## Changelog

- **v0.1 (2026-10-02 ET):** First public draft with v0 SNR table, assumptions, fail cases, roadmap. Code + tests + synthetic WAVs in this repository.
