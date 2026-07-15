# tokenish VERSION LOG

Factual release ledger. Updated when a version is committed.
**Measured** = real TOKEX/Agatha numbers. **Unknown** = not invented.
**DoP** = Duration of Process (approx. wall-clock window for that version’s work, US Eastern).

---

## v0.4.1 — Grett router + provider health UX

- **DoP:** Jul 14–15, 2026 · overnight through ~10:05 AM EST
- Package version **0.4.1**.

### Agents / agentics
| Agent | Role / skills (this release) |
|---|---|
| **Grett** | Splash + API onboarding host; **protoprompter / qualifier / router** — matches what you want to a **curated** capability map, then only among **linked** APIs. Not a live “best LLM” scraper. Sidebar ask + recommend path shipped; **chatbox follow-ups parked** (see reminder below). |
| **Argus** | Provider health; soft grey-out reasons (quota / missing key / no credits); Gemini quota stays marked until recoverable. |
| **Agatha** | Archive to `~/.tokenish/output/runs/*.md` + lifetime scoreboard JSON (SQLite write off for new path). |
| **Rainman** | Equal attributed shares of measured run savings among fired cylinders. |
| **NeoBorg** | Display rename + Live World Counter (as in v0.4). |

### Product
- Brand wordmark polish; history **dropdown** so chat list cannot cover Grett.
- Connection / current-model soft grey + blurbs; Gemini lock to `gemini-3.5-flash` with Search-aware parity path.
- Passthrough parity for bare chat; explicit provider lock (no silent Gemma swap).

### Future reminder — Grett chatbox (parked)
| Phase | Scope | Effort |
|---|---|---|
| **Light** | Short follow-ups (“are you sure?”, “what about ChatGPT?”) + last-pick memory + Enter-to-send | ~0.5–1 day |
| **Medium** | Multi-turn Grett sidebar chat (LLM for talk; rules still route models) | ~2–4 days |
| **Heavy** | Full agent: multi-LLM bake-offs, tools, long memory | 1–2+ weeks |

Light agreed as next chat layer when cylinder finetuning cools down — **not started in v0.4.1**.

---

## Neologisms register

Add every new tokenish coinage here when it is incepted. Keep definitions plain. Update **Active (v0.3 default)** when defaults change.

### Core terms

| Neologism | Meaning (plain) | Incepted | Implemented |
|---|---|---|---|
| **TOKEX** | **Tok**en **Ex**penditure — how many tokens a send would have cost *before* vs *after* tokenish; savings = before − after (never below zero) | v0.0 | v0.1+ meter; v0.2 dual lifetime/this-chat panels; v0.3 honesty for vision billing |
| **Tokopt** | **Tok**en **opt**imization — the practice/engine of shrinking what gets sent to an LLM while keeping meaning | v0.0–v0.1 (idea) | named as such in v0.2–v0.3 logs/agents |
| **Tokopt cylinder** | One discrete optimizer stage in the pipeline (like one piston in an engine). Cylinders fire in concert on each run; Rainman records which ones fired | v0.2 (named in product language) | v0.2 stages; v0.3 Rainman/Agatha ledger |
| **Split-Execution** | Package the *job* and the *document/payload* so the model gets a cheaper, still-loyal send | v0.0 | v0.1+ LCS / envelopes |
| **tknsh** | The little pulsing “t-k-n-s-h” wait animation in chat / attach staging | v0.2 | v0.2 UI |
| **DoP** | Duration of Process — wall-clock window for a version’s work | v0.3 | v0.3 VERSION_LOG |
| **TOKEX CLOCK** | Live global tally of tokens saved by tokenish users (NeoBorg broadcast) | v0.3 (named) | **v0.3.1 Live World Counter Clock** — engine hive + Cloudflare Worker scaffold |
| **Live World Counter** | NeoBorg hive surface: collective TOKEX % + local H:M:S/zone + users online | v0.3.1 (as Clock) | **v0.4** renamed; engine hive + CF Worker scaffold |

### Agents (agentics)

