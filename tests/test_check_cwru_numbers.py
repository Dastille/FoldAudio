"""CI check of scripts/check_cwru_numbers.py against the committed CWRU metrics.

The recompute path needs the CWRU download and is run locally (see
artifacts/cwru-check-run-2026-10-21.log); here the committed JSON files are
compared with the numbers the whitepaper states, and the script's Table 13
constants are compared with the whitepaper's Table 13 text so they cannot drift.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_cwru_numbers", ROOT / "scripts" / "check_cwru_numbers.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_metrics_match_whitepaper_tables_10_to_13(capsys):
    assert _load().main([]) == 0
    assert "RESULT: ALL MATCH" in capsys.readouterr().out


def _num(s: str):
    s = s.strip().replace(",", "")
    return None if s in ("–", "-") else float(s)


def test_table13_constants_match_whitepaper_text():
    mod = _load()
    text = (ROOT / "docs" / "foldaudio-whitepaper.md").read_text(encoding="utf-8")
    block = text.split("**Table 13.**", 1)[1].split("\n\n", 2)[1]
    rows = {}
    for line in block.splitlines():
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) != 10 or not re.match(r"(un)?calibrated", cols[0]):
            continue
        bad_kept, bad_fb = (_num(x) for x in cols[7].split("/"))
        vals = (
            _num(cols[3]),
            _num(cols[4]),
            _num(cols[5]),
            _num(cols[6]),
            bad_kept,
            bad_fb,
            _num(cols[8]),
            _num(cols[9]),
        )
        key = None if cols[1] == "–" else (_num(cols[1].split()[0]), cols[2] == "on")
        rows[key] = vals
    assert rows.pop(None) == mod.TABLE13_UNCAL
    assert rows == mod.TABLE13
