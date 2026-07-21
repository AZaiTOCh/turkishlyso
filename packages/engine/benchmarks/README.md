# tokenish benchmark corpora (P0 measurement scaffold)

Peer reviews of v0.4.2 asked for sealed-run corpora before datacenter / headline claims.
This folder is the **scaffold** — add fixtures over time; do not invent SAVED_PCT here.

## Workload classes

| Class | Purpose | Fidelity bar |
|-------|---------|--------------|
| `redundant_pdf/` | Duplicated pages / paste clones | Dedupe OK |
| `verbose_json/` | API dumps / CRM exports | Structure-preserving |
| `logs/` | Telemetry / debug dumps | Soft headroom OK |
| `chat_parity/` | Bare prompts | Must stay ~0% |
| `legal_fidelity/` | Loyalty stress | Prefer mutators OFF |
| `science_fidelity/` | Loyalty stress | Prefer mutators OFF |
| `vision_caps/` | Multi-image near provider limits | Bilateral vision billing |
| `media_gif_mp4/` | ffmpeg cylinder thesis | Consent-gated lossy sample |

## Required metrics per sealed run

- `TOTAL_TOKEX`, `TOKEX_THIS_RUN`, `SAVED_TOKEX`, `SAVED_PCT`
- stages[] + Rainman `attribution_mode` (`sequential_delta` | `equal_share`)
- optional human fidelity note: pass / fail / n/a

## Honesty

Never commit fabricated lifetime averages. Agatha/Neoborg local ledgers are the source of truth after real runs.
