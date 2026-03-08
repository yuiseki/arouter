from __future__ import annotations

import concurrent.futures
import json
from collections.abc import Callable
from typing import Any


def run_live_cam_parallel(
    specs: list[dict[str, Any]],
    *,
    worker: Callable[[dict[str, Any]], dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    if not specs:
        return []
    if len(specs) == 1:
        return [worker(specs[0])]

    max_workers = min(4, len(specs))
    results: list[dict[str, Any] | None] = [None] * len(specs)
    futures: dict[concurrent.futures.Future[dict[str, Any]], tuple[int, dict[str, Any]]] = {}

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="livecam",
    ) as ex:
        for idx, spec in enumerate(specs):
            futures[ex.submit(worker, spec)] = (idx, spec)

        for fut in concurrent.futures.as_completed(futures):
            idx, spec = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                for other in futures:
                    if other is fut:
                        continue
                    other.cancel()
                port = spec.get("port")
                tag = spec.get("label") or "unknown"
                raise RuntimeError(f"{label} failed ({tag}:{port}): {e}") from e
            if not isinstance(res, dict):
                raise RuntimeError(
                    f"{label} worker returned non-dict for index {idx}: "
                    f"{type(res).__name__}"
                )
            results[idx] = res

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(results):
        if item is None:
            raise RuntimeError(f"{label} missing result for index {idx}")
        out.append(item)
    return out


def build_live_cam_open_result(
    spec: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    final = payload.get("final") or {}
    final_href = final.get("href") if isinstance(final, dict) else None
    return {
        "label": spec["label"],
        "port": spec["port"],
        "videoId": payload.get("videoId"),
        "finalHref": final_href,
        "method": payload.get("method"),
    }


def build_live_cam_reopen_result(
    spec: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "label": spec["label"],
        "port": spec["port"],
        "videoId": payload.get("videoId"),
        "method": payload.get("method"),
    }


def build_live_cam_layout_response(
    *,
    mode: str,
    fast_path: bool,
    screen_w: int,
    screen_h: int,
    work_area: tuple[int, int, int, int],
    started: list[dict[str, Any]],
    opened: list[dict[str, Any]],
    state: dict[str, Any],
    open_errors: list[str],
) -> str:
    work_x, work_y, work_w, work_h = work_area
    payload: dict[str, Any] = {
        "mode": mode,
        "fastPath": fast_path,
        "screen": {"w": screen_w, "h": screen_h},
        "workArea": {"x": work_x, "y": work_y, "w": work_w, "h": work_h},
        "started": started,
        "opened": opened,
        **state,
    }
    if open_errors:
        payload["openErrors"] = open_errors
    return "live camera wall " + json.dumps(payload, ensure_ascii=False)
