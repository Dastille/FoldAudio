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
    return [fm.eval_nonideal_cell(a, f, ni, seed=s) for s in seeds for a in NI_AMPS for f in NI_FREQS]


def test_nonideal_fold_identity_when_ideal():
    x = fm.ring_burst(amp=14.0, f_ring=1000.0)
    ideal = fm.nonideal_fold(x, LAM, fm.NonIdeal())
    assert (abs(ideal - fold_capture(x, LAM)) < 1e-9).all()


def test_noise_keeps_failures_loud_and_noisy_input_rule_exact():
    for snr in (40.0, 10.0, 0.0):
        cells = _ni_cells(fm.NonIdeal(noise_snr_db=snr))
        assert all(c.predicted_ok == c.recovered_ok for c in cells)  # rule on input the fold saw
        assert not any(c.silent_fail for c in cells)
        assert not any(c.slip_flag and c.recovered_ok for c in cells)
        assert all(c.err_peak_V < 1e-6 for c in cells if c.recovered_ok)  # fold adds no error


def test_heavy_noise_breaks_clean_spec_sheet_rule_but_not_honesty():
    cells = fm.run_nonideal_sweep([fm.NonIdeal(noise_snr_db=0.0)], NI_AMPS, NI_FREQS, seeds=(7, 8, 9))["cells"]
    assert any(c.clean_rule_ok and not c.recovered_ok for c in cells)  # noise moved the edge
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
                wraps = np.floor((c.amp_V * 1.5 + LAM) / (2 * LAM))  # generous: harmonic adds 0.4×
                assert c.err_peak_V <= 2 * LAM * abs(g) * wraps + 1e-9


def test_nonideal_sweep_default_configs_zero_silent_zero_false_alarms():
    sweep = fm.run_nonideal_sweep(fm.default_nonideal_configs(), NI_AMPS, NI_FREQS, seeds=(7,))
    for r in sweep["rows"]:
        assert r["fails_silent"] == 0, r["config"]
        assert r["slip_false_alarms_on_ok"] == 0, r["config"]
    assert "combo-bad" in fm.format_nonideal_sweep(sweep)


def test_gain_mismatch_is_accuracy_limit_not_unwrap_failure():
    cells = _ni_cells(fm.NonIdeal(gain_err=0.05))
    ok = [c for c in cells if c.recovered_ok]
    assert ok and any(not c.accurate for c in ok)  # >1 % of peak off ...
    assert not any(c.silent_fail for c in cells)    # ... but no silent unwrap failure
