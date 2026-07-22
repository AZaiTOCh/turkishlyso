# Cylinder Register (OptComp)

**Tokopt** = Token Optimization. A **tokopt cylinder** is one working stage inside **OptComp**.

| Cylinder | Default | Incepted |
|----------|---------|----------|
| [ingest](INGEST.md) | ON w/ files | v0.1 |
| [LCS](LCS.md) | ON | v0.1 |
| [split-exec / envelope](SPLIT_EXEC.md) | ON w/ material | v0.1 |
| [Hi0](HI0.md) | ON when JSON-ish | v0.2 |
| [dedupe](DEDUPE.md) | ON when doc text | v0.2 |
| [format_csv](FORMAT_CSV.md) | situational | v0.2 |
| [headroom](HEADROOM.md) | ON (gated) | v0.2 |
| [ITS](ITS.md) | OFF (consent) | v0.2 |
| [FAISS / MIB](FAISS_MIB.md) | standby w/ ITS | v0.2 |
| [pxpipe](PXPIPE.md) | OFF | v0.1–v0.2 |
| [tokenizer gate](TOKENIZER_GATE.md) | ON | v0.2 |
| [vision (Pillow)](VISION.md) | ON w/ images | v0.1 |
| [passthrough](PASSTHROUGH.md) | ON when triggered | v0.1 |
| [ffmpeg / Clop media](FFMPEG.md) | **ON** (disable with `enable_ffmpeg=false`) | v0.4.3 · ON v0.4.4 |
| [Memtrove](MEMTROVE.md) | not in optimize path | probe v0.2 |

**Rejected / parked:** [Alcubierre](REJECTED_ALCUBIERRE.md) · [Latents](PARKED_LATENTS.md)
