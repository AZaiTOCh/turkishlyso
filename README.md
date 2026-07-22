# tokenish

**Version:** 0.4.4 · **Runtime:** local FastAPI daemon + chat UI · **GitHub:** [`tknsh/tokenish`](https://github.com/tknsh/tokenish)

Open-source **token use optimizer**. Every prompt and attachment runs through a **split-execution / tokopt (OptComp)** pipeline, then dispatches to the model you select.

*Tag: evry drp cnts*

---

## Stack

| Layer | Technology |
|-------|------------|
| **Runtime** | Local daemon (`127.0.0.1:8741`) + static chat UI |
| **Language** | Python 3.10+ |
| **OptComp** | Tokopt cylinders — see [Cylinder Register](docs/cylinders/CYLINDER_REGISTER.md) |
| **Agentics** | **1)** Argus · **2)** Mumblz · **3)** Rainman · **4)** Agatha · **5)** Mrs. Brown · **6)** Neoborg · **7)** Gretta · **8)** tokex_clock — [Agent Registry](docs/agents/AGENT_REGISTRY.md) |
| **Providers** | Gemini 3.5 Flash, OpenRouter, OpenAI, Anthropic, Groq, Grok, Perplexity (user keys) |
| **Hive** | Live World Counter — engine-local + optional Cloudflare Worker (`packages/tokex-clock/`) |
| **Version control** | GitHub — [`tknsh/tokenish`](https://github.com/tknsh/tokenish) |

---

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

---

## golden rule

- optimize **packaging** (how the send is bound), not silent omission
- compress **instructions**; never character-abbreviate free text (vowel shorthand is rejected)
- never silently rewrite **document meaning** — full-doc loyalty by default; ITS chunk-skip only with explicit consent
- never claim vision savings without billing vision tokens on both before & after
- ffmpeg / media sampling is **consent-gated** (default OFF), same loyalty posture as ITS

---

## Pipeline (v0.4.3)

```
attachments → ingest (+ optional ffmpeg keyframes)
prompt + doc → Hi0 / dedupe / format_csv / headroom / ITS (conditional)
            → LCS + envelope candidates → tokenizer gate (≥2 fallbacks)
            → TOKEX meter
            → Rainman → Agatha → Mrs. Brown → Neoborg (optional hive)
            → Argus-aware provider dispatch
```

**Agents:**  
**1) [Argus](docs/agents/ARGUS.md)** · **2) [Mumblz](docs/agents/MUMBLZ.md)** · **3) [Rainman](docs/agents/RAINMAN.md)** · **4) [Agatha](docs/agents/AGATHA.md)** · **5) [Mrs. Brown](docs/agents/MRS_BROWN.md)** · **6) [Neoborg](docs/agents/NEOBORG.md)** · **7) [Gretta](docs/agents/GRETTA.md)** · **8) [tokex_clock](docs/agents/TOKEX_CLOCK.md)**

**Cylinders:**  
**1) [ingest](docs/cylinders/INGEST.md)** · **2) [LCS](docs/cylinders/LCS.md)** · **3) [split-exec](docs/cylinders/SPLIT_EXEC.md)** · **4) [Hi0](docs/cylinders/HI0.md)** · **5) [dedupe](docs/cylinders/DEDUPE.md)** · **6) [format_csv](docs/cylinders/FORMAT_CSV.md)** · **7) [headroom](docs/cylinders/HEADROOM.md)** · **8) [ITS](docs/cylinders/ITS.md)** · **9) [FAISS/MIB](docs/cylinders/FAISS_MIB.md)** · **10) [pxpipe](docs/cylinders/PXPIPE.md)** · **11) [tokenizer gate](docs/cylinders/TOKENIZER_GATE.md)** · **12) [vision](docs/cylinders/VISION.md)** · **13) [passthrough](docs/cylinders/PASSTHROUGH.md)** · **14) [ffmpeg/Clop](docs/cylinders/FFMPEG.md)** · **15) [Memtrove](docs/cylinders/MEMTROVE.md)**

Canonical directories: [Agent Registry](docs/agents/AGENT_REGISTRY.md) · [Cylinder Register](docs/cylinders/CYLINDER_REGISTER.md)

---

## what’s in v0.4 (highlights)

### Live World Counter (Neoborg hive)

- **Third TOKEX panel** (global): upright butterfly GIF, large hive `saved %`, local **H:M:S + timezone**, **users online**
- Flow: Rainman → Agatha → **Mrs. Brown** → **Neoborg** → optional hive broadcast
- Set `TOKENISH_HIVE_URL` for worldwide Worker; blank = engine-local hive

### Product UX

- Connect-an-API popup; dual lifetime / this-chat TOKEX + global hive panel
- Fidelity defaults: ITS off, pxpipe off, ffmpeg off; vision billed both sides
- Gretta onboarding / curated router among linked APIs

### ffmpeg (v0.4.3)

- Optional media cylinder — see [FFMPEG](docs/cylinders/FFMPEG.md)
- Install a build from [ffmpeg.org/download](https://www.ffmpeg.org/download.html); set `TOKENISH_FFMPEG` or PATH
- Form flag: `enable_ffmpeg=true` on `/chat` / `/compile`

Full chronology: [`packages/engine/VERSION_LOG.md`](packages/engine/VERSION_LOG.md).

---

## Version evolution

Listed **newest → oldest**. Changes use **`1)`, `2)`, `3)`** format. Detail + DoP: [`VERSION_LOG.md`](packages/engine/VERSION_LOG.md).

### v0.4.4 — Clop+ffmpeg media OptComp ON
**Commit date:** 2026-07-21

**1) Clop still optimize** (never-upscale · JPEG ladder · keep if smaller)  
**2) ffmpeg temporal keyframes ON by default** ([FFMPEG](docs/cylinders/FFMPEG.md))  
**3) Optional Clop CLIs:** pngquant / jpegoptim / gifsicle when on PATH  

