# tokenish VERSION LOG

Factual release ledger. **Measured** = real TOKEX/Agatha numbers. **Unknown** = not invented.  
**DoP** = Duration of Process (approx. wall-clock window, US Eastern).

## Version evolution

Listed **newest → oldest**. Changes inside each version use the concise **`1)`, `2)`, `3)`** format for instant review. Commit dates are first release commits on `main` (or DoP day when pre-tag).

**Agents:** [Agent Registry](../../docs/agents/AGENT_REGISTRY.md) · **Cylinders:** [Cylinder Register](../../docs/cylinders/CYLINDER_REGISTER.md)

---

### v0.4.4 — Clop+ffmpeg media OptComp ON
**Commit date:** 2026-07-21

Ports Clop image/video optimize semantics into a working media cylinder and turns it **ON by default**.

**1) Clop still path** (`tokenish_engine/media/clop_opt.py`)  
- Downscale never-upscale · JPEG ladder · keep if smaller  
- Optional `pngquant` / `jpegoptim` when on PATH  

**2) Clop+ffmpeg temporal path** ([FFMPEG](../../docs/cylinders/FFMPEG.md))  
- GIF: optional gifsicle then ffmpeg keyframes  
- Video: ffmpeg fps+scale sample → JPEG → Clop still each frame  
- Default **ON** (`enable_ffmpeg=true`); disable with `false`  

**3) Ingest wiring**  
- All still attaches use Clop still; GIF/video use temporal sampler  

**Tests:** `tests/test_peer_review_upgrades.py` (`test_clop_still_shrinks_or_keeps`)

---

### v0.4.3 — Peer-review upgrades + ffmpeg cylinder (pending first commit on new remote)
**Commit date:** 2026-07-21

Implements peer-pack P0/P1: sequential Rainman deltas, dual envelope gate fallback, consent-gated ffmpeg media cylinder (Clop-inspired), micro tokenizer gates, benchmark scaffold. Proposal decisions: Alcubierre rejected; Latents parked; Memtrove still out of optimize path.

**1) ffmpeg media cylinder** ([FFMPEG](../../docs/cylinders/FFMPEG.md) · `tokenish_engine/media/ffmpeg_cylinder.py`)  
- Consent-gated (`enable_ffmpeg`, default OFF)  
- GIF/video → keyframe JPEGs via local ffmpeg binary  
- Fallback to Pillow still + stage note if binary missing  
- Resolve via `TOKENISH_FFMPEG` / PATH; Windows builds from [ffmpeg.org/download](https://www.ffmpeg.org/download.html)

**2) Rainman sequential deltas** ([Rainman](../../docs/agents/RAINMAN.md))  
- Prefers measured before→after stage deltas when present  
- Residual equal-shared; equal-share remains caveated fallback

**3) Envelope gate fallback** ([split-exec](../../docs/cylinders/SPLIT_EXEC.md))  
- `pick_gated_envelope` tries ≥2 ranked candidates against tokenizer gate

**4) Micro tokenizer gates** ([Hi0](../../docs/cylinders/HI0.md) · [format_csv](../../docs/cylinders/FORMAT_CSV.md) · [headroom](../../docs/cylinders/HEADROOM.md))  
- Keep transform only if cheaper

**5) Docs schema alignment**  
- Agent + cylinder link profiles under `docs/agents/`, `docs/cylinders/`  
- Version evolution matches AZ Signal Engine README style

**6) Proposal ledger**  
- Clop → toolchain pattern inside ffmpeg (not a separate cylinder)  
- [Alcubierre rejected](../../docs/cylinders/REJECTED_ALCUBIERRE.md) · [Latents parked](../../docs/cylinders/PARKED_LATENTS.md)

**Tests:** `tests/test_peer_review_upgrades.py`  
**Benchmark scaffold:** `packages/engine/benchmarks/README.md`

---

### v0.4.2 — Vision routing + Gemini quota recovery
**Commit date:** 2026-07-15  
**DoP:** ~9:55 PM – ~10:40 PM EST

**1) OpenRouter + photos**  
- Vision chain prefers VL/Gemma; skips text-only free IDs that 404 on images  
- Clearer privacy/data-policy and busy-vision errors

**2) Gemini grey-out** ([Argus](../../docs/agents/ARGUS.md))  
- Time-bounded quota blocks (honor Google “retry in Xs”)  
- Sticky forever-grey fixed; successful calls clear mark

**3) Auto + images**  
- Do not silently strip vision onto Groq/text-only doors

---

### v0.4.1 — Gretta router + provider health UX
**Commit date:** 2026-07-15  
**DoP:** Jul 14–15 overnight through ~10:05 AM EST

