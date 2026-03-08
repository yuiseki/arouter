from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_vacuumtube_context_error(
    *,
    ts: float,
    error: Exception | str,
) -> dict[str, Any]:
    return {
        "ts": float(ts),
        "available": False,
        "error": str(error),
    }


def resolve_vacuumtube_context_cache(
    cached: dict[str, Any],
    *,
    now_ts: float,
    max_age_sec: float,
    refresh_if_stale: bool,
    refresh_context: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    snapshot = dict(cached)
    ts = float(snapshot.get("ts") or 0.0)
    age = now_ts - ts if ts > 0 else 1e9
    if age <= max(0.0, float(max_age_sec)):
        return snapshot
    if refresh_if_stale:
        return refresh_context()
    return snapshot
