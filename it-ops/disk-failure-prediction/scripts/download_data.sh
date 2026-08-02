#!/usr/bin/env bash
# Fetch the Backblaze S.M.A.R.T. dataset for one quarter and unpack it into
# data/raw/backblaze/ (gitignored). The Q1 2024 zip is ~1 GB.
#
# Usage:  bash scripts/download_data.sh
# Overrides (env vars): DATA_QUARTER / BACKBLAZE_DATA_URL
set -euo pipefail
cd "$(dirname "$0")/.."

QUARTER="${DATA_QUARTER:-data_Q1_2024}"
URL="${BACKBLAZE_DATA_URL:-https://f001.backblazeb2.com/file/Backblaze-Hard-Drive-Data/${QUARTER}.zip}"

mkdir -p data/raw/backblaze
echo "Downloading ${URL}"
curl -L --fail --progress-bar -o "data/raw/backblaze/${QUARTER}.zip" "$URL"
unzip -o "data/raw/backblaze/${QUARTER}.zip" -d data/raw/backblaze/

echo "Dataset ready in data/raw/backblaze/"
ls -la data/raw/backblaze/
