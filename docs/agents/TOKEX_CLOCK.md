# tokex_clock (Live World Counter client)

**Role:** Opt-in sync/fetch client for the global TOKEX hive panel.

**Code:** `packages/engine/tokenish_engine/agents/tokex_clock.py`  
**Hive store:** `packages/engine/tokenish_engine/hive_store.py`  
**Worker scaffold:** `packages/tokex-clock/`

**Owns:** opt-in, sync, contribute payloads.  
**Must not:** double-count without policy; invent global averages.

**Incepted:** v0.3.1 (Clock) · renamed Live World Counter **v0.4**
