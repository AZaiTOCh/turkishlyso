# Cylinder Register (OptComp)

**Tokopt** = Token Optimization. A **tokopt cylinder** is one working stage inside **OptComp**.

| # | Cylinder | Status | Since |
|---|----------|--------|-------|
| 1 | [ingest](INGEST.md) | ON w/ files | v0.1 |
| 2 | [LCS](LCS.md) | ON | v0.1 |
| 3 | [split-exec / envelope](SPLIT_EXEC.md) | ON w/ material | v0.1 |
| 4 | [Hi0](HI0.md) | ON when JSON-ish | v0.2 |
| 5 | [dedupe](DEDUPE.md) | ON when doc text | v0.2 |
| 6 | [format_csv](FORMAT_CSV.md) | situational | v0.2 |
| 7 | [headroom](HEADROOM.md) | ON (gated) | v0.2 |
| 8 | [ITS](ITS.md) | OFF (consent) | v0.2 |
| 9 | [FAISS / MIB](FAISS_MIB.md) | standby w/ ITS | v0.2 |
| 10 | [pxpipe](PXPIPE.md) | OFF | v0.1–v0.2 |
| 11 | [tokenizer gate](TOKENIZER_GATE.md) | ON | v0.2 |
| 12 | [vision (Pillow)](VISION.md) | ON w/ images | v0.1 |
| 13 | [passthrough](PASSTHROUGH.md) | ON when triggered | v0.1 |
| 14 | [ffmpeg / Clop media](FFMPEG.md) | **ON** (disable with `enable_ffmpeg=false`) | v0.4.3 / ON v0.4.4 |
| 15 | [Memtrove](MEMTROVE.md) | not in optimize path | probe v0.2 |

## Rejected / parked

| # | Item | Status |
|---|------|--------|
| 1 | [Alcubierre](REJECTED_ALCUBIERRE.md) | rejected |
| 2 | [Latents](PARKED_LATENTS.md) | parked |
