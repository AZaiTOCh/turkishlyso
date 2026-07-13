# tokenish

Open-source **token use optimizer**: a local daemon + chat UI. Every prompt and attachment runs through a **split-execution optimizer**, then dispatches to the model you select.

## install (pip)

```bash
pip install tokenish
tokenish
```

Opens http://127.0.0.1:8741/ and starts the optimizer daemon.

```bash
tokenish doctor    # keys, home, port
tokenish version
tokenish serve --no-browser
```

### from this repo

```bash
cd packages/engine
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
tokenish
```

## golden rule

- compress **instructions** (evidence-based deletion + densify control plane)
- never character-abbreviate free text (vowel shorthand is rejected)
- never silently rewrite **document meaning** — `#D` stays verbatim in follow mode

## windows exe

See [docs/download.md](docs/download.md). Build with:

```powershell
cd packages/engine
.\packaging\build_windows.ps1
```

## optional env / keys

Keys can be pasted in the first-run UI (saved under `~/.tokenish/config.json`) or set as env vars:

| variable | provider |
|----------|----------|
| `GEMINI_API_KEY` | gemini **3.5 flash only** |
| `OPENROUTER_API_KEY` | openrouter |
| `MEMTROVE_API_KEY` | optional Memtrove cloud SDK |

## license

mit
