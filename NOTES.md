# FoldCrypt / ShockDAQ / FoldAudio NOTES

## Scoreboard (keep honest)

- **BIG company bet now:** **ShockDAQ** (`shockdaq.py`) — fold firmware inside IEPE/vibration DAQ front-ends; silent soft-clip corrupts acceptance; Sunday hard push v0 shipped 2026-10-04.
- **MID public proof:** FoldAudio (`foldaudio.py`) — intentional modulo fold vs hard clip; Itoh recover; synthetic speech/music WAVs. Stays public at Dastille/FoldAudio.
- **Engine:** central modulo + Itoh (WrapCancel family). Symbol-detect SER toys stay archived.
- **Parked:** recovery shares — unique-product bar failed (Sigil constellation overlap).
- **NO:** FoldAsync CRT compose — memo done (`docs/foldasync-decision.md`).
- **Parked:** SettleSeal / FoldOrbit (2026-09-30).

## Done (recent)

- ~~WrapCancel v0 + oracle SER + FoldAsync memo + Alg. 1 block search~~
- ~~Recovery shares pivot~~ then parked after Ashlynn uniqueness check.
- ~~Cold-war scout → FoldAudio pitch~~ (`docs/coldwar-pivot-scout.md`).
- **FoldAudio v0** (2026-10-02) — Ashlynn green-lit build+test + public repo + whitepaper v0.1.
- **Company scouts** (2026-10-02) — `docs/company-adoption-scout.md`, `docs/bigger-problem-scout.md` (ShockDAQ recommended).
- **ShockDAQ v0** (2026-10-04 Sunday hard push) — IEPE fold-vs-clip demo, metrics, OEM one-pager, CLI `shockdaq-demo`.
- **Fail map** (2026-10-07 weekday slice) — `failmap.py`, `shockdaq-failmap` CLI, `docs/shockdaq-failmap.md`. Rule max slew < λ·sr predicted 280/280 cells (5 seeds); every failure (166/166) flagged by blind slip/edge checks, 0 silent, 0 slip false alarms. 53 tests.
- **Blind level prior** (2026-10-06 weekday slice) — `blind_level.recover_blind`: AC-coupling zero-mean or quietest-window prior, no original. Matches oracle on gearbox/impact; fixes mid-overload-start captures (naive k=0 −14/−24 dB → ~120 dB); fails honestly on DC shift ≳ λ. `shockdaq-demo` shows SNR_bl + bl=or columns. 49 tests.

- **UNREC in demo** (2026-10-08 weekday slice) — `shockdaq-demo` now has an `overload_unrecoverable` (`UNREC`) column from blind slip/edge checks (moved to `blind_level.py`, re-exported by `failmap`). New deliberate past-limit case `impact_too_fast` (60 V ring, maxΔ 7.4 V > λ): fold −31 dB (worse than clip +2 dB) but flagged `SLIP+EDGE`; good cases read `no`. Demo exits non-zero on any silent fail or slip false alarm. 55 tests.
- **Quantization** (2026-10-09 weekday slice) — `shockdaq-failmap --quant` / `failmap.run_quant_sweep`: 4–24-bit modulo-ADC through the same grid; slew edge does not move (rule 56/56 at every depth), 0 silent fails, 0 slip false alarms. 57 tests.

- **Non-ideal front end** (2026-10-11 Sunday hard push) — `shockdaq-failmap --nonideal` / `failmap.run_nonideal_sweep`: sensor noise (60→0 dB SNR) + fold gain mismatch, wrap-threshold error, offset, INL, combos × 5 seeds. 0 silent unwrap fails and 0 slip false alarms in all 24 configs. Rule on the noisy input 280/280; spec-sheet (noiseless) rule slips to 219/280 at 0 dB. New honest limit: fold gain/threshold/offset/INL errors give bounded UNFLAGGED peak error (≈ g of peak; e·λ, o·λ, a·λ) — needs calibration, not a flag. `itoh_unwrap` vectorized (same output, ~50× faster). OEM one-pager refreshed with fail-map + quant + non-ideal numbers (synthetic). 63 tests.

- **Front-end calibration** (2026-10-12 weekday slice) — `shockdaq-calibrate` / `calibrate.py`: 159.2 Hz test tone at 4λ, one least-squares fit gives fold-step gain ĝ (worst |ĝ−g| 3e-4 at 60 dB; misses at 40 dB) + INL bow (k=1..3; without INL terms a 5 % bow leaks into ĝ as +4.7 %). `recover_blind(fold_gain=)` + `inl_inverse`. Gain −1 %, INL 2 %/5 % → 114/114 accurate; invisible >1 %-off cells 304 → 0 across all rows. Limit: g>0 and threshold/offset errors push samples past the ADC rail (clipped, unfixable) — visible as `rail_hits`. Design rule: trim fold step short, never long. Rejected: blind g from the burst (~4 % bias), rail interpolation (worse). 69 tests.

