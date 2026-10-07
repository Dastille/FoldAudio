"""ShockDAQ fail map — slew rule + blind self-flags (2026-10-07 slice)."""

from __future__ import annotations

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
