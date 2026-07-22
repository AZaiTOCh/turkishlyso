# Tokenish Engine

FastAPI Split-Execution / tokopt optimizer (**v0.4.4**).

```bash
pip install -e ".[dev]"
uvicorn tokenish_engine.app:app --port 8741
```

Main endpoints: `GET /health`, `GET /providers`, `GET /settings/keys`, `POST /settings/keys`, `POST /compile`, `POST /chat`, `GET /tokex-clock`, `POST /tokex-clock/sync`, `POST /tokex-clock/opt-in`, `POST /hive/contribute`.

Optional form flags on `/chat` and `/compile`: `enable_its`, `enable_ffmpeg` (both default off).

**ffmpeg:** install a build from [ffmpeg.org/download](https://www.ffmpeg.org/download.html) (Windows: gyan.dev or BtbN). Set `TOKENISH_FFMPEG` to the `ffmpeg.exe` path or put it on `PATH`.

Agents live under `tokenish_engine/agents/` (Mumblz, Rainman, Agatha, Mrs. Brown, Neoborg, Gretta, tokex_clock). Media cylinder: `tokenish_engine/media/`. Hive store: `hive_store.py`. Worldwide Worker scaffold: `../tokex-clock/`.

Version chronology (newest → oldest), neologisms, and DoP: [VERSION_LOG.md](VERSION_LOG.md).  
Agent + cylinder docs (linked profiles): [Agent Registry](../../docs/agents/AGENT_REGISTRY.md) · [Cylinder Register](../../docs/cylinders/CYLINDER_REGISTER.md).  
Root overview: [README.md](../../README.md) · GitHub: https://github.com/tknsh/tokenish
