from __future__ import annotations

import json
import re
from pathlib import Path
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


def build_live_cam_force_video_command(
    fast_open_script: str | Path,
    candidate: dict[str, Any],
    *,
    force_video_id: str,
) -> list[str]:
    return [
        "node",
        str(fast_open_script),
        "--cdp-port",
        str(candidate["port"]),
        "--force-video-id",
        str(force_video_id),
        "--keyword",
        str(candidate.get("keyword") or ""),
    ]


def build_live_cam_browse_command(
    fast_open_script: str | Path,
    candidate: dict[str, Any],
) -> list[str]:
    return [
        "node",
        str(fast_open_script),
        "--cdp-port",
        str(candidate["port"]),
        "--browse-url",
        str(candidate["browse_url"]),
        "--keyword",
        str(candidate["keyword"]),
        "--verify-regex",
        str(candidate["verify_regex"]),
    ]


def build_live_cam_json_parse_failure(
    candidate: dict[str, Any],
    *,
    returncode: int,
    error: str,
) -> dict[str, Any]:
    return {
        "keyword": str(candidate.get("keyword") or ""),
        "returncode": int(returncode),
        "error": f"json-parse: {error}",
    }


def build_live_cam_force_retry_failure(
    candidate: dict[str, Any],
    *,
    video_id: str,
) -> dict[str, Any]:
    return {
        "keyword": str(candidate.get("keyword") or ""),
        "reason": "web-watch-rejected-force-failed",
        "videoId": str(video_id or ""),
    }


def build_live_cam_command_failure(
    candidate: dict[str, Any],
    *,
    returncode: int,
    payload: dict[str, Any] | None,
    stderr: str,
) -> dict[str, Any]:
    return {
        "keyword": str(candidate.get("keyword") or ""),
        "returncode": int(returncode),
        "payload": payload if isinstance(payload, dict) else None,
        "stderr": str(stderr or "").strip(),
    }


def format_live_cam_selection_error(port: int, failures: list[dict[str, Any]]) -> str:
    failures_json = json.dumps(failures, ensure_ascii=False)
    return f"live camera select failed on port {int(port)}: {failures_json}"
