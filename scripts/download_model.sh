#!/usr/bin/env bash
set -euo pipefail

# Usage: MODEL_DOWNLOAD_URL=... MODEL_FILE_NAME=... ./scripts/download_model.sh
URL=${MODEL_DOWNLOAD_URL:-"$1"}
OUTDIR=${MODEL_OUTPUT_DIR:-"$(dirname "$0")/../backend/models_store"}
FILENAME=${MODEL_FILE_NAME:-}

if [ -z "$URL" ]; then
  echo "MODEL_DOWNLOAD_URL env var or first arg required" >&2
  exit 2
fi

mkdir -p "$OUTDIR"

if [ -z "$FILENAME" ]; then
  FILENAME=$(basename "$URL")
fi

OUTPATH="$OUTDIR/$FILENAME"

echo "Downloading $URL -> $OUTPATH"
curl -fSL "$URL" -o "$OUTPATH"
echo "Downloaded to $OUTPATH"

exit 0
