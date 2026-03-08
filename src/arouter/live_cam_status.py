from __future__ import annotations

import re
from typing import Any


def select_live_cam_page_url(targets: Any) -> str | None:
    if not isinstance(targets, list):
        return None
    for item in targets:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        url = str(item.get("url") or "")
        if "youtube.com/tv" in url:
            return url
    return None


def select_live_cam_page_target(targets: Any) -> dict[str, Any] | None:
    if not isinstance(targets, list):
        return None
    target: dict[str, Any] | None = None
    for item in targets:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        url = str(item.get("url") or "")
        if "youtube.com/tv" in url:
            return item
        if target is None:
            target = item
    return target


def build_live_cam_runtime_url_entry(
    *,
    port: int,
    targets_or_error: Any,
) -> dict[str, Any]:
    if isinstance(targets_or_error, Exception):
        return {"port": int(port), "error": str(targets_or_error)}
    return {"port": int(port), "url": select_live_cam_page_url(targets_or_error)}


def build_live_cam_page_brief(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": str(target.get("url") or ""),
        "title": str(target.get("title") or ""),
    }


def merge_live_cam_page_snapshot(
    brief: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
    inspect_error: Exception | None = None,
) -> dict[str, Any]:
    out = dict(brief)
    if inspect_error is not None:
        out["inspectError"] = str(inspect_error)
        return out
    if not isinstance(snapshot, dict):
        return out
    for key in ("title", "url", "hash", "bodyText", "watchText"):
        value = snapshot.get(key)
        if isinstance(value, str):
            out[key] = value
    return out


def page_matches_live_camera_spec(spec: dict[str, Any], page: dict[str, Any]) -> bool:
    url = str(page.get("url") or "")
    if "youtube.com/tv" not in url or "watch?v=" not in url:
        return False

    patterns: list[str] = []
    primary_pattern = (
        str(spec.get("verify_regex") or "").strip()
        or str(spec.get("keyword") or "").strip()
    )
    if primary_pattern:
        patterns.append(primary_pattern)
    for fallback in spec.get("fallbacks") or []:
        if not isinstance(fallback, dict):
            continue
        fallback_pattern = str(fallback.get("verify_regex") or "").strip() or str(
            fallback.get("keyword") or ""
        ).strip()
        if fallback_pattern:
            patterns.append(fallback_pattern)
    if not patterns:
        return True

    combined = " ".join(
        part
        for part in (
            str(page.get("title") or ""),
            str(page.get("watchText") or ""),
            str(page.get("bodyText") or ""),
        )
        if part
    )
    if not combined.strip():
        return False
    for pattern in patterns:
        try:
            if re.search(pattern, combined, flags=re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in combined.lower():
                return True
    return False


def find_stuck_live_cam_specs(
    specs: list[dict[str, Any]],
    *,
    pages_by_port: dict[int, dict[str, Any] | Exception],
) -> list[dict[str, Any]]:
    stuck: list[dict[str, Any]] = []
    for spec in specs:
        port = int(spec["port"])
        page_or_error = pages_by_port.get(port)
        if isinstance(page_or_error, Exception) or page_or_error is None:
            stuck.append(spec)
            continue
        if not page_matches_live_camera_spec(spec, page_or_error):
            stuck.append(spec)
    return stuck
