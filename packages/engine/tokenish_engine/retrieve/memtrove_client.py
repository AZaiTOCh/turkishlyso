"""
Optional Memtrove cloud adapter (public SDK when available).

Local ITS / MIB / FAISS always run without this.
Env: MEMTROVE_API_KEY (legacy alias MOORCHEH_API_KEY still accepted).
"""

from __future__ import annotations

from typing import Any

from tokenish_engine.config import memtrove_key, settings


def memtrove_available() -> bool:
    if not memtrove_key():
        return False
    try:
        import moorcheh_sdk  # noqa: F401  # upstream package name until Memtrove SDK ships

        return True
    except Exception:
        return False


# Back-compat alias
moorcheh_available = memtrove_available


def search(
    query: str,
    namespaces: list[str],
    *,
    top_k: int = 10,
    threshold: float | None = None,
    kiosk_mode: bool = False,
) -> dict[str, Any]:
    """Proxy to Memtrove/compatible Search.query when SDK is installed."""
    if not memtrove_available():
        return {"results": [], "execution_time": 0.0, "error": "memtrove_sdk_or_key_missing"}

    from moorcheh_sdk import MoorchehClient

    client = MoorchehClient(api_key=memtrove_key() or settings.memtrove_api_key)
    return client.search.query(
        namespaces=namespaces,
        query=query,
        top_k=top_k,
        threshold=threshold,
        kiosk_mode=kiosk_mode,
    )
