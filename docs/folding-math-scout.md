# Folding-math scout: folding, vectors and origami-like transforms for compression and recovery

Date: 2026-11-03 (ET)  
Owner: FoldCrypt bot  
Status: research watch, running alongside FoldAudio. **Not a pivot.** FoldAudio and ShockDAQ stay the product and science direction (NOTES #10).  
Bar: an idea scores **BIG** only if it could plausibly beat ordinary compressors (xz / zstd / gzip at max level, *and* a fair quantized baseline) on structured data we actually hold, with recovery we can measure. Being elegant is not enough.

---

## Plain-language summary (for Ashlynn)

- **The question.** Can "folding" a long signal or an irregular sheet into a small square, then unfolding it, store it in fewer bytes than ordinary zip-type tools?
- **What already exists.** The closest real math is the **quantized tensor train (QTT)**. You reshape a list of 2^d numbers into a d-fold stack of 2×2 "creases", then keep only the few patterns that matter. Mathematicians have used it since 2009–2011 to shrink smooth functions and physics problems. It is **well known in numerical maths**, so it is not ours to claim. Other folding ideas (origami fold-and-cut, folding a 3D mesh flat onto a square image, hashing that "folds" a long vector onto a short one) are real and published, but none gives a compression lever for our data.
- **Smoke probe today (exploratory, not the real test).** I folded two real CWRU bearing-vibration records this way. The QTT file came out **7–12× larger** than plain "round to a grid, then xz/bz2". It needed more numbers than the original recording had. On a clean three-tone test signal it was **4–9× smaller**, so the code works. Add only 1 % noise (40 dB) and the advantage goes away. Real vibration is mostly noise-like texture, and folding cannot compress noise.
- **Verdict.** Nothing scored BIG. QTT is the only **MID**. The pre-registered next test checks one narrower, honest variant: fold only the *structured part* (tones and harmonics) and code the leftover noise normally. The probe predicts it will probably fail too. If so, we close this cleanly with a receipt.
- **No crypto claims.** Nothing here is encryption or security. Folding/QTT is compression math only.

---

## Abstract

We surveyed published mathematics that compresses or recovers data by folding, reshaping, or origami-like transforms. The aim was an idea that could beat general-purpose compressors on the structured, real-valued sensor data FoldCrypt already holds (CWRU 48 kHz, Paderborn 64 kHz vibration). Eleven candidates were scored BIG/MID/NO. The strongest is quantized tensor-train (QTT) folding (Khoromskij 2011; Oseledets 2011). It is exponentially compact for signals that are sums of a few exponentials or low-degree polynomials, and the theory is well established. An exploratory smoke probe (one script, fixed seed, ~24 s CPU) found that QTT with TT-SVD truncation loses to a fair quantized + xz/bz2 baseline on two real CWRU records by 7.2–12.2× in bytes at matched or better error. It wins 3.8–9.3× on a noiseless three-tone control and loses 10.5–14.8× once 40 dB white noise is added. We pre-register one falsification experiment, a hybrid "QTT structured part + baseline-coded residual" against the same baselines on pinned CWRU records. We state FAIL criteria before running it. No experiment beyond the smoke probe was run today (soft freeze).

## 1. Problem statement

Ashlynn's request (2026-10-27): scout folding, vector and origami-like math for compression and recovery. Examples: folding an irregular shape into a square, keeping a small imprint of a 2D sheet by folding, unfolding back to a complex shape. Look for under-explored folding math that could beat ordinary compressors on structured data.

Engineering restatement. Given a real-valued record x ∈ ℝ^N (N = 2^d), find a fold map F (reshape / permutation / modulo / sketch) and a compact model of F(x) such that

- bytes(model) < bytes(best general-purpose coder on a fair quantization of x), at
- matched reconstruction error (relative ℓ2, and max-abs where stated), with
- an inverse (unfold) that is deterministic and measurable.

"Fair" baseline means quantizing x to the same error budget first. Comparing a lossy fold to *lossless* xz on float64 bytes would flatter the fold, and that comparison is not allowed here.

## 2. Search method

- WebSearch + WebFetch, 2026-11-02/03 (ET). Query families: quantized tensor train / quantics / "multifolding"; tensor-train decomposition; tensor compression of scientific data (Tucker, TTHRESH); MPS image compression; space-filling-curve reordering; fold-and-cut / computational origami; geometry images (mesh → square); count sketch / folded hashing; modulo / unlimited sampling as source coding; compressed sensing with QTT; DNA-origami storage.
- Every citation below was **opened** by me (abstract page, publisher page or author PDF) unless marked **unverified**. Search-result snippets alone do not count as opened.
- Existing in-tree scouts were checked first so nothing is repeated: `docs/bigger-problem-scout.md` and `docs/coldwar-pivot-scout.md` (2026-10-02). They do not cover tensor/folding compression. They already cite Unlimited Sampling (Bhandari et al.) for FoldAudio, and they scored DNA-origami archival NO→watch.
- Scoring: **BIG** = plausible win against the bar above on our data, and not already standard practice. **MID** = real and relevant, but either well known or unproven on data like ours. **NO** = no compression lever for our data, or wrong domain.

## 3. Ideas and scores

| # | Idea (what "folds") | Score | One plain sentence | Already well known? |
|---|---|---|---|---|
| 1 | **QTT / TT-SVD:** reshape a 2^d record into a 2×2×…×2 tensor and keep a low-rank tensor train [3][4] | **MID** | Very small for smooth or few-tone signals, but our smoke probe says real vibration is too noisy for it to beat round-then-xz. | Yes. Standard in numerical tensor methods since 2009–2011; applying it to measured vibration against general coders looks little-tested (not proven absent). |
| 2 | **Hybrid:** QTT for the structured part + baseline-coded residual (our variant of #1) | **MID (pre-registered, §4)** | The only version of folding that could plausibly win: fold the tones, entropy-code the noise. | The parts are known; we did not find this exact pairing benchmarked on bearing vibration. |
| 3 | **Modulo / unlimited sampling** as a source code (fold the amplitude, unwrap later) [1][2] | **MID** | This is already FoldAudio's core. The Modulo-PCM lineage it cites treats folding as source coding, so it is not new territory for us. | Yes (Ericson–Ramamoorthy Modulo-PCM 1979 is cited in [2]; Bhandari et al. 2017–2020). |
| 4 | **Tucker / HOSVD bit-plane coding (TTHRESH)** [6] | **MID** | Beats zfp/sz on 3D simulation grids at medium-high ratios, but our records are 1D, and folding 1D into 3D gives you #1 again. | Yes (IEEE TVCG). |
| 5 | **MPS image compression** (quantum-inspired) [5] | **NO** | The author's own conclusion is that gzip is vastly better unless the image has a definite block structure. | Yes (2005). |
| 6 | **Hilbert / Z-order reordering before compression** [10][11] | **NO** | Helps 2D/3D grids and AMR meshes by tens of percent, but a 1D time series is already in its best order. | Yes. |
| 7 | **Geometry images:** cut a 3D mesh, fold it flat onto a square, then image-code it [7] | **NO** | The literal "irregular → square" idea, but it is for surface meshes, and we have no meshes. | Yes (SIGGRAPH 2002). |
| 8 | **Fold-and-cut / computational origami** [8][9] | **NO** | Beautiful theorems about which shapes one cut can make; no byte-saving lever. | Yes. |
| 9 | **Count sketch / folded hashing** (fold a long vector onto a short one with random signs) [12] | **NO** | Keeps big items and approximate statistics, but cannot unfold back to the original; lossy summary only. | Yes (ICALP 2002). |
| 10 | **QTT compressed sensing** (Walsh–Hadamard measurements of a QTT signal) [13] | **MID (watch)** | Interesting 2026 theory for measuring few samples of a folded signal, but synthetic-only, noiseless, and it assumes ranks are known. | New (2026); watch only. |
| 11 | **DNA-origami storage (dNAM)** [14] | **NO** | "Origami" here is wet-lab DNA scaffolds with fountain/parity codes; wrong domain, same NO→watch as the 2026-10-02 scout. | Yes. |

Nothing scored BIG. The honest headline is that the folding maths that compresses (QTT/TT) is already known and works for smooth, low-rank signals. Our measured signals are dominated by broadband content, so folding has nothing to exploit.

### Exploratory smoke probe (2026-11-03): not the pre-registered test

Script `scripts/probe_qtt_compress.py`, log `artifacts/folding-scout/qtt-probe-2026-11-03.log` (seed 20261103, wall time ~24 s on the box CPU, CWRU cache read only after the SHA-256 check, no download).

Setup: first 2^17 = 131 072 samples (mean removed). Baseline: uniform quantizer, step q = √12·ε·rms(x), integers coded with xz -9e / bz2 -9 / zlib -9, raw or first-differenced, smallest kept. QTT: TT-SVD (Oseledets Alg. 1) with truncation set so the target equals the baseline's measured relative error, cores stored as float32 and coded with xz -9e. zstd is **not installed** on the box and was not used in the probe. It is required in the pre-registered test.

| Signal | ε = 1e-2 | ε = 3e-3 | ε = 1e-3 | QTT max rank |
|---|---|---|---|---|
| Control: 3 tones, no noise | **0.27** | **0.16** | **0.11** | 6 |
| Control: 3 tones + 40 dB white noise | 10.51 | 14.79 | 11.19 | 145–255 |
| CWRU 97 (normal, 48 kHz) | 11.56 | 8.96 | 7.18 | 254–256 |
| CWRU 238 (outer race 0.021 in, 48 kHz) | 12.23 | 11.73 | 9.35 | 202–254 |

Cells are QTT bytes ÷ best-baseline bytes (< 1 means QTT wins). Caveats, both of which favour the baseline: (i) the TT-SVD per-unfolding error split is conservative, so QTT landed at 1.6–3.2× *lower* error than the baseline on the CWRU records (not tuned to equal error); (ii) the QTT cores were not quantized. Neither caveat closes the gap. On the CWRU records the TT parameter count (166 k–293 k values) already exceeds the sample count (131 k), so even 1 byte per parameter would be larger than the best baseline (51–153 kB). Reading: plain QTT is effectively closed for raw vibration. Only a structured-part variant remains worth a test.

## 4. Pre-registered next experiment (run 2026-11-04, see §4b)

**ID:** FS-1 (folding scout, hybrid QTT). To be run on a later slice. Thresholds below are fixed now, before any FS-1 number exists.

**Hypothesis H1.** Split each record into a structured part s and a residual r = x − s, where s is the QTT approximation of x at a fixed low max-rank R ∈ {4, 8, 16}, chosen per record by smallest total bytes. That choice is part of the coder and is charged in the byte count. Code s as quantized QTT cores and r with the same quantizer + general coder as the baseline. The hybrid is then smaller than the best fair baseline at matched error.

**Measurable prediction.** At a fixed target relative ℓ2 error ε = 3·10⁻³ (with max-abs error also reported), hybrid bytes ≤ 0.95 × best-baseline bytes on **≥ 4 of the 7** pinned CWRU 48 kHz records.

**Baselines (all must run; best one per record is the comparator).**
- Uniform quantizer to the same measured error, then `zstd -19 --ultra -22` (CLI or Python `zstandard`; must be installed and version-logged), `xz -9e`, `gzip -9`, `bz2 -9`, each on raw and first-differenced integers.
- Fair quantized baseline with a predictor: the same quantizer plus an order-2 linear predictor residual, then the same coders. This guards against "folding" only helping because the baseline lacked a predictor.

**Data.** The 7 pinned 48 kHz CWRU drive-end records (97, 109, 122, 135, 213, 226, 238), first 2^17 samples, SHA-256 checked, no download. Secondary (reported, not counted for H1): 4 Paderborn KA04 `_1` records (spike-free) at 64 kHz, 2^17 samples.

**Error matching.** Bisect the quantizer step of the residual coder so the hybrid's measured relative error is within ±2 % of the baseline's. Report both errors. Byte counts include every header the decoder needs (shapes, ranks, quantizer steps, R).

**Controls.**
- Positive: noiseless three-tone signal from the probe. The hybrid must beat the baseline there; if it does not, the run is INVALID (pipeline bug), not a FAIL.
- Negative: white Gaussian noise (seed fixed). The hybrid must *not* beat the baseline by more than 5 %; if it does, the run is INVALID (byte accounting bug).

**FAIL criteria (any one ⇒ H1 falsified and the folding-compression line is closed for vibration with that receipt).**
- F1: hybrid ≤ 0.95 × baseline on fewer than 4 of the 7 CWRU records.
- F2: hybrid wins only because the baseline lacks the order-2 predictor (wins vanish against the predictor baseline).
- F3: the median hybrid/baseline ratio across the 7 records is ≥ 1.00.

**Budget.** Single CPU, < 15 min total, no GPU (Parrot is not needed for this size). Script in `scripts/`, log in `artifacts/folding-scout/`, prereg file committed before the first run.

**Expected outcome (stated now).** The probe suggests FAIL: the structured part of a bearing record (shaft and bearing-defect harmonics) is a small share of its energy. A FAIL is still a useful receipt. It would close "folding beats zip" for this data class with numbers instead of opinion.

## 4b. FS-1 result (run 2026-11-04): H1 FALSIFIED

Code `foldcrypt/fs1.py` (encoder and decoder; every byte count is the length of a stream that is decoded back, and the error is measured on the decoded samples), run script `scripts/fs1_hybrid_qtt.py`, tests `tests/test_fs1_hybrid_qtt.py`. Implementation details were fixed in `artifacts/folding-scout/prereg-2026-11-04-fs1.md` (commit f5a30b0) before any FS-1 number. zstd: Python `zstandard` 0.25.0, libzstd 1.5.7, level 22. CPU, 80 s wall time.

**First run INVALID** (`artifacts/folding-scout/fs1-2026-11-04-first.log`, code badc77e). The positive control failed (hybrid/baseline 1.597 on noiseless tones). Cause, confirmed: when the QTT part alone was already more accurate than the target (three tones at R = 8), the residual-step search could not raise the error into the ±2 % window and the encoder silently dropped that setting. Amendment A (same prereg file, commit b0b4479, before the re-run) keeps such settings with an all-zero residual and their lower error. The first run's CWRU numbers had been seen; the fix cannot apply to them (their QTT part alone is far above the target error), and the re-run repeated all 7 CWRU rows byte for byte.

**Valid run** (`artifacts/folding-scout/fs1-2026-11-04.log`). Both controls passed: noiseless tones 0.140 (hybrid wins, as it must); white noise 1.007 (no win, as it must).

| CWRU record (48 kHz, drive end) | Best baseline (bytes, choice) | Hybrid (bytes, choice) | Hybrid ÷ baseline | Hybrid ÷ no-predictor baseline |
|---|---|---|---|---|
| 97 normal | 109 539, LPC2 + xz | 104 978, R8 float16 | 0.958 | 0.883 |
| 109 inner race 0.007 in | 90 163, LPC2 + xz | 91 453, R4 float16 | 1.014 | 0.913 |
| 122 ball 0.007 in | 79 179, LPC2 + xz | 80 858, R4 float16 | 1.021 | 0.887 |
| 135 outer race 0.007 in | 58 123, LPC2 + bz2 | 61 668, R4 float16 | 1.061 | 0.852 |
| 213 inner race 0.021 in | 72 773, LPC2 + bz2 | 70 534, R4 float16 | 0.969 | 0.873 |
| 226 ball 0.021 in | 77 747, LPC2 + zstd | 87 685, R4 float16 | 1.128 | 0.931 |
| 238 outer race 0.021 in | 67 619, LPC2 + xz | 75 490, R4 float16 | 1.116 | 0.983 |

Errors matched: baseline relative error 2.97–3.01·10⁻³, hybrid 2.96–2.97·10⁻³ (hybrid slightly *more* accurate, inside the ±2 % window). Wins at ≤ 0.95×: **0/7** against the predictor baseline, 6/7 against the baseline without a predictor. Median ratio **1.021**. F1, F2 and F3 all fire.

Reading: the low-rank QTT part acts as a crude predictor. It beats plain quantize + zip, but an ordinary order-2 linear predictor with 8 bytes of coefficients does the same job better. Records 97 and 213 come in 3–4 % under the baseline, which is short of the 5 % bar and is not claimed. Secondary Paderborn KA04 `_1` (64 kHz, not counted): 1.005–1.038, no win. Per §4, the "folding beats zip" line is **closed for vibration records of this kind** with this receipt. The watch continues only for ideas that are not QTT-as-predictor.

## 5. Limitations

- Search coverage is limited to what WebSearch surfaced plus papers referenced by opened papers. Absence of a vibration-specific QTT-vs-zstd benchmark in my results does not prove none exists.
- The smoke probe uses 2 real records and stdlib coders only (no zstd). It is exploratory, and its numbers must not be quoted as a result.
- QTT was tried only in natural (time-major) bit order. Other bit orders, or a short-time transform before folding, are not covered by the probe. FS-1 does not cover them either unless amended before running.
- Lossy compression only. Lossless compression of float64 sensor bytes is a different bar and was not scored.
- Nothing here is cryptography. "Folding" in this memo carries no secrecy or integrity claim.
- Whitepaper numbers are unchanged; this memo adds no table to `docs/foldaudio-whitepaper.md`.

## 6. References

Opened = I loaded the page/PDF on 2026-11-02/03 (ET).

1. Bhandari, A., Krahmer, F., Raskar, R. "On Unlimited Sampling." SampTA 2017. arXiv:1707.06340. https://arxiv.org/abs/1707.06340 (opened)
2. Bhandari, A., Krahmer, F., Raskar, R. "On Unlimited Sampling and Reconstruction." IEEE Trans. Signal Processing version. arXiv:1905.03901. https://arxiv.org/abs/1905.03901 (opened; recovery condition T ≤ 1/(2Ωe); discusses Itoh unwrapping and Modulo-PCM, Ericson & Ramamoorthy 1979)
3. Oseledets, I. V. "Tensor-Train Decomposition." SIAM J. Sci. Comput. 33(5):2295–2317, 2011. doi:10.1137/090752286. PDF: https://users.math.msu.edu/users/iwenmark/Teaching/CMSE890/TENSOR_oseledets2011.pdf (opened; TT-SVD Alg. 1, quasi-optimality √(d−1)); note: http://oseledets.github.io/news/tensor-train-decomposition-paper-finally-published/ (opened)
4. Khoromskij, B. N. "O(d log N)-Quantics Approximation of N-d Tensors in High-Dimensional Numerical Modeling." Constructive Approximation 34(2):257–280, 2011. doi:10.1007/s00365-011-9131-1. https://link.springer.com/article/10.1007/s00365-011-9131-1 (opened; exponentials have QTT rank 1)
5. Latorre, J. I. "Image compression and entanglement." arXiv:quant-ph/0510031, 2005. https://arxiv.org/abs/quant-ph/0510031 (opened)
6. Ballester-Ripoll, R., Lindstrom, P., Pajarola, R. "TTHRESH: Tensor Compression for Multidimensional Visual Data." IEEE TVCG 26(9):2891–2903, 2020 (online 2019). arXiv:1806.05952. https://arxiv.org/abs/1806.05952 (opened)
7. Gu, X., Gortler, S. J., Hoppe, H. "Geometry Images." ACM SIGGRAPH 2002 / ACM TOG 21(3):355–361. https://hhoppe.com/proj/gim/ (opened)
8. Demaine, E. D., Demaine, M. L., Lubiw, A. "Folding and Cutting Paper." JCDCG'98, LNCS 1763:104–117, 2000. https://erikdemaine.org/papers/JCDCG98/ (opened)
9. Demaine, E. D., O'Rourke, J. *Geometric Folding Algorithms: Linkages, Origami, Polyhedra.* Cambridge University Press, 2007. https://erikdemaine.org/papers/GFALOP/ (opened)
10. Luo, H., Wang, J., Liu, Q., Chen, J., Klasky, S., Podhorszki, N. "zMesh: Exploring application characteristics to improve lossy compression ratio for adaptive mesh refinement." IEEE IPDPS 2021. https://digitalcommons.njit.edu/fac_pubs/4138/ (opened; up to 16.5 % (ZFP) / 133.7 % (SZ) ratio gain from Z-order/Hilbert level reordering)
11. Haupt, C., Otoo, E., Cheng, L. (as listed in search results) "Effect of d-Dimensional Re-orderings on Lossless Compression of Radio-Astronomy and Digital Elevation Data." IEEE Access, 2021. doi:10.1109/ACCESS.2021.3084838. **Unverified:** publisher and author pages returned 403/404/401 to my fetches; author list, title and the ~13 % SRTM figure come from search results only.
12. Charikar, M., Chen, K., Farach-Colton, M. "Finding Frequent Items in Data Streams." ICALP 2002 (TCS 2004). https://www.cs.princeton.edu/courses/archive/spring04/cos598B/bib/CharikarCF.pdf (opened)
13. Shao, "Compressed Sensing with Quantized Tensor Trains (QTTs)." arXiv:2609.36506, 2026. https://arxiv.org/abs/2609.36506 (opened; synthetic, noiseless, oracle ranks)
14. Dickinson, G. D., et al. "An alternative approach to nucleic acid memory." Nature Communications 12, 2021. https://www.nature.com/articles/s41467-021-22277-y (opened)

Also seen but **not opened** (excluded from scoring): Oseledets, "Approximation of 2^d×2^d matrices using tensor decomposition," SIAM J. Matrix Anal. Appl. 31(4), 2010 (doi:10.1137/090757861; publisher returned 403). It is the original QTT-matrix paper. Also a 2025 IEEE TIM tensor-train DMD bearing-fault paper, which uses TT for fault features, not compression.