### v0.4.3 — Peer-review upgrades + ffmpeg
**Commit date:** 2026-07-21

**1) ffmpeg media cylinder** ([FFMPEG](docs/cylinders/FFMPEG.md)) — consent OFF by default  
**2) Rainman sequential deltas** ([Rainman](docs/agents/RAINMAN.md))  
**3) Envelope gate fallback (≥2 candidates)** ([split-exec](docs/cylinders/SPLIT_EXEC.md))  
**4) Micro tokenizer gates** on Hi0 / format_csv  
**5) Agent + cylinder docs** under `docs/`  
**6) Alcubierre rejected · Latents parked · Memtrove still out of path  

### v0.4.2 — Vision routing + Gemini quota recovery
**Commit date:** 2026-07-15

**1) OpenRouter vision routing**  
**2) Gemini time-bounded grey-out** ([Argus](docs/agents/ARGUS.md))  
**3) Auto+images must not strip to text-only doors  

### v0.4.1 — Gretta + provider health UX
**Commit date:** 2026-07-15

**1) Gretta** ([Gretta](docs/agents/GRETTA.md))  
**2) Soft grey-out reasons**  
**3) History dropdown · passthrough parity  

### v0.4.0 — Live World Counter + brand
**Commit date:** 2026-07-14

**1) Live World Counter** ([Neoborg](docs/agents/NEOBORG.md) · [tokex_clock](docs/agents/TOKEX_CLOCK.md))  
**2) Brand polish · Grok slot  

### v0.3.1 — Hive Clock
**Commit date:** 2026-07-14

**1) Hive store + Worker scaffold · three TOKEX panels**

### v0.3.0 — Fidelity + hive agents
**Commit date:** 2026-07-14

**1) ITS/pxpipe OFF by default**  
**2) Rainman · Agatha · Mrs. Brown · Neoborg**  
**3) Connect-an-AI popup  

### v0.2 — UI + cylinder concert
**Commit date:** 2026-07-13

**1) Lifetime/this-chat TOKEX · Mumblz · expanded cylinders · multi-image fix**

### v0.1 — Engine boots
**Commit date:** 2026-07-13

**1) FastAPI + UI · ingest→LCS→TOKEX→dispatch · Argus beginnings**

### v0.0 — First spark
**Commit date:** 2026-07-13

**1) Local token optimizer idea · TOKEX / Tokopt / Split-Execution**

---

## Future roadmap (WHEN)

| # | Plan | WHEN | Explicitly not yet |
|---|------|------|--------------------|
| F1 | Sealed-run benchmark corpus + published bands | Agatha corpus has multi-workload sealed runs | Invented headline SAVED_PCT |
| F2 | Causal ablation harness beyond sequential deltas | F1 green | UI that implies equal-share is causal |
| F3 | Memtrove retrieve-before-send + RETRIEVE_TOKEX | Enterprise/privacy story + consent UX | Folding retrieve into SAVED_TOKEX |
| F4 | Full Clop-class still encoders (pngquant/gifsicle/…) | ffmpeg path stable on Windows/macOS/Linux | Depending on Clop.app |
| F5 | Latent index (VAE/CLIP+PQ) for retrieve | Memtrove/local index design approved | Sending float latents as chat vision payload |
| F6 | Auditor-grade Live World Counter | Immutable ledgers + anti-double-count policy | Datacenter-deferral marketing claims |

---

## Documentation

| Doc | Path |
|-----|------|
| [Agent Registry](docs/agents/AGENT_REGISTRY.md) | Canonical agent profiles |
| [Cylinder Register](docs/cylinders/CYLINDER_REGISTER.md) | OptComp cylinder profiles |
| [VERSION_LOG](packages/engine/VERSION_LOG.md) | Full version evolution + DoP |
| [Engine README](packages/engine/README.md) | FastAPI endpoints |
| [Download / Windows exe](docs/download.md) | Packaging notes |

---

## windows exe

See [docs/download.md](docs/download.md). Build with:

```powershell
cd packages/engine
.\packaging\build_windows.ps1
```

---

## optional env / keys

| variable | provider |
|----------|----------|
| `GEMINI_API_KEY` | gemini **3.5 flash only** |
| `OPENROUTER_API_KEY` | openrouter |
| `OPENAI_API_KEY` / `GPT_TOKENISH` | ChatGPT |
| `ANTHROPIC_API_KEY` | Claude |
| `GROQ_API_KEY` | Groq |
| `XAI_API_KEY` / `GROK_API_KEY` | Grok (xAI) |
| `PERPLEXITY_API_KEY` | Perplexity |
| `TOKENISH_HIVE_URL` | Live World Counter remote hive |
| `TOKENISH_FFMPEG` | path to `ffmpeg` / `ffmpeg.exe` |
| `MEMTROVE_API_KEY` | optional Memtrove cloud SDK |

---

## deploy worldwide Live World Counter

```bash
cd packages/tokex-clock
npx wrangler deploy
```

Then set `TOKENISH_HIVE_URL` to the Worker URL. See `packages/tokex-clock/README.md`.

---

## license

mit
