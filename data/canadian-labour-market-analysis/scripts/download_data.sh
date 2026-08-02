#!/usr/bin/env bash
# Download the two Statistics Canada tables used by this project.
#
#   scripts/download_data.sh [raw_dir]
#
# Default raw_dir is data/raw (gitignored). Downloads the official CSV zips:
#   14-10-0327-01  Labour force characteristics by province, annual
#   17-10-0005-01  Population estimates on July 1, by age and gender
# Both are released under the Statistics Canada Open Licence.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW_DIR="${1:-$ROOT/data/raw}"
mkdir -p "$RAW_DIR"

echo "downloading labour force table (14-10-0327-01) ..."
curl -fsSL --retry 3 -o "$RAW_DIR/labour_force.zip" \
    "https://www150.statcan.gc.ca/n1/tbl/csv/14100327-eng.zip"
echo "downloading population table (17-10-0005-01) ..."
curl -fsSL --retry 3 -o "$RAW_DIR/population.zip" \
    "https://www150.statcan.gc.ca/n1/tbl/csv/17100005-eng.zip"

echo "unpacking ..."
unzip -o -q "$RAW_DIR/labour_force.zip" -d "$RAW_DIR"
unzip -o -q "$RAW_DIR/population.zip" -d "$RAW_DIR"
rm -f "$RAW_DIR/labour_force.zip" "$RAW_DIR/population.zip"

echo "done — raw CSVs in $RAW_DIR:"
ls -lh "$RAW_DIR"/*.csv
