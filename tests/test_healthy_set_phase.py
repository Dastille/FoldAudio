"""Synthetic checks for the healthy-set N15_M01 phase rules
(prereg-2026-11-08-healthy-set-phase.md). No real K004–K006 numbers."""

from __future__ import annotations

from pathlib import Path

import pytest

from foldcrypt import paderborn as pb
from foldcrypt import paderborn_spikes as ps


def _v(q3: str, c3n: str = "PASS") -> dict:
    return {"Q3": q3, "C3n": c3n}


def test_members_pinned():
    md5 = {
        "K004": "5b9fde1c6d754806539f9a890ee6bbdd",
        "K005": "28d91412ad14583fbdfda958b64a8267",
        "K006": "b36389294fc5a21539d9fcfacfa3604a",
    }
    assert pb.HEALTHY_SET_BEARINGS == ("K004", "K005", "K006")
    assert pb.HEALTHY_SET_MEASUREMENTS == tuple(range(1, 11))
    assert pb.HEALTHY_SET_CONDITIONS == ("N15_M01_F10", "N09_M07_F10")
    for b in pb.HEALTHY_SET_BEARINGS:
        assert pb.EXTRA_BEARINGS[b] == ("healthy", md5[b])
        assert b not in pb.BEARINGS  # earlier sweeps must reproduce unchanged
        for c in pb.HEALTHY_SET_CONDITIONS:
            for m in pb.HEALTHY_SET_MEASUREMENTS:
                assert pb.member(b, c, m) in pb.MAT_SHA256


def test_held_when_all_valid_lock():
    s = ps.healthy_set_verdict(
        {"K004": _v("LOCKS"), "K005": _v("LOCKS"), "K006": _v("LOCKS")}
    )
    assert s["S"] == "HELD"
    assert s["n_valid"] == 3


def test_falsified_by_one_scatter():
    s = ps.healthy_set_verdict(
        {"K004": _v("LOCKS"), "K005": _v("SCATTERS"), "K006": _v("LOCKS")}
    )
    assert s["S"] == "FALSIFIED"


def test_failed_control_bearing_not_counted():
    # a scatter on a bearing whose N09 control failed is not valid evidence
    s = ps.healthy_set_verdict(
        {"K004": _v("LOCKS"), "K005": _v("SCATTERS", "FAIL"), "K006": _v("LOCKS")}
    )
    assert s["S"] == "HELD"
    assert s["valid_bearings"] == ["K004", "K006"]


def test_untestable_below_two_valid():
    s = ps.healthy_set_verdict(
        {"K004": _v("LOCKS"), "K005": _v("UNTESTABLE"), "K006": _v("LOCKS", "FAIL")}
    )
    assert s["S"] == "UNTESTABLE"


def test_not_settled_on_inconclusive():
    s = ps.healthy_set_verdict(
        {"K004": _v("LOCKS"), "K005": _v("INCONCLUSIVE"), "K006": _v("LOCKS")}
    )
    assert s["S"] == "NOT SETTLED"


def test_extract_command_shapes(tmp_path: Path):
    rar, name = tmp_path / "K004.rar", "K004/N15_M01_F10_K004_1.mat"
    u = pb.extract_command(("unar", "/usr/bin/unar"), rar, tmp_path, name)
    assert u == ["/usr/bin/unar", "-q", "-f", "-o", str(tmp_path), str(rar), name]
    z = pb.extract_command(("7z", "/opt/7zz"), rar, tmp_path, name)
    assert (
        z[:2] == ["/opt/7zz", "x"]
        and f"-o{tmp_path}" in z
        and z[-2:] == [str(rar), name]
    )


def test_extractor_prefers_unar_then_env(monkeypatch: pytest.MonkeyPatch):
    found = {"unar": None, "/opt/my7z": "/opt/my7z", "7zz": "/usr/bin/7zz", "7z": None}
    monkeypatch.setattr(pb.shutil, "which", lambda c: found.get(c))
    monkeypatch.setenv(pb.SEVENZIP_ENV, "/opt/my7z")
    assert pb.extractor() == ("7z", "/opt/my7z")
    monkeypatch.delenv(pb.SEVENZIP_ENV)
    assert pb.extractor() == ("7z", "/usr/bin/7zz")
    found["unar"] = "/usr/bin/unar"
    assert pb.extractor() == ("unar", "/usr/bin/unar")
    found.update(unar=None, **{"7zz": None})
    assert pb.extractor() is None
