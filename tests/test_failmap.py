"""ShockDAQ fail map — slew rule + blind self-flags (2026-10-07 slice)."""

from __future__ import annotations

import numpy as np

from foldcrypt import failmap as fm
from foldcrypt.blind_level import recover_blind
from foldcrypt.foldaudio import fold_capture
from foldcrypt.shockdaq import DEFAULT_LAM_V, gen_gearbox_startup, gen_impact_transient

LAM = DEFAULT_LAM_V
AMPS = (6.0, 10.0, 20.0, 40.0)
FREQS = (500.0, 2000.0, 4000.0, 12000.0)


def test_slew_rule_predicts_outcome_on_grid():
    cells = fm.run_failmap(AMPS, FREQS)
    assert all(c.predicted_ok == c.recovered_ok for c in cells)
    assert any(c.recovered_ok for c in cells) and any(not c.recovered_ok for c in cells)


def test_every_failure_is_flagged_and_no_slip_false_alarms():
    cells = fm.run_failmap(AMPS, FREQS)
    s = fm.summarize(cells)
    assert s["failed"] > 0
    assert s["fails_silent"] == 0
    assert s["slip_false_alarms_on_ok"] == 0


def test_flags_quiet_on_shipped_shockdaq_cases():
    for gen in (gen_gearbox_startup, gen_impact_transient):
        y = fold_capture(gen(lam=LAM), LAM)
        rec, _ = recover_blind(y, LAM, prior="quiet_window")
        assert not fm.slip_flag(rec, LAM)
        assert not fm.edge_flag(y, LAM)


def test_report_writes_json_and_svg(tmp_path):
    cells, summ = fm.run_failmap_report(tmp_path)
    assert (tmp_path / "failmap.json").exists()
    svg = (tmp_path / "failmap.svg").read_text()
    assert svg.startswith("<svg") and "fail map" in svg
    assert summ["cells"] == len(cells)


def test_quantization_does_not_move_slew_edge_and_stays_loud():
    sweep = fm.run_quant_sweep((6, 12), AMPS, FREQS)
    ideal = sweep["rows"][0]
    for r in sweep["rows"]:
        assert r["rule_agrees_with_outcome"] == r["cells"]
        assert r["fails_silent"] == 0
        assert r["slip_false_alarms_on_ok"] == 0
        assert r["recovered_ok"] == ideal["recovered_ok"]
    assert "ideal" in fm.format_quant_sweep(sweep)


def test_eval_cell_quantized_matches_ideal_on_easy_cell():
    c = fm.eval_cell(10.0, 500.0, bits=8)
    assert c.bits == 8 and c.recovered_ok and not c.slip_flag


# --- non-ideal front end (2026-10-11) ---------------------------------------

NI_AMPS = (6.0, 14.0, 40.0)
NI_FREQS = (500.0, 3000.0, 12000.0)


def _ni_cells(ni, seeds=(7, 8)):
    return [
        fm.eval_nonideal_cell(a, f, ni, seed=s)
        for s in seeds
        for a in NI_AMPS
        for f in NI_FREQS
    ]


def test_nonideal_fold_identity_when_ideal():
    x = fm.ring_burst(amp=14.0, f_ring=1000.0)
    ideal = fm.nonideal_fold(x, LAM, fm.NonIdeal())
    assert (abs(ideal - fold_capture(x, LAM)) < 1e-9).all()


def test_noise_keeps_failures_loud_and_noisy_input_rule_exact():
    for snr in (40.0, 10.0, 0.0):
        cells = _ni_cells(fm.NonIdeal(noise_snr_db=snr))
        assert all(
            c.predicted_ok == c.recovered_ok for c in cells
        )  # rule on input the fold saw
        assert not any(c.silent_fail for c in cells)
        assert not any(c.slip_flag and c.recovered_ok for c in cells)
        assert all(
            c.err_peak_V < 1e-6 for c in cells if c.recovered_ok
        )  # fold adds no error


def test_heavy_noise_breaks_clean_spec_sheet_rule_but_not_honesty():
    cells = fm.run_nonideal_sweep(
        [fm.NonIdeal(noise_snr_db=0.0)], NI_AMPS, NI_FREQS, seeds=(7, 8, 9)
    )["cells"]
    assert any(
        c.clean_rule_ok and not c.recovered_ok for c in cells
    )  # noise moved the edge
    assert not any(c.silent_fail for c in cells)


