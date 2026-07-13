#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../packages/engine"
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" -q
uvicorn tokenish_engine.app:app --host 127.0.0.1 --port 8741