- **RAIL in demo** (2026-10-13 weekday slice) — `shockdaq-demo` now reports rail-clipped samples per capture (`RAIL` column = `blind_level.rail_hits`, the same `rail_mask` the sweep uses; re-exported by `failmap`). Ideal-fold cases read `no`. New case `gearbox_fold_long` (gearbox through a +1 % long fold step via `failmap.nonideal_fold`, synthetic): RAIL = 92, UNREC = no, blind SNR 42 dB (clip 13 dB), peak error 0.10 V of 12.8 V. Firmware status sketch `ShockDAQResult.capture_status`: UNRECOVERABLE (UNREC) > BOUNDED_ACCURACY (RAIL) > RECOVERED > IN_RANGE; also in `metrics.json`. Demo's silent check now counts a degraded case as flagged if UNREC or RAIL fires, and fails if RAIL lights on an ideal front end. 72 tests.

- **Technical report v1.0** (2026-10-13) — `docs/foldaudio-whitepaper.md` rewritten as a formal report covering audio + vibration; all numbers re-run. Corrections: slip check alone catches 157/166 five-seed failures (edge 166/166, combined 166/166); `harsh_kick` failure is not caught by slip/edge (isolated-impulse blind spot).

- **Measured CWRU bearing records** (2026-10-14 weekday slice) — `shockdaq-real` / `realdata.py`: 13 public CWRU drive-end records (7 at 48 kHz, 6 at 12 kHz) + 48→12k subsampled copies, rail λ = 0.8…0.25 × peak applied in software, blind recovery. Rule 120/120, 26 exact, 94 failed all flagged, 0 silent, 0 slip false alarms, 3 edge-conservative. 48 kHz: max step 0.32–0.42 × peak → 7.5–9.8 dB extra range, kurtosis/crest kept exact (clip: 20.8→15.9 kurtosis on 238). 12 kHz: step 1.03–1.61 × peak → **no** recoverable overload. Files fetched + SHA-256 checked, not redistributed; SciPy optional extra `[real]`. Whitepaper v1.1 §6.6, one-pager + README updated. 78 tests.

