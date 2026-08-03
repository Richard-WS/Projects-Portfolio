#!/usr/bin/env bash
# Run the Paradox Engine test suite (node:test — hermetic, no network, no deps).
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v node >/dev/null 2>&1; then
  echo "── JavaScript tests (node:test)"
  node --test tests/*.test.js
  echo "── Browser viewer smoke test (stubbed DOM)"
  node tests/browser-smoke.js
else
  echo "node not found — skipping JavaScript tests" >&2
fi