| Neologism | Meaning (plain) | Incepted | Implemented |
|---|---|---|---|
| **Argus** | Watchdog that checks which AIs are ready and handles fallback when one is busy | v0.1 | v0.1–v0.3 |
| **Mumblz** | Names each History chat with two clear lowercase words | v0.2 | v0.2–v0.3 (no vowel-strip) |
| **Rainman** | After each run, fact-checks which tokopt cylinders fired and what TOKEX measured — **no guessing, no LLM** | v0.3 | v0.3 (wired into every optimize seal) |
| **Agatha** | Files Rainman’s briefs in a local SQLite archive (`~/.tokenish/agatha.db`) | v0.3 | v0.3 |
| **Mrs. Brown** | Matriarch hive agent — accepts only valid numeric TOKEX records, then hands off to NeoBorg | v0.3 | v0.3 |
| **NeoBorg** | Benevolent hive agent — cross-vet + ledger + Live World Counter broadcast | v0.3 | v0.3 ledger; **v0.4** live counter / sync |
| **Grett** | Onboarding + LLM **protoprompter / qualifier / router** via curated map + linked keys (not scrape-as-truth) | v0.4.1 | v0.4.1 splash/recommend; chatbox phases parked |

### Tokopt cylinders (current register)

**Tokopt** = Token Optimization. A **tokopt cylinder** is one working stage inside that optimization engine.

| Cylinder | What it does (plain) | Incepted | **Active (v0.3 default)** |
|---|---|---|---|
| **ingest** | Reads uploads (PDF, Word, Excel, CSV, images, etc.) into usable text/images | v0.1 | **ON** (always when files attach) |
| **LCS** | Cleans/package the instruction (“what you asked”) into a tighter form | v0.1 | **ON** |
| **split-exec / envelope** | Builds the actual package sent to the AI (job + document layout) | v0.1 | **ON** when there is material to pack |
| **Hi0** | Packs JSON-ish data more tightly without inventing content | v0.2 | **ON** when input looks like JSON |
| **dedupe** | Removes repeated/near-duplicate pages or sections | v0.2 | **ON** when document text exists |
| **format_csv** | Turns some array/JSON tables into cheaper CSV-like text | v0.2 | **ON** when applicable (non–follow-mode) |
| **headroom** | Soft compression on long text logs/docs | v0.2 | **ON** (still blocked from lying by later verbatim/tokenizer gates) |
| **ITS** | Drops *less-relevant* document chunks to save tokens (needs your OK) | v0.2 | **OFF** unless you check “allow skip less-relevant chunks” |
| **FAISS / MIB** | Helps ITS pick which chunks matter (binary index assist) | v0.2 | **Standby** — only with ITS consent |
| **pxpipe** | Packs dense text into an image for vision models when cheaper | v0.1–v0.2 | **OFF** by default (fidelity); also skipped for PDF/normal docs |
| **tokenizer gate** | Rejects “fake savings” tricks (e.g. vowel shorthand that actually costs more) and keeps the cheaper loyal form | v0.2 | **ON** |
| **vision (Pillow)** | Shrinks/normalizes attached photos before send; TOKEX bills vision on both before & after | v0.1 / honesty v0.3 | **ON** when images attach |
| **passthrough** | Very short prompts with nothing to optimize — send as-is | v0.1 | **ON** when triggered |
| **ffmpeg** | Planned media compress cylinder | named in plans | **NOT IMPLEMENTED** |
| **Memtrove cloud** | Optional cloud retrieve assist | v0.2 probe | **NOT in optimize path** (local ITS is the in-engine cousin) |

**v0.3 loyalty rule:** cylinders may **repackage** (how we bind the send). They must not quietly **omit** people’s material unless the user explicitly consents (ITS checkbox).

---

## v0.0 → first spark (pre-public / prototype)
- **DoP:** unknown (pre-repo prototype; before first git commit)
- Idea: a local “token optimizer” you run like a small app, not a giant SaaS.
- See neologisms: **TOKEX**, **Tokopt**, **Split-Execution**.

## v0.1 — engine boots
- **DoP:** Jul 13, 2026 · ~2:56 AM – ~11:00 AM EST (first commit through eve of formal v0.2 packaging)
- **Innovative:** local FastAPI daemon + chat UI; optimize path before the model sees your prompt/files.
- Early cylinders: ingest → LCS / envelope → TOKEX meter → provider dispatch.
- API key wizard (Gemini / OpenRouter).
- **Argus** beginnings.

## v0.2 — product UI + cylinder concert (shipped line through `b108761`)
- **DoP:** Jul 13, 2026 · ~11:13 AM – ~2:21 PM EST (v0.2 packaging ship through multi-image + attachment thumbs)
### Agents / agentics
- **Argus** — live preflight; OpenRouter cools down *one busy model*, not the whole provider.
- **Mumblz** — History chat naming agent (settled on **2 lowercase words**, no vowel-stripping).

