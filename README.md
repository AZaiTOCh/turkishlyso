# tokenish

Open-source **token use optimizer**: a local daemon + chat UI. Every prompt and attachment runs through a **split-execution / tokopt** pipeline, then dispatches to the model you select.

**evry drp cnts** · current package **v0.4.2**

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

- optimize **packaging** (how the send is bound), not silent omission
- compress **instructions**; never character-abbreviate free text (vowel shorthand is rejected)
- never silently rewrite **document meaning** — full-doc loyalty by default; ITS chunk-skip only with explicit consent
- never claim vision savings without billing vision tokens on both before & after

## what’s in v0.4 (highlights)

### Live World Counter (NeoBorg hive)

- **Third TOKEX panel** (global): upright butterfly GIF, large hive `saved %` (2 decimals), local **H:M:S + timezone**, and **connected users online**.
- Flow: Rainman → Agatha → **Mrs. Brown** (validate numbers) → **NeoBorg** (cross-vet + ledger) → optional hive broadcast.
- Discrete modules:
  - `tokenish_engine/agents/tokex_clock.py` — Live World Counter client (opt-in, sync, fetch)
  - `tokenish_engine/hive_store.py` — engine-local hive (absolute per-node lifetime TOKEX + presence)
  - `packages/tokex-clock/` — Cloudflare Worker scaffold for **true multi-user** worldwide tally
- Endpoints: `GET /tokex-clock`, `POST /tokex-clock/sync`, `POST /tokex-clock/opt-in`, `POST /hive/contribute`
- Sole-user parity: UI syncs **lifetime** totals into the hive so global % matches lifetime until more nodes join.
- Opt-in via the global panel **⋮**. Set `TOKENISH_HIVE_URL` (or paste Worker URL in the popup) for worldwide sharing; blank URL = this engine’s local hive.

### Agents

| Agent | Role |
|-------|------|
| **Argus** | Provider health / failover + linked-API inventory on preflight |
| **Mumblz** | History titles (2 lowercase words) |
| **Rainman** | Factual tokopt-cylinder interrogation (no LLM) |
| **Agatha** | SQLite archive (`~/.tokenish/agatha.db`) |
| **Mrs. Brown** | Matriarch hive intake — numeric TOKEX only |
| **NeoBorg** | Cross-vet + local ledger + Live World Counter broadcast |

### Product UX

- Connect-an-API popup: optional slots, **already linked** greying, Perplexity paid badge, **Grok (xAI)** slot
- Dual **lifetime** / **this chat** TOKEX panels + global hive panel
- Fidelity defaults: ITS off, pxpipe off, vision billed both sides

Full chronological detail: `packages/engine/VERSION_LOG.md`.

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
| `OPENAI_API_KEY` / `GPT_TOKENISH` | ChatGPT |
| `ANTHROPIC_API_KEY` | Claude |
| `GROQ_API_KEY` | Groq |
| `XAI_API_KEY` / `GROK_API_KEY` | Grok (xAI) |
| `PERPLEXITY_API_KEY` | Perplexity |
| `TOKENISH_HIVE_URL` | Live World Counter remote hive (Cloudflare Worker) |
| `MEMTROVE_API_KEY` | optional Memtrove cloud SDK |

## deploy worldwide Live World Counter

```bash
cd packages/tokex-clock
npx wrangler deploy
```

Then set `TOKENISH_HIVE_URL` to the Worker URL (or paste it in the Connect popup). See `packages/tokex-clock/README.md`.

## license

mit
