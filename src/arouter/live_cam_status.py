from __future__ import annotations

import re
from typing import Any


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
