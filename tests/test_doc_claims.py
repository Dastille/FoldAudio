"""Guard: any test count stated in the README or docs must match pytest.

The docs avoid hardcoding the count (they point at CI instead). If someone
writes "NN tests" in README.md or docs/*.md again, this test checks the number
against what pytest actually collects, so the claim stays backed.

NOTES.md is excluded on purpose: it is a dated changelog whose per-entry
counts ("... 53 tests.") record the suite size at that date.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
CLAIM = re.compile(r"\b(\d+)\s+(?:unit\s+)?tests\b", re.IGNORECASE)


def _collected_count() -> int:
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    m = re.search(r"(\d+) tests? collected", out)
    assert m, out[-2000:]
    return int(m.group(1))


def _doc_claims() -> list[tuple[str, int, int]]:
    claims = []
    for path in DOCS:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in CLAIM.finditer(line):
                claims.append((path.name, lineno, int(m.group(1))))
    return claims


def test_documented_test_counts_match_pytest_collection():
    n = _collected_count()
    assert n > 0
    stale = [(f, ln, c) for f, ln, c in _doc_claims() if c != n]
    assert not stale, f"pytest collects {n} tests; stale doc counts: {stale}"
