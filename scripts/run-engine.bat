@echo off
cd /d "%~dp0\..\packages\engine"
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -e ".[dev]" -q
uvicorn tokenish_engine.app:app --host 127.0.0.1 --port 8741
