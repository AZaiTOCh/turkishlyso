# tokenish

Open-source **token use optimizer**: a local desktop chat UI whose every prompt and attachment runs through a **split-execution optimizer engine**, then dispatches to the model you select (local or cloud APIs).

## golden rule

- compress **instructions** (lcs / shorthand)
- never semantically compress **document content** — extracted file text stays verbatim in `#D`

## layout

```
apps/desktop          chat ui sources
packages/engine       fastapi optimizer + model routers
docs/evals            evaluation protocols (gveb, tokex, energy)
```

optimizer stages (backend only — not shown in the ui): lcs, hi0, headroom, moorcheh-style its gate, conditional pxpipe.

## quick start

```bash
cd packages/engine
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn tokenish_engine.app:app --reload --port 8741
```

open **http://127.0.0.1:8741/**

### optional env

| variable | provider |
|----------|----------|
| `GPT_TOKENISH` | openai (chatgpt) |
| `GEMINI_API_KEY` | gemini 3.5 |
| `OPENROUTER_API_KEY` | openrouter |
| `ANTHROPIC_API_KEY` | anthropic |
| `MOORCHEH_API_KEY` | optional moorcheh cloud sdk |

## license

mit
