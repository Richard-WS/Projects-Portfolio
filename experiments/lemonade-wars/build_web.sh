#!/usr/bin/env bash
# Rebuild the GitHub Pages web version (pygbag) and stage it under web/.
# Run from the project root:  ./build_web.sh
set -euo pipefail

cd "$(dirname "$0")"

if ! python -c "import pygbag" 2>/dev/null; then
    echo "pygbag not installed. Try:  pip install pygbag" >&2
    exit 1
fi

rm -rf build/web
python -m pygbag --build main.py
rm -rf web
cp -r build/web web
echo "Web build staged in web/ — commit it and GitHub Pages will serve it."
