# Tokenish v2 Implementation Plan (pip → Windows exe)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Tokenish v2 as an Ollama-simple local optimizer: `pip install tokenish` → `tokenish` opens UI; then package a Windows `.exe`; evidence-based savings only (no vowel shorthand).

**Architecture:** Keep the FastAPI Split-Execution engine. Unify the public package as `tokenish` with a CLI that starts the daemon and opens the browser. Harden LCS with tokenizer gates (delete-don’t-abbreviate). Add first-run key wizard. After pip path works, freeze a PyInstaller Windows build.

**Tech Stack:** Python 3.10+, FastAPI/uvicorn, tiktoken, existing tokenish_engine modules, PyInstaller (Phase B only), pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-tokenish-v2-upgrade-plan.md`  
**Packaging order (locked):** A (pip + CLI) → B (Windows `.exe`)  
**Git rule:** Do **not** commit/push until the user explicitly approves. Plan steps that say “Commit” mean “stage locally and wait for user OK,” unless the user has already authorized commits.

---

## File map (create / modify)

| Path | Responsibility |
|---|---|
| `packages/engine/pyproject.toml` | Rename distribute as `tokenish`, scripts, version `2.0.0a1` |
| `packages/engine/tokenish_engine/cli.py` | `tokenish` / `tokenish serve` / `doctor` / `stop` / `version` |
| `packages/engine/tokenish_engine/__main__.py` | Delegate to CLI |
| `packages/engine/tokenish_engine/config.py` | User config dir + key storage paths |
| `packages/engine/tokenish_engine/settings_store.py` | Read/write keys outside repo `.env` |
| `packages/engine/tokenish_engine/compile/lcs.py` | Evidence-LCS; reject char shorthand; tokenizer gate helper |
| `packages/engine/tokenish_engine/compile/tokenizer_gate.py` | Keep transform only if tokens drop |
| `packages/engine/tokenish_engine/compile/format_rewrite.py` | Tabular JSON/list → CSV/pipe when cheaper |
| `packages/engine/tokenish_engine/history/summarize.py` | Rolling history compression |
| `packages/engine/tokenish_engine/pipeline.py` | Wire gates, format rewrite, cheapest envelope |
| `packages/engine/tokenish_engine/app.py` | `/settings/keys`, `/health`, open-friendly static |
| `packages/engine/tokenish_engine/static/*` | First-run key wizard + overhead TOKEX UI |
| `packages/engine/tests/test_tokenizer_gate.py` | Prove vowel shorthand rejected / deletion kept |
| `packages/engine/tests/test_cli.py` | CLI help / doctor / version |
| `packages/engine/tests/test_format_rewrite.py` | CSV cheaper than JSON for flat rows |
| `packages/engine/packaging/tokenish.spec` | PyInstaller spec (Phase B) |
| `packages/engine/packaging/build_windows.ps1` | One-shot exe build (Phase B) |
| `docs/download.md` | Ollama-like install page content |
| `README.md` | pip-first quick start |

---

### Task 1: Lock evidence rules into failing tests (TDD)

**Files:**
- Create: `packages/engine/tests/test_tokenizer_gate.py`
- Create: `packages/engine/tokenish_engine/compile/tokenizer_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
# packages/engine/tests/test_tokenizer_gate.py
from tokenish_engine.compile.tokenizer_gate import apply_if_cheaper, reject_char_shorthand
from tokenish_engine.meters.tokens import count_tokens


def test_vowel_shorthand_increases_tokens_and_is_rejected():
    original = "Build a token optimization framework that saves tokens"
    bad = "Bld a tkn optmztn frmwrk tht svs tkns"
    assert count_tokens(bad) >= count_tokens(original)
    assert reject_char_shorthand(bad) is True


def test_filler_deletion_is_kept_when_cheaper():
    original = "Please could you kindly help me summarize the key points"
    cleaned = "Summarize the key points"
    out = apply_if_cheaper(original, cleaned)
    assert out == cleaned
    assert count_tokens(out) < count_tokens(original)


def test_apply_if_cheaper_keeps_original_on_tie_or_worse():
    text = "hello world"
    assert apply_if_cheaper(text, text + " !!!") == text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
Set-Location "c:\Users\admin\Desktop\TOKISH\tokenish\packages\engine"
.\.venv\Scripts\python -m pytest tests\test_tokenizer_gate.py -v
```
Expected: FAIL (module/import missing)

- [ ] **Step 3: Minimal implementation**

```python
# packages/engine/tokenish_engine/compile/tokenizer_gate.py
from __future__ import annotations
import re
from tokenish_engine.meters.tokens import count_tokens

_VOWEL_STRIP_HINT = re.compile(r"\b[b-df-hj-np-tv-z]{4,}\b", re.I)

def reject_char_shorthand(text: str) -> bool:
    """True if text looks like vowel-stripped stenography (forbidden)."""
    if not text:
        return False
    # Heuristic: many long consonant-only tokens vs normal English
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 3:
        return False
    strippedish = sum(1 for w in words if _VOWEL_STRIP_HINT.fullmatch(w) and not re.search(r"[aeiouy]", w, re.I))
    return strippedish / max(1, len(words)) >= 0.35


def apply_if_cheaper(before: str, after: str) -> str:
    if count_tokens(after) < count_tokens(before):
        return after
    return before
```

- [ ] **Step 4: Run tests to verify they pass**

Run: same pytest command  
Expected: PASS

- [ ] **Step 5: Commit (only if user authorized)**

```powershell
# DO NOT RUN until user says commit
git add packages/engine/tokenish_engine/compile/tokenizer_gate.py packages/engine/tests/test_tokenizer_gate.py
git commit -m "test: gate transforms by tokenizer cost; reject char shorthand"
```

---

### Task 2: Wire evidence-LCS (no vowel shorthand)

**Files:**
- Modify: `packages/engine/tokenish_engine/compile/lcs.py`
- Modify: `packages/engine/tokenish_engine/pipeline.py`
- Modify: `packages/engine/tests/test_pipeline.py`

- [ ] **Step 1: Add failing test for LCS never emitting stenography**

```python
def test_compress_instructions_never_strips_vowels():
    from tokenish_engine.compile import compress_instructions
    nodes = compress_instructions("Please analyze the attached financial framework document")
    blob = " ".join(nodes.values())
    assert "frmwrk" not in blob
    assert "optmztn" not in blob
    assert "please" not in nodes["clean_prompt"].lower()
```

- [ ] **Step 2: Run to confirm current behavior / fail if needed**

Run:
```powershell
.\.venv\Scripts\python -m pytest tests\test_pipeline.py::test_compress_instructions_never_strips_vowels -v
```

- [ ] **Step 3: Update `compress_instructions` to use word-level filler deletion only; after building envelope candidates, run `apply_if_cheaper` against naive baseline in `pipeline.optimize` (already has `pick_cheapest_envelope` — ensure every candidate loses to baseline only if truly cheaper, else fall back to `bare`).**

Key pipeline rule to enforce in `optimize()`:

```python
from tokenish_engine.compile.tokenizer_gate import apply_if_cheaper, reject_char_shorthand

# after picking envelope:
if reject_char_shorthand(envelope):
    envelope = naive_baseline_prompt(prompt, original_doc or raw_doc)
envelope = apply_if_cheaper(naive_baseline_prompt(prompt, original_doc or ""), envelope)
```

- [ ] **Step 4: Run full pipeline tests**

```powershell
.\.venv\Scripts\python -m pytest tests\test_pipeline.py tests\test_tokenizer_gate.py -q
```
Expected: all PASS

- [ ] **Step 5: Commit only if authorized**

---

### Task 3: Format rewrite for flat tabular `#D`

**Files:**
- Create: `packages/engine/tokenish_engine/compile/format_rewrite.py`
- Create: `packages/engine/tests/test_format_rewrite.py`
- Modify: `packages/engine/tokenish_engine/pipeline.py`
- Modify: `packages/engine/tokenish_engine/compile/__init__.py`

- [ ] **Step 1: Failing tests**

```python
# packages/engine/tests/test_format_rewrite.py
import json
from tokenish_engine.compile.format_rewrite import maybe_tabular_cheaper
from tokenish_engine.meters.tokens import count_tokens

def test_list_of_dicts_becomes_csv_when_cheaper():
    rows = [{"name": "John Smith", "age": 34, "city": "Toronto"} for _ in range(20)]
    raw = json.dumps(rows)
    out, applied = maybe_tabular_cheaper(raw)
    assert applied is True
    assert count_tokens(out) < count_tokens(raw)
    assert "John Smith" in out

def test_nested_json_left_alone():
    raw = json.dumps({"a": {"b": [1, {"c": 2}]}})
    out, applied = maybe_tabular_cheaper(raw)
    assert applied is False
    assert out == raw
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# packages/engine/tokenish_engine/compile/format_rewrite.py
from __future__ import annotations
import csv
import io
import json
from tokenish_engine.compile.tokenizer_gate import apply_if_cheaper

def maybe_tabular_cheaper(text: str) -> tuple[str, bool]:
    stripped = (text or "").strip()
    if not stripped.startswith("["):
        return text, False
    try:
        data = json.loads(stripped)
    except Exception:
        return text, False
    if not isinstance(data, list) or not data or not all(isinstance(x, dict) for x in data):
        return text, False
    keys = list(data[0].keys())
    if not keys or any(set(x.keys()) != set(keys) for x in data):
        return text, False
    if any(isinstance(v, (dict, list)) for row in data for v in row.values()):
        return text, False
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, lineterminator="\n")
    w.writeheader()
    w.writerows(data)
    csv_text = buf.getvalue()
    cheaper = apply_if_cheaper(text, csv_text)
    return cheaper, cheaper != text
```

- [ ] **Step 4: Call from `pipeline.optimize` after ingest, before ITS, only when `data_type in {"json","txt"}` and not `follow_mode` for free-form PDFs; for pure JSON attachments always try.**

- [ ] **Step 5: pytest pass; commit only if authorized**

---

### Task 4: User settings store + API for keys

**Files:**
- Create: `packages/engine/tokenish_engine/settings_store.py`
- Modify: `packages/engine/tokenish_engine/config.py`
- Modify: `packages/engine/tokenish_engine/app.py`
- Create: `packages/engine/tests/test_settings_store.py`

- [ ] **Step 1: Failing test**

```python
from pathlib import Path
from tokenish_engine.settings_store import save_keys, load_keys

def test_save_and_load_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKENISH_HOME", str(tmp_path))
    save_keys({"GPT_TOKENISH": "sk-test", "GEMINI_API_KEY": "gem-test"})
    data = load_keys()
    assert data["GPT_TOKENISH"] == "sk-test"
    assert (tmp_path / "config.json").exists()
```

- [ ] **Step 2: Implement store**

```python
# packages/engine/tokenish_engine/settings_store.py
from __future__ import annotations
import json
import os
from pathlib import Path

def tokenish_home() -> Path:
    raw = os.environ.get("TOKENISH_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".tokenish"

def config_path() -> Path:
    return tokenish_home() / "config.json"

def load_keys() -> dict[str, str]:
    p = config_path()
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in (data.get("keys") or {}).items() if v}

def save_keys(keys: dict[str, str]) -> Path:
    home = tokenish_home()
    home.mkdir(parents=True, exist_ok=True)
    path = config_path()
    existing = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    merged = dict(existing.get("keys") or {})
    for k, v in keys.items():
        if v:
            merged[k] = v
    existing["keys"] = merged
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return path
```

- [ ] **Step 3: On app startup / config load, merge `load_keys()` into `os.environ` if env var missing.**

- [ ] **Step 4: Add FastAPI routes**

```python
@app.get("/settings/keys")
def get_key_status():
    keys = load_keys()
    return {
        "openai": bool(keys.get("GPT_TOKENISH") or keys.get("OPENAI_API_KEY")),
        "gemini": bool(keys.get("GEMINI_API_KEY") or keys.get("GOOGLE_API_KEY")),
        "openrouter": bool(keys.get("OPENROUTER_API_KEY")),
        "home": str(tokenish_home()),
    }

@app.post("/settings/keys")
async def set_keys(payload: dict):
    save_keys({k: v for k, v in payload.items() if isinstance(v, str)})
    # refresh process env for current process
    for k, v in load_keys().items():
        os.environ.setdefault(k, v)
    return {"ok": True}
```

- [ ] **Step 5: Tests pass; commit only if authorized**

---

### Task 5: First-run key wizard in UI

**Files:**
- Modify: `packages/engine/tokenish_engine/static/index.html`
- Modify: `packages/engine/tokenish_engine/static/app.js`
- Modify: `packages/engine/tokenish_engine/static/styles.css`

- [ ] **Step 1: On load, `GET /settings/keys`. If no openai and no gemini, show modal: paste Gemini and/or OpenAI key → `POST /settings/keys` → dismiss.**

- [ ] **Step 2: Keep TOKEX overhead label (already started in `app.js`).**

- [ ] **Step 3: Manual check**

```powershell
.\.venv\Scripts\python -m tokenish_engine
# open UI, clear keys temporarily via TOKENISH_HOME temp dir, confirm wizard
```

- [ ] **Step 4: Commit only if authorized**

---

### Task 6: `tokenish` CLI (pip path — packaging A)

**Files:**
- Create: `packages/engine/tokenish_engine/cli.py`
- Modify: `packages/engine/tokenish_engine/__main__.py`
- Modify: `packages/engine/pyproject.toml`
- Create: `packages/engine/tests/test_cli.py`

- [ ] **Step 1: Failing CLI tests using typer-less argparse**

```python
from tokenish_engine.cli import build_parser

def test_parser_has_serve_doctor_version():
    p = build_parser()
    assert p.parse_args(["version"]).cmd == "version"
    assert p.parse_args(["doctor"]).cmd == "doctor"
    assert p.parse_args(["serve"]).cmd == "serve"
```

- [ ] **Step 2: Implement CLI**

```python
# packages/engine/tokenish_engine/cli.py
from __future__ import annotations
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from tokenish_engine import __version__
from tokenish_engine.settings_store import load_keys, tokenish_home

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8741

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tokenish")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("serve")
    sub.add_parser("doctor")
    sub.add_parser("version")
    sub.add_parser("stop")
    p.set_defaults(cmd="serve", open_browser=True)
    serve = sub.choices.get("serve")
    # also allow: tokenish  (no subcommand) => serve + open
    return p

def port_open(host: str, port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0

def apply_saved_keys() -> None:
    for k, v in load_keys().items():
        os.environ.setdefault(k, v)

def cmd_doctor() -> int:
    apply_saved_keys()
    print(f"tokenish {__version__}")
    print(f"home: {tokenish_home()}")
    print(f"openai key: {'yes' if os.getenv('GPT_TOKENISH') or os.getenv('OPENAI_API_KEY') else 'no'}")
    print(f"gemini key: {'yes' if os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') else 'no'}")
    print(f"port {DEFAULT_PORT}: {'in use' if port_open(DEFAULT_HOST, DEFAULT_PORT) else 'free'}")
    return 0

def cmd_serve(*, open_browser: bool = True) -> int:
    apply_saved_keys()
    if open_browser:
        def _open():
            for _ in range(50):
                if port_open(DEFAULT_HOST, DEFAULT_PORT):
                    webbrowser.open(f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/")
                    return
                time.sleep(0.1)
        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run("tokenish_engine.app:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)
    return 0

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return cmd_serve(open_browser=True)
    # allow `tokenish version` etc.
    if argv[0] in {"serve", "doctor", "version", "stop"}:
        cmd = argv[0]
    else:
        # default
        return cmd_serve(open_browser=True)
    if cmd == "version":
        print(__version__)
        return 0
    if cmd == "doctor":
        return cmd_doctor()
    if cmd == "stop":
        print("Stop the process from the terminal (Ctrl+C) or Task Manager.")
        return 0
    return cmd_serve(open_browser=False if "--no-browser" in argv else True)
```

- [ ] **Step 3: Update `pyproject.toml`**

```toml
[project]
name = "tokenish"
version = "2.0.0a1"
description = "Local token optimizer daemon — Ollama-simple install"

[project.scripts]
tokenish = "tokenish_engine.cli:main"
tokenish-engine = "tokenish_engine.cli:main"
```

Also bump `__version__` in `tokenish_engine/__init__.py` to `2.0.0a1`.

- [ ] **Step 4: Reinstall editable and smoke**

```powershell
.\.venv\Scripts\pip install -e .
.\.venv\Scripts\tokenish doctor
.\.venv\Scripts\tokenish version
```
Expected: prints version + key status

- [ ] **Step 5: Commit only if authorized**

---

### Task 7: README + download docs (Ollama-shaped)

**Files:**
- Modify: `README.md`
- Create: `docs/download.md`
- Modify: `docs/architecture.md` (remove stale “Ollama required” wording; clarify optional)

- [ ] **Step 1: Rewrite README quick start to:**

```bash
pip install tokenish
tokenish
```

Windows note: open http://127.0.0.1:8741/ if browser doesn’t auto-open.

- [ ] **Step 2: `docs/download.md` with tabs-style sections: Windows / macOS / Linux / pip — pip complete now; exe “coming in Phase B”. Link [Ollama-style simplicity](https://ollama.com/download) as UX reference only.**

- [ ] **Step 3: Commit only if authorized**

---

### Task 8: History summarization (v2.0 evidence win)

**Files:**
- Create: `packages/engine/tokenish_engine/history/__init__.py`
- Create: `packages/engine/tokenish_engine/history/summarize.py`
- Create: `packages/engine/tests/test_history.py`
- Modify: `packages/engine/tokenish_engine/app.py` chat handlers to compress history before dispatch

- [ ] **Step 1: Test**

```python
from tokenish_engine.history.summarize import compress_history

def test_long_history_is_shortened():
    hist = [{"role": "user", "content": "x"*500}, {"role": "assistant", "content": "y"*500}] * 6
    out = compress_history(hist, max_tokens=800)
    from tokenish_engine.meters.tokens import count_tokens
    joined = "\n".join(m["content"] for m in out)
    assert count_tokens(joined) <= 900
    assert out[-1]["role"] in {"user", "assistant"}
```

- [ ] **Step 2: Implement keep-last-N + prepend one summary bullet list of dropped turns (local extractive: first 200 chars each), gated by `apply_if_cheaper` on serialized history.**

- [ ] **Step 3: Wire into chat_complete / chat_stream call sites in `app.py`.**

- [ ] **Step 4: pytest; commit only if authorized**

---

### Task 9: Phase A acceptance gate

- [ ] **Step 1: Fresh venv install simulation**

```powershell
cd c:\Users\admin\Desktop\TOKISH\tokenish\packages\engine
py -3.12 -m venv .venv-v2check
.\.venv-v2check\Scripts\pip install -e .
.\.venv-v2check\Scripts\tokenish doctor
.\.venv-v2check\Scripts\tokenish
```

- [ ] **Step 2: Checklist**
  - [ ] Browser opens or URL printed
  - [ ] Key wizard appears when no keys
  - [ ] Attach ~5k text + “follow instructions…” → saved_pct ≥ 0 and not overhead-only
  - [ ] `pytest` green

- [ ] **Step 3: User reviews Phase A. Only after OK → start Phase B.**

---

### Task 10: Windows `.exe` (packaging B)

**Files:**
- Create: `packages/engine/packaging/tokenish.spec`
- Create: `packages/engine/packaging/build_windows.ps1`
- Modify: `docs/download.md` (Windows exe section live)

- [ ] **Step 1: Add PyInstaller dev extra**

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "pyinstaller>=6.0.0"]
```

- [ ] **Step 2: `tokenish.spec` entry `tokenish_engine.cli:main`, collect `tokenish_engine/static` datas.**

```python
# packaging/tokenish.spec (PyInstaller)
a = Analysis(
    ['../tokenish_engine/__main__.py'],
    pathex=[],
    datas=[('../tokenish_engine/static', 'tokenish_engine/static')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops', 'uvicorn.protocols'],
)
```

- [ ] **Step 3: Build script**

```powershell
# packages/engine/packaging/build_windows.ps1
Set-Location $PSScriptRoot\..
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\pyinstaller packaging\tokenish.spec --noconfirm
Write-Host "exe at dist\tokenish\tokenish.exe"
```

- [ ] **Step 4: Manual run `dist\tokenish\tokenish.exe doctor` then `tokenish.exe` — UI loads, keys persist under `%USERPROFILE%\.tokenish`.**

- [ ] **Step 5: Update `docs/download.md` with “Download for Windows” placeholder path/release asset naming `tokenish-windows.zip`.**

- [ ] **Step 6: Commit/release only when user authorizes.**

---

### Task 11: Explicit non-work (do not implement in this plan)

- Vowel-removal shorthand module
- FAISS / full MIB vector stack
- Electron/Tauri shell
- ffmpeg stage (defer to v2.1)
- Interval document diffs (defer to v2.1)
- GitHub push until user says so

---

## Self-review

| Spec requirement | Task |
|---|---|
| Reject char shorthand | Task 1–2 |
| Evidence LCS / tokenizer gate | Task 1–2 |
| CSV/pipe format rewrite | Task 3 |
| pip + CLI first | Task 6–7, 9 |
| Windows exe second | Task 10 |
| First-run keys | Task 4–5 |
| History management | Task 8 |
| Honest TOKEX | Task 5 (UI) + existing pipeline |
| Ollama-like docs | Task 7 |
| No GitHub until approved | Header + every commit step |

---

## Execution handoff

Plan complete and saved to:

`docs/superpowers/plans/2026-07-13-tokenish-v2-pip-then-exe.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with checkpoints  

**Which approach?**  

(Still no GitHub commit/push until you explicitly say so.)
