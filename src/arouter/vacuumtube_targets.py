from __future__ import annotations

from typing import Any


def select_vacuumtube_page_target(targets: Any) -> dict[str, Any] | None:
    if not isinstance(targets, list):
        return None

    first_page: dict[str, Any] | None = None
    titled_candidate: dict[str, Any] | None = None
    for item in targets:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        url = str(item.get("url") or "")
        title = str(item.get("title") or "")
        if "youtube.com/tv" in url:
            return item
        if titled_candidate is None and ("VacuumTube" in title or "YouTube" in title):
            titled_candidate = item
        if first_page is None:
            first_page = item
    return titled_candidate or first_page


def select_vacuumtube_websocket_url(target: Any) -> str | None:
    if not isinstance(target, dict):
        return None
    ws_url = target.get("webSocketDebuggerUrl")
    if not isinstance(ws_url, str) or not ws_url:
        return None
    return ws_url
