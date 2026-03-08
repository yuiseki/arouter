from __future__ import annotations

from collections.abc import Callable
from typing import Any


def require_cdp_target_list(payload: Any, error_message: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(error_message)
    return [item for item in payload if isinstance(item, dict)]


def run_cdp_target_list_query(
    *,
    fetch_json: Callable[[], Any],
    validate: Callable[[Any, str], list[dict[str, Any]]],
    error_message: str,
) -> list[dict[str, Any]]:
    return validate(fetch_json(), error_message)
