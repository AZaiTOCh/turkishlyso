# Tokenish

Open-source **token-saver** platform: an Ollama-like desktop chat UI whose every prompt and attachment runs through a **Split-Execution Optimizer Engine**, then dispatches to the model you select (local Ollama or cloud APIs).

## Golden rule

- **Compress instructions** (LCS / shorthand).
- **Never semantically compress document content** — extracted file text stays verbatim in `#D`.

## Layout

```
apps/desktop          Ollama-like chat UI (Vite + React)
packages/engine       FastAPI optimizer + model routers
```

## Quick start

### One process (engine + Ollama-like UI)

```bash
cd packages/engine
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
uvicorn tokenish_engine.app:app --reload --port 8741
```

Open **http://127.0.0.1:8741/** — the desktop chat UI is served by the engine (no Node/npm required).

Optional Vite React sources live under `apps/desktop/` if you later install Node.

### Optional env

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GROQ_API_KEY` | Groq |
| `OLLAMA_HOST` | default `http://127.0.0.1:11434` |

OCR needs [Tesseract](https://github.com/tesseract-ocr/tesseract) on PATH (optional: `pip install -e ".[ocr]"`).

## License

MIT
