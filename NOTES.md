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

## Next slices (weekday-sized, soft freeze)

1. ~~**Listen / plot fail cases**~~ — done 2026-10-07 (`failmap.py`, slew rule + self-flags).
2. ~~**Absolute-level prior without original**~~ — done 2026-10-06 (`blind_level.py`).
3. **One real WAV / IEPE capture** (Ashlynn or OEM sample) if supplied — replace synthetic-only claim.

4. ~~**Wire slip/edge flags into `shockdaq-demo`**~~ — done 2026-10-08 (`UNREC` column + `impact_too_fast` case).
5. ~~**Quantization in the fail map**~~ — done 2026-10-09 (`--quant`, `run_quant_sweep`).
6. **Next:** real IEPE/WAV capture (#3) if supplied; else sensor-noise + non-ideal ADC (INL) in the sweep, or refresh whitepaper/OEM one-pager with fail-map + quantization numbers.

## Do not do

- Touch Sigil / Regenamatron / ChaosLog.
- Polish recovery shares as product.
- Claim a specific OEM chip soft-sat rail (λ=5 V is an ASSUMPTION).
- Soft-freeze: no heavy WrapCancel Monte Carlo on weekday slices.
- Invent bots or Parrot GPU work for synthetic demos.
