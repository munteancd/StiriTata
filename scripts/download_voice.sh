#!/usr/bin/env bash
# Downloads Piper Romanian voice models used by the generator.
# Run once locally, and in the GitHub Actions workflow (cached).
set -euo pipefail

VOICE_DIR="${VOICE_DIR:-generator/voices}"
mkdir -p "$VOICE_DIR"

VOICE="ro_RO-mihai-medium"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/ro/ro_RO/mihai/medium"

curl -L -o "$VOICE_DIR/${VOICE}.onnx"       "${BASE}/${VOICE}.onnx"
curl -L -o "$VOICE_DIR/${VOICE}.onnx.json"  "${BASE}/${VOICE}.onnx.json"

echo "Downloaded $VOICE to $VOICE_DIR"
