from __future__ import annotations

import concurrent.futures
import json
from collections.abc import Callable
from pathlib import Path
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


def collect_live_cam_pids(
    instances: list[dict[str, Any]],
    *,
    pid_lookup: Callable[[int], int | None],
) -> dict[int, int] | None:
    pids_by_port: dict[int, int] = {}
    for spec in instances:
        port = int(spec["port"])
        pid = pid_lookup(port)
        if not pid:
            return None
        pids_by_port[port] = int(pid)
    return pids_by_port


def collect_live_cam_skip_pids(
    instances: list[dict[str, Any]],
    *,
    pid_lookup: Callable[[int], int | None],
) -> list[int]:
    pids_by_port = collect_live_cam_pids(instances, pid_lookup=pid_lookup) or {}
    return sorted({int(pid) for pid in pids_by_port.values()})


def collect_window_ids_for_pids(
    pids: list[int],
    *,
    window_id_lookup: Callable[[int], str | None],
) -> list[str]:
    window_ids: list[str] = []
    for pid in pids:
        wid = window_id_lookup(int(pid))
        if wid:
            window_ids.append(wid)
    return window_ids


def find_missing_live_cam_window_ports(
    pids_by_port: dict[int, int],
    rows: list[dict[str, Any]],
) -> list[int]:
    visible_pids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        pid = row.get("pid")
        if pid is None:
            continue
        visible_pids.add(int(pid))
    return [port for port, pid in pids_by_port.items() if int(pid) not in visible_pids]


def resolve_existing_live_cam_windowed_pids(
    pids_by_port: dict[int, int] | None,
    *,
    expected_count: int,
    rows: list[dict[str, Any]],
) -> dict[int, int] | None:
    if not pids_by_port or len(pids_by_port) != int(expected_count):
        return None
    missing_ports = find_missing_live_cam_window_ports(pids_by_port, rows)
    if missing_ports:
        return None
    return pids_by_port


def resolve_live_cam_action_state(
    instances: list[dict[str, Any]],
    *,
    pid_lookup: Callable[[int], int | None],
    state_fetcher: Callable[[dict[int, int]], dict[str, Any]],
) -> dict[str, Any]:
    pids_by_port = collect_live_cam_pids(instances, pid_lookup=pid_lookup) or {}
    if not pids_by_port:
        return {
            "pids_by_port": {},
            "state": {"windows": [], "urls": []},
        }
    return {
        "pids_by_port": pids_by_port,
        "state": state_fetcher(pids_by_port),
    }


def parse_key_value_stdout(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def build_live_cam_start_command(
    start_silent_script: str | Path,
    spec: dict[str, Any],
    *,
    display: str,
    sink: str = "vacuumtube_silent",
) -> list[str]:
    return [
        "bash",
        str(start_silent_script),
        "--session",
        str(spec["session"]),
        "--port",
        str(spec["port"]),
        "--sink",
        str(sink),
        "--display",
        str(display),
        "--instance-dir",
        str(spec["instance_dir"]),
    ]


def build_live_cam_started_result(
    spec: dict[str, Any],
    parsed: dict[str, str],
) -> dict[str, str]:
    result = dict(parsed)
    result["port"] = str(spec["port"])
    result["session_name"] = str(spec["session"])
    return result


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


def build_live_cam_hide_response(
    *,
    window_ids: list[str],
    ports: list[int],
    state: dict[str, Any],
) -> str:
    payload = {
        "closed": len(window_ids),
        "windowIds": window_ids,
        "ports": ports,
        **state,
    }
    return "live camera wall hide " + json.dumps(payload, ensure_ascii=False)


def build_live_cam_minimize_response(
    *,
    window_ids: list[str],
    ports: list[int],
    state: dict[str, Any],
) -> str:
    payload = {
        "minimized": len(window_ids),
        "windowIds": window_ids,
        "ports": ports,
        **state,
    }
    return "live camera wall minimize " + json.dumps(payload, ensure_ascii=False)


def build_minimize_other_windows_response(skip_pids: list[int]) -> str:
    skip_info = (
        f"skipped live_cam pids={skip_pids}" if skip_pids else "no live_cam pids"
    )
    return f"minimize other windows via KWin: ok ({skip_info})"
