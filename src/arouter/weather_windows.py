from __future__ import annotations

import json
from typing import Any


def build_weather_tile_result(
    *,
    spec: dict[str, Any],
    moved: dict[str, Any],
) -> dict[str, Any]:
    result = dict(moved)
    result["label"] = spec["label"]
    result["url"] = spec["url"]
    return result


def build_weather_pages_tiled_response(results: list[dict[str, Any]]) -> str:
    return "weather pages tiled " + json.dumps(results, ensure_ascii=False)


def prune_weather_window_history(
    last_weather_window_ids: list[str],
    remaining_ids: set[str],
) -> list[str]:
    return [wid for wid in last_weather_window_ids if wid in remaining_ids]


def build_weather_pages_closed_response(candidate_ids: list[str]) -> str:
    return "weather pages closed " + json.dumps(
        {"closed": len(candidate_ids), "ids": candidate_ids},
        ensure_ascii=False,
    )
