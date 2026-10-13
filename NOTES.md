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

## Next slices (weekday-sized, soft freeze)

1. ~~**Listen / plot fail cases**~~ — done 2026-10-07 (`failmap.py`, slew rule + self-flags).
2. ~~**Absolute-level prior without original**~~ — done 2026-10-06 (`blind_level.py`).
3. **One real WAV / IEPE capture** (Ashlynn or OEM sample) if supplied — replace synthetic-only claim.

4. ~~**Wire slip/edge flags into `shockdaq-demo`**~~ — done 2026-10-08 (`UNREC` column + `impact_too_fast` case).
5. ~~**Quantization in the fail map**~~ — done 2026-10-09 (`--quant`, `run_quant_sweep`).
6. ~~**Sensor noise + non-ideal ADC in the sweep**~~ — done 2026-10-11 (`--nonideal`); OEM one-pager refreshed.
7. ~~**Fold-step calibration**~~ — done 2026-10-12 (`shockdaq-calibrate`; gain + INL; rail_hits flag the rest).
7b. ~~**RAIL column in `shockdaq-demo`**~~ — done 2026-10-13 (`blind_level.rail_hits`; `gearbox_fold_long` case; firmware status sketch).
8. **Next (light):** noise-aware slew rule (margin = k·σ) fitted properly; real-time flag logic sketch (fall back to clipped value when UNREC).
9. **Still #3:** real IEPE/WAV capture if supplied — the only thing that turns "synthetic" into evidence. Refresh the FoldAudio whitepaper with the fail-map numbers once #3 or an OEM reply lands.

## Do not do

- Touch Sigil / Regenamatron / ChaosLog.
- Polish recovery shares as product.
- Claim a specific OEM chip soft-sat rail (λ=5 V is an ASSUMPTION).
- Soft-freeze: no heavy WrapCancel Monte Carlo on weekday slices.
- Invent bots or Parrot GPU work for synthetic demos.
