#!/usr/bin/env bash
# Lemonade Wars JS test runner — auto-discovered by the portfolio CI
# (scripts/test.sh in the repo root scans experiments/*/scripts/test.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
node --test tests/*.test.js