### Product innovations
- Lifetime + this-chat **TOKEX** panels (lifetime = saved÷before, never resets on new chat)
- History left / settings right; **tknsh** loader; attachment thumbs
- Multi-image attach (was silently one-image — fixed) + vision cap warnings
- Cylinder concert expanded (see register above for definitions)

### Factual savings stats
- **Unknown server-side** (no Agatha yet in v0.2). UI lifetime % lived in browser localStorage only.

## v0.3.0 — fidelity + hive agents
- **DoP:** Jul 14, 2026 · ~4:34 AM – ~5:42 AM EST (fidelity/agents/popup plan through v0.3.0 merge `dc7048d`)
### Theme
Everyday-user simplicity + **100% loyalty default** + factual agent ledger. Package version **0.3.0**.

### Agents / agentics (innovative)
| Agent | What it does |
|---|---|
| **Mumblz** | History titles (kept) |
| **Argus** | Provider health / failover (kept, stack expanded) |
| **Rainman** | Interrogates each run’s **tokopt cylinders** with *only* measured stage tags + TOKEX — **no LLM, no guesses** |
| **Agatha** | SQLite archivist for Rainman briefs + cylinder fire counts |
| **Mrs. Brown** | Matriarch hive intake — validates numeric TOKEX records |
| **NeoBorg** | Benevolent hive cross-vet + local ledger for future **TOKEX CLOCK** (network broadcast parked) |

### Cylinder defaults this version
- See **Tokopt cylinders (current register)** for full list.
- Fidelity-first: **ITS OFF**, **pxpipe OFF**, vision billed both sides, max **16** images.

### Everyday UX
- New **Connect an AI** popup every session (unless “don’t show again”): signup links, plain-language hints, paid vs free badges, stack order, + add another key
- Sidebar ⋮ explainers (connection / model / keys / status / PDF pages)
- Groq **70b then 8b** after OpenRouter
- Claude / ChatGPT / Perplexity / Groq keys supported when pasted

### Fallback (simple)
Paid you added (Claude → ChatGPT) first → **Gemini free first** among unpaid → OpenRouter free swarm → Groq 70b/8b → Perplexity.

### Factual savings stats (at ship)
- Agatha/NeoBorg ledgers start empty until you run chats on this build → **unknown until first sealed runs**.
- Rainman then reports measured run TOKEX; Agatha fire counts accumulate locally.

### Not in this commit (parked)
- Live multi-user NeoBorg **TOKEX CLOCK** network broadcast (local ledger ready).

---

## v0.3.1 — Live World Counter Clock (NeoBorg hive)
- **DoP:** Jul 14, 2026 · ~8:03 AM EST onward (global panel + hive resume)
- **Tokopt / hive:** NeoBorg unparks network path
  - Discrete module: **Live World Counter Clock** (`tokex_clock.py` + `hive_store.py`)
  - Option **B**: tiny always-on hive API (Cloudflare Worker scaffold in `packages/tokex-clock`); engine-local `/hive` until Worker URL is set
  - Opt-in popup + global panel with local H:M:S clock + upright butterfly + hive saved-%
- **UI:** three TOKEX panels — lifetime / this chat / global

---

## v0.4.0 — Live World Counter + brand polish
- **DoP:** Jul 14, 2026 · ~8:03 AM – ~8:46 AM EST (NeoBorg hive resume through v0.4 UI/README)
- Package version **0.4.0**.
- **Live World Counter** (was “TOKEX CLOCK” / Live World Counter Clock): global panel, absolute per-node hive sync, users-online presence, Cloudflare Worker scaffold (`packages/tokex-clock`).
- Brand: logo + tagline **evry drp cnts**; Grok (xAI) slot; API-link greying inventory; lifetime/this-chat borderless color panels.
- Agents unchanged in set from v0.3; NeoBorg broadcast + `tokex_clock` / `hive_store` are the net-new hive surface.

---

## Maintenance notes
When committing a new version:
1. Add **DoP:** `Mon DD, YYYY · ~H:MM AM/PM – ~H:MM AM/PM EST`
2. If any **neologism** is new or redefined, update the tables at the head (incepted + implemented columns).
3. If any **tokopt cylinder** is added, removed, or changes default ON/OFF, update the cylinder register **Active** column.
4. Never invent savings numbers in this log.