**1) Gretta agent** ([Gretta](../../docs/agents/GRETTA.md) · `agents/gretta.py`)  
- Splash + API onboarding; curated protoprompter / qualifier / router  
- Sidebar ask + `/gretta/recommend`; chatbox phases parked

**2) Argus soft grey-out** ([Argus](../../docs/agents/ARGUS.md))  
- Quota / missing key / no credits reasons

**3) Product UX**  
- History dropdown so chat list cannot cover Gretta  
- Passthrough parity for bare chat ([passthrough](../../docs/cylinders/PASSTHROUGH.md))

**4) Agent ledger polish**  
- [Agatha](../../docs/agents/AGATHA.md) · [Rainman](../../docs/agents/RAINMAN.md) · [Neoborg](../../docs/agents/NEOBORG.md)

---

### v0.4.0 — Live World Counter + brand polish
**Commit date:** 2026-07-14  
**DoP:** ~8:03 AM – ~8:46 AM EST

**1) Live World Counter** ([tokex_clock](../../docs/agents/TOKEX_CLOCK.md) · [Neoborg](../../docs/agents/NEOBORG.md))  
- Global panel, absolute per-node hive sync, users-online, CF Worker scaffold

**2) Brand**  
- Logo + tagline *Tag: evry drp cnts*; Grok (xAI) slot; API-link greying inventory

---

### v0.3.1 — Live World Counter Clock (Neoborg hive)
**Commit date:** 2026-07-14  
**DoP:** ~8:03 AM EST onward

**1) Hive modules**  
- `tokex_clock.py` + `hive_store.py` + `packages/tokex-clock/` Worker scaffold

**2) UI**  
- Three TOKEX panels — lifetime / this chat / global

---

### v0.3.0 — fidelity + hive agents
**Commit date:** 2026-07-14  
**DoP:** ~4:34 AM – ~5:42 AM EST

**1) Fidelity-first defaults**  
- [ITS](../../docs/cylinders/ITS.md) OFF · [pxpipe](../../docs/cylinders/PXPIPE.md) OFF · vision billed both sides

**2) Agentics**  
- [Rainman](../../docs/agents/RAINMAN.md) · [Agatha](../../docs/agents/AGATHA.md) · [Mrs. Brown](../../docs/agents/MRS_BROWN.md) · [Neoborg](../../docs/agents/NEOBORG.md)

**3) Connect-an-AI popup + expanded keys**  
- Claude / ChatGPT / Perplexity / Groq when pasted

**4) Cylinder concert**  
- See [Cylinder Register](../../docs/cylinders/CYLINDER_REGISTER.md)

---

### v0.2 — product UI + cylinder concert
**Commit date:** 2026-07-13  
**DoP:** ~11:13 AM – ~2:21 PM EST

**1) TOKEX panels** — lifetime + this-chat  
**2) Mumblz** ([Mumblz](../../docs/agents/MUMBLZ.md))  
**3) Cylinders expanded** — Hi0, dedupe, format_csv, headroom, ITS/FAISS, pxpipe, tokenizer gate, vision  
**4) Multi-image attach fix**

---

### v0.1 — engine boots
**Commit date:** 2026-07-13  
**DoP:** ~2:56 AM – ~11:00 AM EST

**1) FastAPI daemon + chat UI**  
**2) Early path:** ingest → LCS/envelope → TOKEX → dispatch  
**3) Argus beginnings** ([Argus](../../docs/agents/ARGUS.md))  
**4) Key wizard** (Gemini / OpenRouter)

---

### v0.0 — first spark
**Commit date:** 2026-07-13 (~2:56 AM EST first git `80df061`)  
**DoP:** unknown pre-repo; first commit dated above

**1) Idea:** local token optimizer app (not giant SaaS)  
**2) Coinages:** TOKEX · Tokopt · Split-Execution

---

## Neologisms (core)

| Term | Meaning |
|------|---------|
| **TOKEX** | Token Expenditure — before vs after; savings = max(0, before − after) |
| **Tokopt** | Token Optimization |
| **OptComp** | Optimization / Compression engine (cylinder pipeline) |
| **Tokopt cylinder** | One working stage inside OptComp |
| **Split-Execution** | Package job + document for cheaper loyal send |
| **DoP** | Duration of Process |
| **Live World Counter** | Neoborg hive global TOKEX surface |

---

## Maintenance

1. Add newest version at top with **Commit date** + numbered `1)`, `2)`, `3)` blocks.  
2. Link agents/cylinders to `docs/agents/` and `docs/cylinders/`.  
3. Never invent savings numbers in this log.
