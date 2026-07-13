"""
Optional Moorcheh cloud adapter (public SDK).

Uses https://github.com/moorcheh-ai/moorcheh-python-sdk when installed and
MOORCHEH_API_KEY is set. Local ITS decode always runs without this.
"""

from __future__ import annotations

from typing import Any

from tokenish_engine.config import settings


def moorcheh_available() -> bool:
    if not getattr(settings, "moorcheh_api_key", None):
        return False
    try:
        import moorcheh_sdk  # noqa: F401

        return True
    except Exception:
        return False


def search(
    query: str,
    namespaces: list[str],
    *,
    top_k: int = 10,
    threshold: float | None = None,
    kiosk_mode: bool = False,
) -> dict[str, Any]:
    """Proxy to Moorcheh Search.query (kiosk_mode + threshold semantics)."""
    if not moorcheh_available():
        return {"results": [], "execution_time": 0.0, "error": "moorcheh_sdk_or_key_missing"}

    from moorcheh_sdk import MoorchehClient

    client = MoorchehClient(api_key=settings.moorcheh_api_key)
    return client.search.query(
        namespaces=namespaces,
        query=query,
        top_k=top_k,
        threshold=threshold,
        kiosk_mode=kiosk_mode,
    )
