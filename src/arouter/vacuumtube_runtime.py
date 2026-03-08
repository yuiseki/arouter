from __future__ import annotations

import json
import socket
from collections.abc import Callable
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


def ensure_vacuumtube_started_and_positioned(
    *,
    ensure_running: Callable[[], None],
    wait_window: Callable[[float], str],
    restart_tmux_session: Callable[[], None],
    wait_cdp_ready: Callable[[float], bool],
    select_account_if_needed: Callable[[], None],
    capture_window_presentation: Callable[[str], dict[str, Any]],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
    base_url: str,
) -> dict[str, Any]:
    ensure_running()
    try:
        win_id = wait_window(20.0)
    except Exception as err:
        log(f"VacuumTube window missing after startup; restarting session: {err}")
        restart_tmux_session()
        if not wait_cdp_ready(35.0):
            raise RuntimeError(f"VacuumTube CDP not ready at {base_url}") from err
        win_id = wait_window(20.0)

    select_account_if_needed()
    presentation = capture_window_presentation(win_id)
    if bool(presentation.get("fullscreen")):
        payload = json.dumps(presentation, ensure_ascii=False)
        log(f"VacuumTube window position preserved (fullscreen): {payload}")
        return presentation

    try:
        position = ensure_top_right_position()
        log(f"VacuumTube window position check: {json.dumps(position, ensure_ascii=False)}")
    except Exception as err:
        log(f"tile top-right skipped: {err}")

    return capture_window_presentation(win_id)
