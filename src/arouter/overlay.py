from __future__ import annotations

import json
from typing import Any


def trim_notify_text(text: str, *, limit: int = 240) -> str:
    squashed = " ".join((text or "").split())
    if len(squashed) <= limit:
        return squashed
    if limit <= 1:
        return squashed[:limit]
    return squashed[: limit - 1] + "…"


def compose_overlay_notify_text(title: str, body: str) -> str:
    title_trimmed = trim_notify_text(title, limit=80) or "音声コマンド"
    body_trimmed = trim_notify_text(body, limit=240)
    if body_trimmed:
        return f"{title_trimmed}: {body_trimmed}"
    return title_trimmed


def build_overlay_ipc_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
