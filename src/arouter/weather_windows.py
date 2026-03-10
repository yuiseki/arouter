from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from .window_rows import select_weather_candidate_window_ids

WeatherWindowIdsFetcher = Callable[[], set[str]]
WeatherWindowLauncher = Callable[[str], None]
WeatherWindowDetector = Callable[[set[str], float], str]
WeatherWindowMover = Callable[[str, dict[str, Any]], dict[str, Any]]
WeatherTileResultBuilder = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
WeatherTiledResponseBuilder = Callable[[list[dict[str, Any]]], str]
WeatherCandidateSelector = Callable[[list[str], list[str]], list[str]]
WeatherWindowCloser = Callable[[str], None]
WeatherWindowHistoryPruner = Callable[[list[str], set[str]], list[str]]
WeatherClosedResponseBuilder = Callable[[list[str]], str]
WeatherAfterClose = Callable[[], None]


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


def run_weather_pages_tiled(
    *,
    weather_desktop_tiles: list[dict[str, Any]],
    current_window_ids: WeatherWindowIdsFetcher,
    launch_window: WeatherWindowLauncher,
    detect_new_window: WeatherWindowDetector,
    move_window: WeatherWindowMover,
) -> dict[str, Any]:
    flow = open_weather_pages_flow(
        weather_desktop_tiles,
        current_window_ids=current_window_ids,
        launch_window=launch_window,
        detect_new_window=detect_new_window,
        move_window=move_window,
        build_tile_result=lambda spec, moved: build_weather_tile_result(spec=spec, moved=moved),
        build_response=build_weather_pages_tiled_response,
    )
    return {
        "history": list(flow["opened_ids"]),
        "results": list(flow["results"]),
        "response": flow["response"],
    }


def run_weather_pages_tiled_host_runtime(
    *,
    runtime: Any,
) -> str:
    flow = run_weather_pages_tiled(
        weather_desktop_tiles=list(runtime._weather_desktop_tiles),
        current_window_ids=runtime._chromium_window_ids,
        launch_window=runtime._launch_chromium_new_window,
        detect_new_window=runtime._detect_new_chromium_window,
        move_window=runtime._move_window_to_geometry,
    )
    runtime._last_weather_window_ids = list(flow["history"])
    return str(flow["response"])


def run_weather_pages_closed(
    *,
    lines: list[str],
    last_weather_window_ids: list[str],
    select_candidate_window_ids: WeatherCandidateSelector,
    close_window: WeatherWindowCloser,
    current_window_ids: WeatherWindowIdsFetcher,
    after_close: WeatherAfterClose | None = None,
) -> dict[str, Any]:
    flow = close_weather_pages_flow(
        lines,
        last_weather_window_ids,
        select_candidate_window_ids=select_candidate_window_ids,
        close_window=close_window,
        current_window_ids=current_window_ids,
        prune_history=prune_weather_window_history,
        build_response=build_weather_pages_closed_response,
        after_close=after_close,
    )
    return {
        "candidate_ids": list(flow["candidate_ids"]),
        "history": list(flow["history"]),
        "response": flow["response"],
    }


def run_weather_pages_closed_host_runtime(
    *,
    runtime: Any,
    select_candidate_window_ids: WeatherCandidateSelector | None = None,
    after_close: WeatherAfterClose | None = None,
) -> str:
    flow = run_weather_pages_closed(
        lines=runtime._wmctrl_lines(),
        last_weather_window_ids=list(getattr(runtime, "_last_weather_window_ids", [])),
        select_candidate_window_ids=select_candidate_window_ids
        or select_weather_candidate_window_ids,
        close_window=runtime._wmctrl_close_window,
        current_window_ids=runtime._chromium_window_ids,
        after_close=after_close or (lambda: time.sleep(0.2)),
    )
    runtime._last_weather_window_ids = list(flow["history"])
    return str(flow["response"])


def open_weather_pages_flow(
    weather_desktop_tiles: list[dict[str, Any]],
    *,
    current_window_ids: WeatherWindowIdsFetcher,
    launch_window: WeatherWindowLauncher,
    detect_new_window: WeatherWindowDetector,
    move_window: WeatherWindowMover,
    build_tile_result: WeatherTileResultBuilder,
    build_response: WeatherTiledResponseBuilder,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    opened_ids: list[str] = []
    for spec in weather_desktop_tiles:
        before_ids = current_window_ids()
        launch_window(str(spec["url"]))
        win_id = detect_new_window(before_ids, 18.0)
        opened_ids.append(win_id.lower())
        moved = move_window(win_id, dict(spec["geom"]))
        results.append(build_tile_result(spec, moved))
    return {
        "opened_ids": opened_ids,
        "results": results,
        "response": build_response(results),
    }


def close_weather_pages_flow(
    lines: list[str],
    last_weather_window_ids: list[str],
    *,
    select_candidate_window_ids: WeatherCandidateSelector,
    close_window: WeatherWindowCloser,
    current_window_ids: WeatherWindowIdsFetcher,
    prune_history: WeatherWindowHistoryPruner,
    build_response: WeatherClosedResponseBuilder,
    after_close: WeatherAfterClose | None = None,
) -> dict[str, Any]:
    candidate_ids = select_candidate_window_ids(lines, last_weather_window_ids)
    for wid in candidate_ids:
        close_window(wid)
    if candidate_ids and after_close is not None:
        after_close()
    remaining_ids = current_window_ids()
    return {
        "candidate_ids": candidate_ids,
        "remaining_ids": remaining_ids,
        "history": prune_history(last_weather_window_ids, remaining_ids),
        "response": build_response(candidate_ids),
    }