def test_fold_error_magnitudes_match_model_bounds():
    # threshold / offset / INL: error ≤ param·λ (+ numerical slack); gain: ≤ 2λ|g|·wraps
    for ni, bound in (
        (fm.NonIdeal(thresh_err=0.02), 0.02 * LAM),
        (fm.NonIdeal(thresh_err=-0.02), 0.02 * LAM),
        (fm.NonIdeal(offset=0.02), 0.02 * LAM),
        (fm.NonIdeal(inl=0.02), 0.02 * LAM),
    ):
        for c in _ni_cells(ni):
            if c.recovered_ok:
                assert c.err_peak_V <= bound * 1.05 + 1e-9, (ni.name, c)
    for g in (0.01, -0.01):
        for c in _ni_cells(fm.NonIdeal(gain_err=g)):
            if c.recovered_ok:
                wraps = np.floor(
                    (c.amp_V * 1.5 + LAM) / (2 * LAM)
                )  # generous: harmonic adds 0.4×
                assert c.err_peak_V <= 2 * LAM * abs(g) * wraps + 1e-9


def test_nonideal_sweep_default_configs_zero_silent_zero_false_alarms():
    sweep = fm.run_nonideal_sweep(
        fm.default_nonideal_configs(), NI_AMPS, NI_FREQS, seeds=(7,)
    )
    for r in sweep["rows"]:
        assert r["fails_silent"] == 0, r["config"]
        assert r["slip_false_alarms_on_ok"] == 0, r["config"]
    assert "combo-bad" in fm.format_nonideal_sweep(sweep)


def test_gain_mismatch_is_accuracy_limit_not_unwrap_failure():
    cells = _ni_cells(fm.NonIdeal(gain_err=0.05))
    ok = [c for c in cells if c.recovered_ok]
    assert ok and any(not c.accurate for c in ok)  # >1 % of peak off ...
    assert not any(c.silent_fail for c in cells)  # ... but no silent unwrap failure


# --- noise-aware slew rule (2026-10-15, NOTES #8) ---------------------------


def test_slew_threshold_margin_and_clamp():
    assert fm.slew_threshold(LAM, 0.0) == LAM
    assert np.isclose(fm.slew_threshold(LAM, 0.1, k=5.0), LAM - 0.5)
    assert fm.slew_threshold(LAM, 10.0, k=5.0) == 0.0  # budget used up, never negative
    assert (
        fm.slew_threshold(LAM, -1.0, k=5.0) == LAM
    )  # nonsense σ cannot widen the limit
    # σ = 0 reduces to the plain rule
    assert fm.noise_aware_slew_ok(4.99, LAM, 0.0) and not fm.noise_aware_slew_ok(
        5.0, LAM, 0.0
    )
    assert not fm.noise_aware_slew_ok(4.6, LAM, 0.1, k=5.0)
    assert not fm.noise_aware_slew_ok(0.0, LAM, 10.0)  # threshold 0 → nothing passes


def test_noise_aware_rule_removes_false_ok_on_noisy_rows():
    cfgs = [
        fm.NonIdeal("noise 5 dB", noise_snr_db=5.0),
        fm.NonIdeal("noise 0 dB", noise_snr_db=0.0),
    ]
    sweep = fm.run_nonideal_sweep(cfgs, seeds=(7, 8))
    for r in sweep["rows"]:
        assert r["clean_rule_false_ok"] > 0  # spec-sheet rule is optimistic under noise
        assert r["noise_aware_false_ok"] == 0  # k·σ margin removes every dangerous miss
        assert r["noise_aware_rule_agrees"] > r["clean_rule_agrees"]
        assert r["fails_silent"] == 0
    assert sweep["noise_k"] == fm.NOISE_K
    assert "n-aware" in fm.format_nonideal_sweep(sweep)


def test_noise_aware_rule_costs_nothing_at_high_snr():
    cfgs = [fm.NonIdeal("ideal"), fm.NonIdeal("noise 60 dB", noise_snr_db=60.0)]
    sweep = fm.run_nonideal_sweep(cfgs, seeds=(7,))
    for r in sweep["rows"]:
        assert r["noise_aware_rule_agrees"] == r["cells"] == r["clean_rule_agrees"]


def test_fit_noise_k_finds_safe_k_at_or_below_default():
    cells = fm.run_nonideal_sweep(
        [fm.NonIdeal("noise 0 dB", noise_snr_db=0.0)], seeds=(7,)
    )["cells"]
    fit = fm.fit_noise_k(cells)
    assert fit["rows"][0]["k"] == 0.0 and fit["rows"][0]["false_ok"] > 0
    assert fit["k_min_safe"] is not None and fit["k_min_safe"] <= fm.NOISE_K
    assert [c.name for c in fm.noise_configs()][:2] == ["ideal", "noise 60 dB"]


