# Tokenish Engine

FastAPI Split-Execution / tokopt optimizer (**v0.4.1**).

```bash
pip install -e ".[dev]"
uvicorn tokenish_engine.app:app --port 8741
```

Main endpoints: `GET /health`, `GET /providers`, `GET /settings/keys`, `POST /settings/keys`, `POST /compile`, `POST /chat`, `GET /tokex-clock`, `POST /tokex-clock/sync`, `POST /tokex-clock/opt-in`, `POST /hive/contribute`.

Agents live under `tokenish_engine/agents/` (Mumblz, Rainman, Agatha, Mrs. Brown, NeoBorg, tokex_clock). Hive store: `hive_store.py`. Worldwide Worker scaffold: `../tokex-clock/`.

See root [README.md](../../README.md) and [VERSION_LOG.md](VERSION_LOG.md).
