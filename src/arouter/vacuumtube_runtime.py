from __future__ import annotations

import socket
from typing import Any

from .vacuumtube_state import vacuumtube_is_watch_state


def build_vacuumtube_context_base(*, ts: float) -> dict[str, Any]:
    return {
        "ts": float(ts),
        "available": False,
        "windowFound": False,
        "fullscreenish": False,
        "quadrantish": False,
        "watchRoute": False,
        "homeRoute": False,
        "videoPlaying": False,
        "videoPaused": None,
    }


def merge_vacuumtube_window_snapshot(
    context: dict[str, Any],
    *,
    window_id: str | None,
    geom: dict[str, Any] | None,
    fullscreenish: bool,
    quadrantish: bool,
) -> dict[str, Any]:
    merged = dict(context)
    merged["quadrantish"] = bool(quadrantish)
    if not window_id:
        return merged

    merged["windowFound"] = True
    if isinstance(geom, dict):
        merged["geom"] = {
            "x": int(geom.get("x") or 0),
            "y": int(geom.get("y") or 0),
            "w": int(geom.get("w") or 0),
            "h": int(geom.get("h") or 0),
        }
    merged["fullscreenish"] = bool(fullscreenish)
    return merged


def merge_vacuumtube_cdp_state(
    context: dict[str, Any],
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(context)
    if not isinstance(state, dict):
        return merged

    hash_value = str(state.get("hash") or "")
    merged["hash"] = hash_value
    merged["watchRoute"] = vacuumtube_is_watch_state(state)
    merged["homeRoute"] = hash_value == "#/"

    video = state.get("video")
    if isinstance(video, dict):
        paused = bool(video.get("paused", True))
        merged["videoPaused"] = paused
        merged["videoPlaying"] = not paused

    merged["accountSelectHint"] = bool(state.get("accountSelectHint"))
    merged["homeHint"] = bool(state.get("homeHint"))
    merged["watchUiHint"] = bool(state.get("watchUiHint"))
    return merged


def finalize_vacuumtube_context(context: dict[str, Any]) -> dict[str, Any]:
    finalized = dict(context)
    finalized["available"] = bool(finalized.get("windowFound")) or bool(finalized.get("hash"))
    return finalized


def is_recoverable_vacuumtube_error(
    err: Exception,
    *,
    timeout_exception_type: type[BaseException] | None = None,
) -> bool:
    if isinstance(err, (TimeoutError, socket.timeout)):
        return True
    if timeout_exception_type and isinstance(err, timeout_exception_type):
        return True

    msg = str(err or "").lower()
    return any(
        token in msg
        for token in (
            "timed out",
            "cdp not ready",
            "vacuumtube window not found",
            "no vacuumtube/youtube tv page target",
            "websocket is already closed",
            "broken pipe",
            "connection reset",
            "connection refused",
        )
    )
