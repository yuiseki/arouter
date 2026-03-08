from __future__ import annotations

from typing import Any


def require_cdp_target_list(payload: Any, error_message: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(error_message)
    return [item for item in payload if isinstance(item, dict)]