- **Noise-aware slew rule + UNREC fallback** (2026-10-15 weekday slice, NOTES #8) — `failmap.noise_aware_slew_ok` / `slew_threshold`: spec-sheet rule max|Δx_signal| < λ − k·σ, **k = 5** fitted on the 9 noise rows × 5 seeds (2,520 cells; smallest 0.25-grid k with 0 false-ok = 4.75, rounded up). False-ok 119 → 0, agree 2401 → 2435, cost 85 conservative cells all at ≤ 30 dB; ideal/60/40 dB rows unchanged 280/280. Seeds 7–9 alone fit k = 4 → 4 false-ok on held-out 10–11 (hence all-seed fit + round-up). INL rows keep 3–4 false-ok cells (needs derate, not noise margin; all flagged). New table columns `n-aware`, `falseOK c→n`; additive JSON fields; `fit_noise_k`, `noise_configs`. `shockdaq.recover_or_clip` + `overload_event_mask`: on UNREC discard the unwrap, emit the folded samples (exact where |x| < λ), mask the event untrusted, peak "≥ λ". impact_too_fast: SNR −0.1 dB vs slipped unwrap −29.7 dB, 3,385 samples untrusted. Rejected clip(unwrap) (−11…−16 dB vs true clip after a slip). Mask covered every |x| ≥ λ sample in 168 burst cells. `shockdaq-demo` prints `firmware out`, metrics.json `fw_*`. Whitepaper v1.2 (brief §3.6 + §4.4). 87 tests.

- **Combined derate + noise rule + blind σ** (2026-10-16 weekday slice, NOTES #8b) — `failmap.combined_slew_ok` / `combined_slew_threshold`: max|Δx_signal| < λ·D − k·σ with D = max(0, 1 − 2|g| − |e| − |o| − π·|a|), threshold clamped ≥ 0 (same clean-slew convention as noise-aware). On INL+combo rows (1,400 cells, 5 seeds): noise-aware false-ok **12 → 0**, over-derate false-no **0 → 19** (inl 1 %: 0; 2 %: 1; 5 %: 14; combo-mild/bad: 2 each); ideal/60/40 dB unchanged 280/280. `blind_level.estimate_noise_sigma` / `quietest_window_std`: quiet-window sample std of the folded capture; tracks injected σ within ~5 % max rel. error on synthetic quiet+noise and folded mid-overload. Table columns `combined`, `falseOK n→c`; additive JSON. Whitepaper v1.3 (brief §4.4/§4.5 note). 94 tests.

- **Non-ideal front end + fallback on CWRU** (2026-10-19 weekday slice, NOTES #8c) — `shockdaq-real --nonideal` / `realdata.run_real_nonideal_sweep`: 120 CWRU cells × 25 front ends → `recover_or_clip` (3,000 cells). Hypothesis "fallback mask covers every overloaded sample on measured data" **falsified on first run**: 117 overloaded samples in 21 fallback cells (thresh ±2/±10 %, combos) left trusted — threshold error leaves a slow excursion just past λ unwrapped and rail-clipped, steps too small for `overload_event_mask`. **Fix:** fallback untrusted = event mask | rail mask (regression test fails on old code). After: 0 silent slips, 0 uncovered; 2,492 fallback / 508 kept (all 48 kHz). Accuracy: 145 kept cells >1 % off (uncalibrated gain/INL/combo-bad; max 8.0 %), 57 of them invisible (`RECOVERED`, gain −1/−5 %, INL 2/5 %); fallback INL bow 50 cells, ≤3.9 %. Mask is honest but not selective on CWRU: median 100 % of record untrusted (gap 16 → 79 %, default kept; `scripts/probe_fallback_mask.py`). Whitepaper v1.6 (§3.6, §6.6 Table 12, Limitation 1). 117 tests.

## Next slices (weekday-sized, soft freeze)

1. ~~**Listen / plot fail cases**~~ — done 2026-10-07 (`failmap.py`, slew rule + self-flags).
2. ~~**Absolute-level prior without original**~~ — done 2026-10-06 (`blind_level.py`).
3. **One real WAV / IEPE capture** (Ashlynn or OEM sample) if supplied — replace synthetic-only claim.

4. ~~**Wire slip/edge flags into `shockdaq-demo`**~~ — done 2026-10-08 (`UNREC` column + `impact_too_fast` case).
5. ~~**Quantization in the fail map**~~ — done 2026-10-09 (`--quant`, `run_quant_sweep`).
6. ~~**Sensor noise + non-ideal ADC in the sweep**~~ — done 2026-10-11 (`--nonideal`); OEM one-pager refreshed.
7. ~~**Fold-step calibration**~~ — done 2026-10-12 (`shockdaq-calibrate`; gain + INL; rail_hits flag the rest).
7b. ~~**RAIL column in `shockdaq-demo`**~~ — done 2026-10-13 (`blind_level.rail_hits`; `gearbox_fold_long` case; firmware status sketch).
7c. ~~**Real public vibration data**~~ — done 2026-10-14 (CWRU, `shockdaq-real`). Follow-ups: non-ideal front end on CWRU records (light); a second dataset with higher rate or real overload (e.g. Paderborn 64 kHz) (medium).
8. ~~**Noise-aware slew rule + UNREC fallback**~~ — done 2026-10-15 (`noise_aware_slew_ok`, k = 5; `recover_or_clip`).
8b. ~~**Combined derate + noise rule + blind σ**~~ — done 2026-10-16 (`combined_slew_ok`; INL/combo false-ok 12 → 0, false-no +19; `estimate_noise_sigma`).
8c. ~~**Non-ideal front end + `recover_or_clip` on CWRU**~~ — done 2026-10-19 (falsified first, fixed: fallback mask now includes rail samples; 0 silent, 0 uncovered of 3,000 cells).
8d. **Next (light):** one-tone calibration (`calibrate.py`) applied to the CWRU non-ideal rows — do the 57 invisible cells go to 0 on measured waveforms as on the synthetic grid?
9. **Still #3:** real IEPE/WAV capture if supplied — the only thing that turns "synthetic" into evidence. Refresh the FoldAudio whitepaper with the fail-map numbers once #3 or an OEM reply lands.

## Do not do

- Touch Sigil / Regenamatron / ChaosLog.
- Polish recovery shares as product.
- Claim a specific OEM chip soft-sat rail (λ=5 V is an ASSUMPTION).
- Soft-freeze: no heavy WrapCancel Monte Carlo on weekday slices.
- Invent bots or Parrot GPU work for synthetic demos.
