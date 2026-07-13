# Tokenish v2 — Architecture Assessment & Working Upgrade Plan

**Status:** Packaging decision locked — **A then B** (pip/CLI first, Windows `.exe` second). Spec not pushed to GitHub.  
**Date:** 2026-07-13  
**Sources reviewed:**
1. `tokenish arch sketch 2.pdf` (Grok conversation: shorthand + interval + MIB + ffmpeg + Ollama UX)
2. `llm-token-optimization-framework.md` (tokenizer-evidence counter-brief)
3. Current repo: `AZaiTOCh/tokenish` @ `main` (v0.1 engine + static UI)
4. Target UX reference: [ollama.com/download](https://ollama.com/download)

---

## 1. Executive verdict

This is a **partial rework, not a full rewrite** — if we keep the golden rule and kill the bad ideas.

| Idea from sources | Verdict for v2 |
|---|---|
| Split-Execution (`#C/#I#L#O` + verbatim `#D`) | **KEEP** — already correct core |
| Delete filler / compress instructions (word-level) | **KEEP & HARDEN** — Tier-1 from MD |
| Structured data formats (CSV/pipe vs JSON) | **ADD** — Tier-1, high ROI |
| Prompt caching awareness | **ADD** — biggest lever for repeated prefixes |
| Conversation history summarization | **ADD** — Tier-1 scaling win |
| Interval / delta updates for chat turns | **ADD (phased)** — real savings, not magic |
| ITS / MIB gating (local, already started) | **KEEP & harden**; FAISS optional later |
| Conditional pxpipe (text→image when cheaper) | **KEEP** — already proven path for dense docs |
| ffmpeg media downscale for attachments | **ADD (optional stage)** |
| Vowel-removal / invented shorthand (`tkn`, `frmwrk`) | **REJECT** — MD proves it *increases* tokens |
| Custom private abbreviation dictionary for free text | **REJECT** — ambiguity + not 100% error-free |
| Gzip/LZMA of prompt text *sent to LLM* | **REJECT as token saver** — APIs count decompressed tokens |
| Full FAISS + DynamoDB RAG stack in v2 MVP | **DEFER** — research track, not install UX |
| Ollama-like one-click / pip install UX | **MUST HAVE for v2** — current install is too hard |

**Bottom line:** The PDF mixes excellent systems ideas (interval diffs, MIB, Ollama UX) with a **tokenizer-hostile** shorthand proposal. The MD is the scientific correction. v2 should be built on the MD’s rules + the PDF’s *systems* ideas + Ollama-grade packaging.

---

## 2. What the two docs actually say (and where they collide)

### 2.1 PDF / Grok sketch — proposed stack

1. **Lossless English shorthand** via vowel stripping + dictionary (`token`→`tkn`)
2. **Interval code** for updates (sentence/chunk deltas + ITS prune)
3. **Multi-layer compression:** shorthand → zip → MIB binary → pxpipe → ffmpeg
4. **MIB/FAISS** binary retrieval with contingency → C+/C− → RSS
5. **Desktop** Electron/Tauri + local models
6. Marketing pro formas (40–70% savings claims)

### 2.2 MD evidence brief — hard constraints

- Token count ≠ character count; BPE rewards *common* strings.
- Letter-removal shorthand **backfires** (tested: 7 tokens → 15).
- **Rule zero: never abbreviate at the character level.**
- Reliable wins: delete redundancy, cheap structured formats, prompt caching, history management.
- Common abbreviations (`info`, `auth`) usually **tie**, not save.
- Verify every transform on the *target* tokenizer.

### 2.3 Collision resolution (authoritative for v2)

```
MD Rule Zero  >  PDF Shorthand Design
PDF Systems (interval, ITS, pxpipe, install UX)  remain valuable
Any "compression" that does not reduce tiktoken/provider tokens is NOT a TOKEX win
```

v2 LCS = **semantic instruction thinning** (delete filler, densify control plane),  
**not** character-level stenography.

---

## 3. Current product reality (v0.1)

### What exists and works conceptually

- FastAPI engine + static chat UI on `:8741`
- Ingest: pdf / docx / xlsx / csv / image
- Pipeline: ingest → Hi0 → Headroom → ITS → pxpipe → LCS envelope → dispatch
- Providers: OpenAI → Gemini → OpenRouter (Argus preflight)
- TOKEX meters (before / after / saved %)
- Follow-attachment mode fixes (in-progress locally, uncommitted)

### What is broken / incomplete for “v2 ready”

| Gap | Impact |
|---|---|
| Install requires venv + `uvicorn` + knowing the port | Fails the Ollama UX bar |
| No single `tokenish` CLI that “just opens” | Users bounce |
| No Windows `.exe` / installer | Non-devs cannot adopt |
| Desktop app (`apps/desktop`) is Vite scaffold only | Not shipping |
| README still mentions Ollama in architecture doc while product dropped it | Confusion |
| Savings often ~0% on mid-size docs if envelope overhead > compression | Trust killer |
| Provider keys buried in `.env` | Friction |
| Marketing claims ahead of measured evals | Credibility risk |
| MIB/ITS is hash-approx, not full dissertation MIB | OK for gate; don’t oversell |

---

## 4. Product thesis for Tokenish v2

**Tokenish is not another chat client.**  
It is a **local optimizer daemon** (Ollama-shaped) that sits in front of any LLM and makes every send cheaper and more honest.

User journey (Ollama-parity):

1. Download installer **or** `pip install tokenish`
2. Run `tokenish` → UI opens, daemon starts
3. Paste API key once (or use local models later)
4. Chat / attach files — every send is optimized automatically
5. See **Saved Tokens** (TOKEX) every turn — never lie (show overhead if negative)

Reference UX: [Ollama Download](https://ollama.com/download) — OS tabs, one command or one binary, no ceremony.

---

## 5. Three upgrade approaches

### Approach A — “Polish v0.1” (small)
Fix savings bugs, keep current layout, document better install.

- **Pros:** Fast  
- **Cons:** Still not downloadable; still not Ollama-simple; still carries bad shorthand temptation  
- **Fit:** No

### Approach B — “v2 Optimizer Daemon + Install Pack” (**recommended**)
Keep Split-Execution core; reject vowel shorthand; add evidence-based LCS; add interval history; ship `pip` + Windows exe; first-run key wizard; harden TOKEX.

- **Pros:** Matches user ask; reuses working engine; kills tokenizer myths; shippable UX  
- **Cons:** Packaging work (PyInstaller/Tauri); phased RAG/MIB  
- **Fit:** Yes

### Approach C — “Full research platform rewrite”
Rebuild around FAISS MIB RAG + Electron + ffmpeg + custom shorthand codec + DynamoDB.

- **Pros:** Matches Grok maximalism  
- **Cons:** Months; high risk; contradicts MD evidence; still doesn’t ship easy UX first  
- **Fit:** Research track only, not v2 MVP

**Recommendation: Approach B**, with Approach C items parked as `v2.x / research` milestones.

---

## 6. v2 Architecture (target)

```
┌─────────────────────────────────────────────────────────────┐
│  tokenish CLI / .exe                                        │
│   • starts local daemon (127.0.0.1:11435 or 8741)            │
│   • opens UI (bundled static or thin desktop shell)         │
│   • first-run: provider keys + defaults                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│  Optimizer Daemon (FastAPI)                                 │
│                                                             │
│  Ingest ──► Evidence-LCS ──► FormatRewrite(#D structured)   │
│       ──► IntervalHistory (deltas / summaries)              │
│       ──► ITS Gate (keep/prune)                             │
│       ──► Conditional pxpipe                                │
│       ──► Optional ffmpeg (images/video)                    │
│       ──► CheapestEnvelope picker                           │
│       ──► TOKEX meter (honest)                              │
│       ──► Dispatch (Argus fallback chain)                   │
└─────────────────────────────────────────────────────────────┘
```

### Golden rules (unchanged + strengthened)

1. Compress **instructions**, never silently rewrite **document meaning**.
2. Never character-abbreviate free text.
3. Every stage must prove `tokens_after < tokens_before` on the target tokenizer, else skip.
4. TOKEX never reports fake savings (show overhead if after > before).
5. Attachments marked “follow instructions” stay verbatim in `#D` (no headroom lossy pass).

---

## 7. Module plan (what to build / kill / defer)

### Build in v2 MVP

| Module | Work |
|---|---|
| `tokenish` packaging | Rename/unify package; entrypoint `tokenish` opens UI + server |
| Install story | `pip install tokenish` + Windows `.exe` (PyInstaller or briefcase) |
| First-run wizard | Paste OpenAI/Gemini/OpenRouter keys in UI; write local config |
| Evidence-LCS | Word/phrase deletion only; densify control plane; tokenizer gate |
| Format optimizer | Tabular `#D` → CSV/pipe when schema-fixed; keep JSON when nested |
| History manager | Summarize/truncate old turns; optional interval deltas |
| Envelope picker | Keep cheapest-of-N (already started) |
| pxpipe | Keep; threshold tuned; vision models only |
| TOKEX honesty | Overhead label; stage breakdown for debug |
| Provider health | Keep Argus; skip dead providers immediately |
| Docs site / download page | Ollama-like: Windows / macOS / Linux / pip one-liners |

### Kill / do not implement

- Vowel-removal shorthand codec
- Expecting models to decode private abbreviation dictionaries
- Gzip/LZMA as a *token* reduction for API payloads
- Shipping Ollama as a hard dependency (optional later adapter only)

### Defer to v2.1+ / research

- Full FAISS Binary IVF + embedding MIB
- Dissertation-faithful C+/C− RSS over dense vectors
- DynamoDB / cloud binary store
- Electron/Tauri native shell (bundled browser UI is enough for MVP)
- Energy pro-forma dashboards (needs measured evals first)

---

## 8. Install UX spec (Ollama-parity)

### Target user actions

**Windows (primary for you now):**
- Download `tokenish-windows.exe` → double-click → tray/daemon + browser UI  
  *or*
- `pip install tokenish` then `tokenish`

**macOS / Linux:**
- `curl -fsSL https://tokenish.ai/install.sh | sh` (future)  
  *or* `pip install tokenish`

### CLI surface (minimal)

```bash
tokenish                 # start daemon + open UI
tokenish serve           # daemon only
tokenish doctor          # keys, ports, tokenizer, provider ping
tokenish stop
tokenish version
```

### First-run

1. Detect missing keys → settings panel (not a buried `.env` edit)
2. Default provider: Auto (Argus chain)
3. One sample “optimize this” prompt to prove TOKEX ≠ 0 on a long paste

---

## 9. Optimizer policy (evidence-based LCS)

### Allowed transforms (must pass tokenizer check)

1. Strip filler phrases (`please`, `kindly`, `in order to`, …)
2. Collapse whitespace / duplicate instructions
3. Control-plane densification (`#C/#I#L#O`) **only if** total tokens drop
4. Structured `#D` rewrite: JSON rows → CSV/pipe when schema stable
5. History: replace old turns with rolling summary
6. Interval deltas for iterative edits to the *same* document session
7. pxpipe when `text_tokens > image_surcharge` and model is vision-capable
8. ffmpeg: downscale huge images/video before OCR/vision

### Forbidden transforms

1. Vowel stripping / consonant skeletons
2. Invented abbreviations for natural language
3. Lossy semantic summarization of `#D` in follow-mode
4. Claiming zip/binary storage savings as TOKEX API savings

### Gate every stage

```python
if count_tokens(after, model) >= count_tokens(before, model):
    discard_stage()  # no-op; never ship overhead as “optimization”
```

---

## 10. Phased delivery plan (working upgrade)

### Phase 0 — Stabilize current engine (1–2 days)
- Land uncommitted savings/follow-mode fixes locally
- Honest TOKEX overhead UI
- `tokenish doctor` basics
- **No GitHub until you approve this plan**

### Phase 1 — Installable MVP (v2.0.0-alpha)
- Unified package name `tokenish`
- `pip install` path that works on Windows
- `tokenish` CLI starts server + opens browser
- First-run key wizard in UI
- Download page markdown (Windows + pip) mirroring Ollama simplicity

### Phase 2 — Evidence optimizer (v2.0)
- Tokenizer-gated LCS (delete-don’t-abbreviate)
- Format rewrite for tabular attachments
- Conversation history summarization
- Eval suite: 20 golden prompts proving savings ≥ 0 and follow-mode correctness

### Phase 3 — Interval + media (v2.1)
- Interval deltas for document update sessions
- ffmpeg optional extra for large media
- Prompt-cache hints for providers that support it

### Phase 4 — Research track (v2.x optional)
- FAISS binary index prototype
- Full MIB bit selection benchmarks (recall@K vs float32)
- Publish numbers; only then market “info-theoretic layer”

---

## 11. Success metrics (definition of done for v2.0)

1. **Install:** New Windows user to first optimized chat in ≤ 3 minutes without reading code.
2. **Honesty:** On GVEB-style follow-attachment, model executes instructions; does not rewrite the spec as “help.”
3. **Savings:** Median saved_pct > 0 on attachment corpus ≥ 4k tokens; never silent overhead.
4. **Reliability:** Dead providers skipped in < 1s after Argus mark.
5. **Evidence:** Every default stage has a tokenizer unit test; vowel-shorthand tests assert *rejection*.

---

## 12. Explicit non-goals for v2.0

- Becoming a full RAG cloud platform
- Guaranteeing 40–70% savings on every prompt (market only measured medians)
- Requiring users to run Ollama
- Shipping proprietary Moorcheh code (keep open approximation + optional SDK)

---

## 13. Recommended immediate next step after your review

1. You approve / amend this plan (especially Approach B vs C).
2. Then we write a task-level implementation plan (`docs/superpowers/plans/...`).
3. Implement Phase 0–1 on a `v2` branch.
4. **Only then** commit/push when you say so.

---

## 14. One decision needed from you

**Packaging primary for v2.0 — which ship shape do you want first?**

| Option | What you get first |
|---|---|
| **A. pip + CLI only** | Fastest; `pip install tokenish` → `tokenish` |
| **B. Windows .exe first** | Double-click parity with Ollama Windows users |
| **C. Both in parallel** | Best UX, slightly slower |

Recommendation: **C if you can spare ~1 extra packaging day, else A then B immediately after.**
