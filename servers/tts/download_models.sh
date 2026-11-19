#!/usr/bin/env bash
# Download official Kokoro ONNX model weights and voice library
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

KOKORO_MODEL_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_BIN_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

echo "Checking Kokoro TTS model weights..."

if [ ! -f "kokoro-v1.0.onnx" ]; then
    echo "Downloading kokoro-v1.0.onnx..."
    curl -L --progress-bar -o "kokoro-v1.0.onnx" "$KOKORO_MODEL_URL"
else
    echo "kokoro-v1.0.onnx already exists."
fi

if [ ! -f "voices-v1.0.bin" ]; then
    echo "Downloading voices-v1.0.bin..."
    curl -L --progress-bar -o "voices-v1.0.bin" "$VOICES_BIN_URL"
else
    echo "voices-v1.0.bin already exists."
fi

echo "Kokoro TTS models ready."
