#!/usr/bin/env bash
# Run the full test suite for this project: R (testthat) + JavaScript (node:test).
# Tools that are missing are skipped so the suite degrades gracefully locally.
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v Rscript >/dev/null 2>&1; then
  echo "── R tests (testthat)"
  Rscript tests/testthat.R
else
  echo "Rscript not found — skipping R tests" >&2
fi

if command -v node >/dev/null 2>&1; then
  echo "── JavaScript tests (node:test)"
  node --test tests/*.test.js
else
  echo "node not found — skipping JavaScript tests" >&2
fi
