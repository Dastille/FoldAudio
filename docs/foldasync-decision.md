# FoldAsync decision memo

**Date:** 2026-10-01 (weekday slice)  
**Status:** **NO compose** — cite + watch only. No code.  
**Primary stay:** WrapCancel / FoldDetect (arXiv:2609.11298).  
**Complementary watch:** FoldAsync / CoSI-Fold (arXiv:2606.21012).

## Plain-language split

| | **WrapCancel** (ours, BIG) | **FoldAsync** (Guo–Bhandari) |
|--|--|--|
| **Ask** | Which *symbols* were sent? | What was the *analog waveform*? |
| **Hardware story** | One oversampled modulo-ADC | Several channels, possibly different fold thresholds λ_l |
| **Timing** | Single clock; oversampling OF | Channels may be *async* (jitter, drift, multi-coset offsets) |
| **Core trick** | Cancel unknown wraps inside residual `r(a)=M_λ(y_λ−Ha)`; Mahalanobis ML on folded samples | Recover integer wraps via modified CRT + *graph smoothness* across channels, then interpolate |
| **Output** | Symbol vector `â` | Unfolded samples → reconstruct `g(t)` |
| **Needs alphabet / H?** | Yes (comms constellation + pulse matrix) | No (bandlimited prior + co-prime λ ratios) |

WrapCancel skips unfolding because the job is detection. FoldAsync *is* an unfolding method, built for multi-channel Unlimited Sampling when clocks do not line up.

## When each applies

**Use WrapCancel when:**

- Goal is SER / symbol recovery on a known injective alphabet.
- One folded stream (or a model that still looks like `y_λ = M_λ(Ha + w) + q`).
- You trust `λ/σ ≳ 2–3` so wrap-cancellation ≈ noise residual.
- You care about low-bitrate MF-ADC comms, not full waveform fidelity.

**Use FoldAsync (or any CRT-USF) when:**

- Goal is high-dynamic-range *waveform* recovery.
- You have **L ≥ 2** folded channels with structured diversity (spatial / multi-coset / deliberate async offsets).
- Folding thresholds satisfy co-prime integer ratios (`λ_l = λ κ_l`).
- Sync is imperfect — that is the paper’s point vs classical CRT-USF.

**Use neither glued together when:** the observation model is undefined (see rule below).

## Never-glue rule (standing)

> **Never compose WrapCancel with FoldAsync (or any unfold-then-detect CRT path) until we write down one shared observation model that both papers’ assumptions fit.**

Why this is not pedantry:

1. **Different unknowns.** WrapCancel searches over symbol strings `a`. FoldAsync searches over wrap integers `γ` (then reconstructs `g`). Gluing “CRT-unfold, then WrapCancel” reintroduces the brittle unfold step WrapCancel exists to avoid. Gluing “multi-channel WrapCancel” invents an `H` / alphabet story FoldAsync does not provide.
2. **Different noise + sync stories.** Ours: bandlimited Gaussian after LPF + uniform quant on one OF-grid. Theirs: per-channel async offsets `T_l^n`, graph smoothness bound `τ_n ≈ Ω · t_c · ‖g‖_∞`, optional quant on the graph residual. Mixing covariances without a joint model is fiction.
3. **Bitcoin-style wiring test.** A mergeable slice must plug into an existing interface (`transmit_with_OF`, `ser`, defect-mask gate). There is no shared plug today — only two arXiv abstracts that both say “modulo.”

Until someone (us or a paper) specifies e.g. “L async MF-ADC streams of the *same* linearly modulated `Ha`, with known relative offsets, detect `a` without full reconstruct,” composition stays **NO**.

## Decision for FoldCrypt v0 / near-term

| Action | Verdict |
|--|--|
| Implement async CRT / graph-smooth unfold | **NO** |
| Keep arXiv:2606.21012 in README as complementary cite | **YES** |
| Revisit compose if a concrete multi-channel *comms* gap appears | **YES — then write the shared model first** |
| Next code slices | Stay on WrapCancel: block-Mahalanobis, stronger unfold baselines, injective-alphabet audit; defect-mask only if still wanted |

## One-line for Ashlynn

FoldAsync is a cousin that *unfolds* multi-channel async modulo samples; WrapCancel *detects* on one folded stream — we cite the cousin and do not bolt it on until we share an observation model.

## Cites

- Vaghela, Appaiah, Mulleti — *Fold First, Detect Directly…* — arXiv:2609.11298  
- Guo & Bhandari — *Asynchronous Multi-Channel USF: Modified CRT…* — arXiv:2606.21012 (EUSIPCO 2026; CoSI-Fold ERC)
