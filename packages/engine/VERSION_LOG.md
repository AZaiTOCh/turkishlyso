# tokenish VERSION LOG

Factual release ledger. Updated when a version is committed.
**Measured** = real TOKEX/Agatha numbers. **Unknown** = not invented.

---

## v0.0 → first spark (pre-public / prototype)
- Idea: a local “token optimizer” you run like a small app, not a giant SaaS.
- **Neologism born: TOKEX** (Token Expenditure) — honest before/after token accounting.
- First Split-Execution sketch: shrink what you *send* to an LLM without pretending magic.

## v0.1 — engine boots
- **Innovative:** local FastAPI daemon + chat UI; optimize path before the model sees your prompt/files.
- **Tokopt cylinders (early):** ingest → LCS packaging → early TOKEX meter → provider dispatch.
- API key wizard (Gemini / OpenRouter).
- Argus beginnings (provider health / failover thinking).

## v0.2 — product UI + cylinder concert (shipped line through `b108761`)
### Agents / agentics
- **Argus** — live preflight; OpenRouter cools down *one busy model*, not the whole provider.
- **Mumblz** — History chat naming agent (settled on **2 lowercase words**, no vowel-stripping).

### Tokopt cylinders working in concert
- ingest (pdf/docx/xlsx/csv/images)
- LCS / split-exec envelopes
- Hi0 (JSON packing)
- dedupe + fuzzy PDF page near-dupes
- headroom
- ITS + FAISS/MIB (with **assess skip** for document loyalty)
- tokenizer gate (rejects fake “vowel shorthand” savings)
- pxpipe (disabled for PDF/text-like; pointer-only bug fixed earlier)
- Pillow vision resize

### Product innovations
- Lifetime + this-chat **TOKEX** panels (lifetime = saved÷before, never resets on new chat)
- History left / settings right; tknsh loader; attachment thumbs
- Multi-image attach (was silently one-image — fixed) + vision cap warnings

### Factual savings stats
- **Unknown server-side** (no Agatha yet in v0.2). UI lifetime % lived in browser localStorage only.

## v0.3.0 — fidelity + hive agents (this commit)
### Theme
Everyday-user simplicity + **100% loyalty default** + factual agent ledger. Package version **0.3.0**.

### Agents / agentics (innovative)
| Agent | What it does |
|---|---|
| **Mumblz** | History titles (kept) |
| **Argus** | Provider health / failover (kept, stack expanded) |
| **Rainman** | Interrogates each run’s **tokopt cylinders** with *only* measured stage tags + TOKEX — **no LLM, no guesses** |
| **Agatha** | SQLite archivist (`~/.tokenish/agatha.db`) for Rainman briefs + cylinder fire counts |
| **Mrs. Brown** | Matriarch hive intake — validates numeric TOKEX records |
| **NeoBorg** | Benevolent hive cross-vet + local ledger for future **global TOKEX CLOCK** (network broadcast still parked) |

### Tokopt cylinders (concert + defaults)
- Same orchestra as v0.2, with fidelity-first defaults:
  - **ITS off** unless user checks “allow skip less-relevant chunks”
  - **pxpipe off** by default
  - vision tokens **billed on both before & after** (no fake vision %)
  - max vision images **16**

### Everyday UX
- New **Connect an AI** popup every session (unless “don’t show again”): signup links, plain-language hints, paid vs free badges, stack order, + add another key
- Sidebar ⋮ explainers (connection / model / keys / status / PDF pages)
- Groq **70b then 8b** in free/paid stack after OpenRouter
- Claude / ChatGPT / Perplexity / Groq keys supported when pasted

### Fallback (simple)
Paid you added (Claude → ChatGPT) first → **Gemini free first** among unpaid → OpenRouter free swarm → Groq 70b/8b → Perplexity.

### Factual savings stats (at ship)
- Agatha/NeoBorg ledgers start empty until you run chats on this build → **unknown until first sealed runs**.
- Rainman will then report measured run TOKEX; Agatha fire counts accumulate locally.

### Not in this commit (parked)
- Live multi-user NeoBorg TOKEX CLOCK network broadcast (local ledger ready).