# --- combined derate + noise-aware slew rule (2026-10-16, NOTES #8b) --------


def test_combined_slew_threshold_edges():
    # σ = 0 → derate-only (D = 1 − π·0.05 ≈ 0.843)
    d = 1.0 - np.pi * 0.05
    assert np.isclose(fm.combined_slew_threshold(LAM, 0.0, inl=0.05), LAM * d)
    # no front-end errors → noise-aware threshold
    assert np.isclose(fm.combined_slew_threshold(LAM, 0.1, k=5.0), LAM - 0.5)
    assert np.isclose(
        fm.combined_slew_threshold(LAM, 0.1, k=5.0),
        fm.slew_threshold(LAM, 0.1, k=5.0),
    )
    # both: derate then subtract kσ
    assert np.isclose(
        fm.combined_slew_threshold(LAM, 0.1, inl=0.05, k=5.0),
        LAM * d - 0.5,
    )
    # derate clamps at 0 (huge INL) → threshold 0
    assert fm.combined_slew_threshold(LAM, 0.0, inl=1.0) == 0.0
    # noise eats the remaining budget → threshold 0, never negative
    assert fm.combined_slew_threshold(LAM, 10.0, k=5.0) == 0.0
    assert fm.combined_slew_threshold(LAM, 10.0, inl=0.05, k=5.0) == 0.0
    # nonsense σ cannot widen the limit
    assert fm.combined_slew_threshold(LAM, -1.0) == LAM


def test_combined_slew_ok_matches_component_rules():
    # σ = 0, no errors → plain clean rule
    assert fm.combined_slew_ok(4.99, LAM, 0.0) and not fm.combined_slew_ok(
        5.0, LAM, 0.0
    )
    # derate=1 → identical to noise_aware
    assert fm.combined_slew_ok(4.4, LAM, 0.1, k=5.0) == fm.noise_aware_slew_ok(
        4.4, LAM, 0.1, k=5.0
    )
    assert fm.combined_slew_ok(4.6, LAM, 0.1, k=5.0) == fm.noise_aware_slew_ok(
        4.6, LAM, 0.1, k=5.0
    )
    # σ = 0 → derate-only on clean slew
    d = 1.0 - np.pi * 0.05
    assert fm.combined_slew_ok(LAM * d - 0.01, LAM, 0.0, inl=0.05)
    assert not fm.combined_slew_ok(LAM * d + 0.01, LAM, 0.0, inl=0.05)
    # threshold 0 → nothing passes
    assert not fm.combined_slew_ok(0.0, LAM, 10.0)
    assert not fm.combined_slew_ok(0.0, LAM, 0.0, inl=1.0)


def test_combined_rule_clears_inl_false_ok():
    """Residual INL false-ok that noise-aware leaves must go to 0 under combined."""
    cfgs = [
        fm.NonIdeal("inl 1%", inl=0.01),
        fm.NonIdeal("inl 2%", inl=0.02),
        fm.NonIdeal("inl 5%", inl=0.05),
        fm.NonIdeal(
            "combo-mild",
            noise_snr_db=60,
            gain_err=0.001,
            thresh_err=0.005,
            offset=0.005,
            inl=0.002,
            bits=16,
        ),
        fm.NonIdeal(
            "combo-bad",
            noise_snr_db=40,
            gain_err=0.005,
            thresh_err=0.01,
            offset=0.01,
            inl=0.01,
            bits=12,
        ),
    ]
    # Two seeds keep this light; the weekday falsify uses all five.
    sweep = fm.run_nonideal_sweep(cfgs, seeds=(7, 8))
    total_naware_fok = sum(r["noise_aware_false_ok"] for r in sweep["rows"])
    total_comb_fok = sum(r["combined_false_ok"] for r in sweep["rows"])
    assert total_comb_fok == 0
    # Combined should not invent silent fails
    assert all(r["fails_silent"] == 0 for r in sweep["rows"])
    assert "combined" in fm.format_nonideal_sweep(sweep)
    # Document the before count for the report (noise-aware may already be 0 on
    # a short seed set; the helper still has to report 0 combined false-ok).
    assert total_naware_fok >= total_comb_fok


def test_combined_rule_no_overderate_on_ideal_high_snr():
    cfgs = [fm.NonIdeal("ideal"), fm.NonIdeal("noise 60 dB", noise_snr_db=60.0)]
    sweep = fm.run_nonideal_sweep(cfgs, seeds=(7,))
    for r in sweep["rows"]:
        assert r["combined_rule_agrees"] == r["cells"] == r["noise_aware_rule_agrees"]
        assert r["combined_false_ok"] == 0
        assert r["combined_false_no"] == 0
