#!/usr/bin/env bash
# Linux/macOS: o'zbek TTS sinovi (Edge TTS, kalitsiz). Repo ildizidan ishga tushiring.
set -e
cd "$(dirname "$0")/.."
if [ ! -d apps/api/.venv ]; then
  uv venv --python 3.12 apps/api/.venv
  uv pip install --python apps/api/.venv/bin/python -e "apps/api[dev]"
fi
apps/api/.venv/bin/python evals/tts_bench.py --providers "${1:-edge}" --out evals/out
echo "Natija: evals/out/results.md va evals/out/edge_*.mp3"
