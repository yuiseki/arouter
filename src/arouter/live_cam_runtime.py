from __future__ import annotations

import concurrent.futures
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


class LiveCamWindowIdCollector(Protocol):
    def __call__(
        self,
        pids: list[int],
        *,
        window_id_lookup: Callable[[int], str | None],
    ) -> list[str]: ...


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


def resolve_live_cam_layout_bootstrap(
    *,
    mode: str,
    instances: list[dict[str, Any]],
    resolve_existing_windowed_pids: Callable[[], dict[int, int] | None],
    find_stuck_specs: Callable[[], list[dict[str, Any]]],
    reopen_specs: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    ensure_scripts_present: Callable[[], None],
    ensure_instances_started: Callable[[], list[dict[str, Any]]],
    ensure_targets_opened: Callable[[], list[dict[str, Any]]],
    pid_lookup: Callable[[int], int | None],
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    def _log(message: str) -> None:
        if log is not None:
            log(message)

    started: list[dict[str, Any]] = []
    opened: list[dict[str, Any]] = []
    open_errors: list[str] = []
    fast_path = False

    pids_by_port: dict[int, int] | None = None
    if mode in {"full", "compact"}:
        pids_by_port = resolve_existing_windowed_pids()
        if pids_by_port:
            fast_path = True
            _log(
                f"LIVE_CAM {mode} fast-path: reusing existing windows and applying layout only"
            )
            stuck_specs = find_stuck_specs()
            if stuck_specs:
                _log(
                    f"LIVE_CAM fast-path: re-opening {len(stuck_specs)} stuck instance(s): "
                    + ", ".join(str(spec["label"]) for spec in stuck_specs)
                )
                try:
                    opened = reopen_specs(stuck_specs)
                except Exception as exc:
                    open_errors.append(str(exc))
                    _log(
                        "LIVE_CAM fast-path reopen partial failure (layout will still be applied): "
                        f"{exc}"
                    )

    if not pids_by_port:
        ensure_scripts_present()
        started = ensure_instances_started()
        try:
            opened = ensure_targets_opened()
        except Exception as exc:
            open_errors.append(str(exc))
            _log(f"LIVE_CAM channel open partial failure (layout will still be applied): {exc}")
        pids_by_port = {}
        for spec in instances:
            port = int(spec["port"])
            pid = pid_lookup(port)
            if not pid:
                raise RuntimeError(f"live camera port {port} PID not found after start")
            pids_by_port[port] = pid

    return {
        "fast_path": fast_path,
        "started": started,
        "opened": opened,
        "open_errors": open_errors,
        "pids_by_port": pids_by_port,
    }


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


def run_live_cam_window_action_flow(
    instances: list[dict[str, Any]],
    *,
    pid_lookup: Callable[[int], int | None],
    state_fetcher: Callable[[dict[int, int]], dict[str, Any]],
    perform_window_action: Callable[[list[int]], list[str]],
    build_response: Callable[[list[str], list[int], dict[str, Any]], str],
    after_action: Callable[[], None] | None = None,
) -> str:
    action_state = resolve_live_cam_action_state(
        instances,
        pid_lookup=pid_lookup,
        state_fetcher=state_fetcher,
    )
    pids_by_port = dict(action_state["pids_by_port"])
    state = dict(action_state["state"])
    window_ids = perform_window_action(list(pids_by_port.values()))
    if after_action is not None:
        after_action()
    return build_response(window_ids, sorted(pids_by_port.keys()), state)


def run_live_cam_raise_windows(
    pids: list[int],
    *,
    window_id_lookup: Callable[[int], str | None],
    build_activate_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], None],
) -> None:
    for pid in pids:
        wid = window_id_lookup(int(pid))
        if not wid:
            continue
        run_command(build_activate_command(wid))


def run_live_cam_close_windows(
    pids: list[int],
    *,
    window_id_lookup: Callable[[int], str | None],
    build_close_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], None],
) -> list[str]:
    closed: list[str] = []
    for pid in pids:
        wid = window_id_lookup(int(pid))
        if not wid:
            continue
        run_command(build_close_command(wid))
        closed.append(wid)
    return closed


