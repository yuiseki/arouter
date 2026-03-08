from __future__ import annotations

import json
import time
from pathlib import Path


def write_signal_file(
    *,
    signal_path: Path,
    action: str,
    requested_at: float | None = None,
) -> Path:
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "action": action,
            "requestedAt": time.time() if requested_at is None else requested_at,
        },
        ensure_ascii=False,
    )
    signal_path.write_text(payload + "\n", encoding="utf-8")
    return signal_path


def consume_signal_file(
    *,
    signal_path: Path,
    seen_mtime: float,
) -> tuple[bool, float]:
    try:
        stat = signal_path.stat()
    except OSError:
        return False, seen_mtime

    current_mtime = float(stat.st_mtime)
    if current_mtime <= float(seen_mtime):
        return False, seen_mtime
    try:
        signal_path.unlink()
    except OSError:
        pass
    return True, current_mtime
