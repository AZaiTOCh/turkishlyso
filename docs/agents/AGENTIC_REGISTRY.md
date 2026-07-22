# Agentic Registry (tokenish)

Canonical roster for **agentics** (Engineship + Status). Append role history in each profile; **do not invent TOKEX savings**.

**Measured** = sealed Agatha / Rainman numbers from real runs. **Unknown** = not measured / not invented.

| # | Agentic | Engineship | Status | Role | Agent-attributable TOKEX | Since |
|---|---------|------------|--------|------|--------------------------|-------|
| 1 | [Argus](ARGUS.md) | Agent | Plug-in | Provider health / failover | Unknown (dispatch — no OptComp compression) | v0.1 |
| 2 | [Mumblz](MUMBLZ.md) | Resgent | Reserve | History chat titles (2 lowercase words) | Unknown (UX titles — no OptComp compression) | v0.2 |
| 3 | [Rainman](RAINMAN.md) | Resgent | Reserve | Factual cylinder + TOKEX interrogation (0 LLM) | Unknown as *cause* — attributes cylinder deltas after the run | v0.3 |
| 4 | [Agatha](AGATHA.md) | Agent | Plug-in | Local archive of Rainman briefs | Unknown (archives measures; does not compress) | v0.3 |
| 5 | [Mrs. Brown](MRS_BROWN.md) | Resgent | Reserve | Numeric TOKEX intake gate | Unknown (gate only) | v0.3 |
| 6 | [Neoborg](NEOBORG.md) | Resgent | Resident | Cross-vet + Live World Counter broadcast | Unknown (hive bookkeeping) | v0.3 |
| 7 | [Gretta](GRETTA.md) | Resgent | Reserve | Onboarding + curated LLM router | Unknown (routing / suitability UX) | v0.4.1 |
| 8 | [ZamanZamin](ZAMANZAMIN.md) | Resgent | Resident | Live World Counter client module | Unknown (clock / hive sync) | v0.3.1 |

### Engineship (like citizenship, for agentics)

| Value | Meaning |
|-------|---------|
| **Agent** | General / migrated agentic pattern — may have entered as a plug-in or archive-style module; not yet fully specialized as a mother-codebase resgent |
| **Resgent** | Native agentic form — leaner, tighter coupling to this engine (see [RESGENTS](RESGENTS.md)) |

### Status

| Value | Meaning |
|-------|---------|
| **Plug-in** | Migrant / bolt-on style relative to the mother tree (or archive/dispatch sibling); can evolve toward Resident resgent if finetuned for this engine |
| **Reserve** | Callable specialist orientation — intended to spawn/activate on demand from the mother codebase (runtime spawn API still landing) |
| **Resident** | Always-present specialist programmed into the mother engine path |

**Evolution (product law):** Plug-in → Resident resgent (if optimized for this engine) · Resident → Reserve resgent (if code/KG is specialized enough to spawn lean). Engineship may flip Agent → Resgent on the same path.

### What actually saves tokens (engineering fact)

**OptComp / [vTOPU](../cylinders/CYLINDER_REGISTER.md) cylinders** reduce TOKEX (Hi0/*Highzero*, dedupe, ITS, ffmpeg/Fidelvid, etc.). Agentics above mostly **measure, gate, route, title, or broadcast** — they do **not** currently have sealed, agent-attributable savings % in VERSION_LOG or committed Agatha scoreboards.

**Hi0** is a **cylinder** (*Highzero*), not a registry agentic — Plug-in-migrant *pattern* at the OptComp layer. See [HI0](../cylinders/HI0.md).

**Privacy Middleware (TOKISH):** [Nemean](../middleware/NEMEAN.md) — not an agentic; Engineship N/A.

Code: `packages/engine/tokenish_engine/agents/` (+ Argus under `dispatch/`)

> Formerly: Agent Registry / Resgent Registry → **Agentic Registry**.