def run_live_cam_minimize_windows(
    pids: list[int],
    *,
    window_id_lookup: Callable[[int], str | None],
    collect_window_ids: LiveCamWindowIdCollector,
    build_script: Callable[[list[int]], str],
    run_script: Callable[..., None],
    plugin_name: str,
) -> list[str]:
    window_ids = collect_window_ids(pids, window_id_lookup=window_id_lookup)
    if not pids:
        return window_ids
    run_script(
        script_text=build_script(pids),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-livecam-minimize-",
        sleep_sec=0.4,
    )
    return window_ids


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


def run_live_cam_start_flow(
    spec: dict[str, Any],
    *,
    build_command: Callable[[dict[str, Any]], list[str]],
    run_command: Callable[[list[str]], Any],
    parse_stdout: Callable[[str], dict[str, str]],
    build_result: Callable[[dict[str, Any], dict[str, str]], dict[str, Any]],
) -> dict[str, Any]:
    command = build_command(spec)
    completed = run_command(command)
    parsed = parse_stdout(str(getattr(completed, "stdout", "") or ""))
    return build_result(spec, parsed)


def run_live_cam_open_flow(
    specs: list[dict[str, Any]],
    *,
    assign_live_camera: Callable[[dict[str, Any]], dict[str, Any]],
    build_result: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    label: str,
    parallel_runner: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    def _worker(spec: dict[str, Any]) -> dict[str, Any]:
        payload = assign_live_camera(spec)
        return build_result(spec, payload)

    return parallel_runner(specs, worker=_worker, label=label)


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


def run_minimize_other_windows_flow(
    *,
    instances: list[dict[str, Any]],
    pid_lookup: Callable[[int], int | None],
    build_script: Callable[[list[int]], str],
    run_script: Callable[..., None],
    build_response: Callable[[list[int]], str],
    plugin_name: str,
    file_prefix: str = "codex-kwin-minimize-",
    sleep_sec: float = 0.3,
) -> str:
    skip_pids = collect_live_cam_skip_pids(instances, pid_lookup=pid_lookup)
    script_text = build_script(skip_pids)
    run_script(
        script_text=script_text,
        plugin_name=plugin_name,
        file_prefix=file_prefix,
        sleep_sec=sleep_sec,
    )
    return build_response(skip_pids)


def run_live_cam_layout_flow(
    *,
    mode: str,
    screen_w: int,
    screen_h: int,
    work_area: tuple[int, int, int, int] | None,
    pids_by_port: dict[int, int],
    fast_path: bool,
    started: list[dict[str, Any]],
    opened: list[dict[str, Any]],
    open_errors: list[str],
    resolve_layout_plan: Callable[
        [str, int, int, tuple[int, int, int, int] | None, dict[int, int]],
        dict[str, Any],
    ],
    apply_layout: Callable[[list[dict[str, Any]], str, bool, bool], None],
    raise_windows_for_pids: Callable[[list[int]], None],
    collect_runtime_state: Callable[[dict[int, int]], dict[str, Any]],
) -> str:
    plan = resolve_layout_plan(mode, screen_w, screen_h, work_area, pids_by_port)
    work = plan["work_area"]
    work_area_tuple = (
        int(work["x"]),
        int(work["y"]),
        int(work["w"]),
        int(work["h"]),
    )
    targets = list(plan["targets"])
    plugin_name = str(plan["plugin_name"])
    keep_above = bool(plan["keep_above"])

    apply_layout(targets, plugin_name, keep_above, True)
    if keep_above:
        raise_windows_for_pids(list(pids_by_port.values()))
    state = collect_runtime_state(pids_by_port)
    return build_live_cam_layout_response(
        mode=mode,
        fast_path=fast_path,
        screen_w=screen_w,
        screen_h=screen_h,
        work_area=work_area_tuple,
        started=started,
        opened=opened,
        state=state,
        open_errors=open_errors,
    )
