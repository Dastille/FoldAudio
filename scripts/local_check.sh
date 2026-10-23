#!/usr/bin/env bash
# Local merge gate for FoldCrypt (GitHub Actions is manual-only on the free plan).
#
# Runs ruff lint, ruff format check, pip-audit (dependencies only) and pytest,
# and writes everything to artifacts/local-check-<YYYY-MM-DD>.log as the
# merge receipt. Exits non-zero if any step fails.
#
#   scripts/local_check.sh          # quick gate (CWRU tests may skip)
#   scripts/local_check.sh --full   # also: CWRU and Paderborn tests must run (no skips),
#                                   # and check_cwru_numbers.py --recompute
#
# --full needs SciPy (pip install -e '.[dev,real]') and the 13 CWRU files in
# $FOLDCRYPT_CWRU_CACHE or ~/.cache/foldcrypt/cwru (python -m foldcrypt
# shockdaq-real downloads them once; every file is SHA-256 checked on use),
# plus the 12 Paderborn files in $FOLDCRYPT_PADERBORN_CACHE or
# ~/.cache/foldcrypt/paderborn (python scripts/run_paderborn.py; needs unar).
set -uo pipefail

full=0
case "${1:-}" in
  "") ;;
  --full) full=1 ;;
  *) echo "usage: $0 [--full]" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root" || exit 2
log="artifacts/local-check-$(date +%F).log"
mkdir -p artifacts
: > "$log"

say() { printf '%s\n' "$*" | tee -a "$log"; }
fail=0
step() {
  local name="$1"; shift
  say ""
  say "## $name: $*"
  "$@" 2>&1 | tee -a "$log"
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 0 ]; then say "## $name: PASS"; else say "## $name: FAIL (exit $rc)"; fail=1; fi
}

dirty=""
[ -n "$(git status --porcelain -- . ":(exclude)$log")" ] && dirty=" + uncommitted changes"
say "# FoldCrypt local check ($([ $full -eq 1 ] && echo full || echo quick)), $(date '+%F %H:%M %Z')"
say "# code = $(git rev-parse --short HEAD)$dirty"
say "# $(python --version 2>&1); $(python -c 'import numpy; print("numpy", numpy.__version__)')"
say "# $(python -c 'import scipy; print("scipy", scipy.__version__)' 2>/dev/null || echo 'scipy not installed')"
say "# $(ruff --version); $(pip-audit --version 2>&1)"
say "# CWRU cache = $(python -c 'from foldcrypt import realdata as rd; print(rd.default_cache())')"
say "# Paderborn cache = $(python -c 'from foldcrypt import paderborn as pb; print(pb.default_cache())')"

step lint ruff check .
step format ruff format --check .
step audit pip-audit --skip-editable
if [ $full -eq 1 ]; then
  step tests env FOLDCRYPT_REQUIRE_CWRU=1 FOLDCRYPT_REQUIRE_PADERBORN=1 python -m pytest -q -rs
  step cwru-recompute python scripts/check_cwru_numbers.py --recompute
else
  step tests python -m pytest -q -rs
fi

say ""
if [ $fail -eq 0 ]; then say "# RESULT: PASS"; else say "# RESULT: FAIL"; fi
exit $fail
