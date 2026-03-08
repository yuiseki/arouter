from __future__ import annotations

import re
from typing import Any


def expand_live_cam_candidates(spec: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [dict(spec)]
    for fallback in spec.get("fallbacks") or []:
        if not isinstance(fallback, dict):
            continue
        merged = dict(spec)
        merged.update(fallback)
        merged.pop("fallbacks", None)
        candidates.append(merged)
    return candidates


def normalize_live_cam_force_video_id(candidate: dict[str, Any]) -> str:
    force_video_id = str(candidate.get("force_video_id") or "")
    if force_video_id and re.match(r"^[A-Za-z0-9_-]{11}$", force_video_id):
        return force_video_id
    return ""


def web_watch_retry_video_id(payload: dict[str, Any]) -> str:
    if str(payload.get("method") or "") != "web-streams-fallback-web-watch":
        return ""
    video_id = str(payload.get("videoId") or "")
    if video_id and re.match(r"^[A-Za-z0-9_-]{11}$", video_id):
        return video_id
    return ""


def annotate_live_cam_payload_selection(
    payload: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    payload.setdefault("selectedKeyword", str(candidate.get("keyword") or ""))
    payload.setdefault("selectedVerifyRegex", str(candidate.get("verify_regex") or ""))
    return payload
