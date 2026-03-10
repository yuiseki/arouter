from __future__ import annotations

import concurrent.futures
import json
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

from .kwin_runtime import (
    KWinScriptCommandPlan,
    run_live_cam_minimize_runtime,
    run_minimize_other_windows_runtime,
)
from .kwin_scripts import (
    build_kwin_script_command_plan,
    build_minimize_other_windows_script,
)
from .live_cam_layout import resolve_live_cam_layout_plan


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


def _write_temp_js_script(script_text: str, prefix: str) -> str:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".js",
        prefix=prefix,
        delete=False,
    ) as temp_file:
        temp_file.write(script_text)
        return temp_file.name


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


def run_live_cam_existing_windowed_pids_query(
    *,
    instances: list[dict[str, Any]],
    pid_lookup: Callable[[int], int | None],
    row_provider: Callable[[list[int]], list[dict[str, Any]]],
    log: Callable[[str], None] | None = None,
) -> dict[int, int] | None:
    pids_by_port = collect_live_cam_pids(instances, pid_lookup=pid_lookup)
    if not pids_by_port:
        return None

    if len(pids_by_port) != len(instances):
        return None

    rows = row_provider(list(pids_by_port.values()))
    missing_ports = find_missing_live_cam_window_ports(pids_by_port, rows)
    if missing_ports:
        if log is not None:
            log(
                "LIVE_CAM layout fast-path skipped (missing windows for ports: "
                + ", ".join(str(port) for port in sorted(missing_ports))
                + ")"
            )
        return None
    return pids_by_port


def run_live_cam_existing_windowed_pids_host_runtime_query(
    *,
    runtime: Any,
) -> dict[int, int] | None:
    log = runtime.log
    return run_live_cam_existing_windowed_pids_query(
        instances=list(runtime._live_camera_instance_specs()),
        pid_lookup=runtime._pid_for_port,
        row_provider=runtime._window_rows_by_pids,
        log=log if callable(log) else None,
    )


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


def run_live_cam_hide_flow(
    instances: list[dict[str, Any]],
    *,
    pid_lookup: Callable[[int], int | None],
    state_fetcher: Callable[[dict[int, int]], dict[str, Any]],
    close_windows: Callable[[list[int]], list[str]],
    after_action: Callable[[], None] | None = None,
) -> str:
    return run_live_cam_window_action_flow(
        instances,
        pid_lookup=pid_lookup,
        state_fetcher=state_fetcher,
        perform_window_action=close_windows,
        build_response=lambda window_ids, ports, state: build_live_cam_hide_response(
            window_ids=window_ids,
            ports=ports,
            state=state,
        ),
        after_action=after_action,
    )


def run_live_cam_minimize_flow(
    instances: list[dict[str, Any]],
    *,
    pid_lookup: Callable[[int], int | None],
    state_fetcher: Callable[[dict[int, int]], dict[str, Any]],
    minimize_windows: Callable[[list[int]], list[str]],
    after_action: Callable[[], None] | None = None,
) -> str:
    return run_live_cam_window_action_flow(
        instances,
        pid_lookup=pid_lookup,
        state_fetcher=state_fetcher,
        perform_window_action=minimize_windows,
        build_response=lambda window_ids, ports, state: build_live_cam_minimize_response(
            window_ids=window_ids,
            ports=ports,
            state=state,
        ),
        after_action=after_action,
    )


def run_live_cam_hide_host_runtime_flow(*, runtime: Any) -> str:
    return run_live_cam_hide_flow(
        list(runtime._live_camera_instance_specs()),
        pid_lookup=runtime._pid_for_port,
        state_fetcher=runtime._collect_runtime_state,
        close_windows=runtime._close_windows_for_pids,
        after_action=runtime._after_window_action_pause,
    )


def run_live_cam_minimize_host_runtime_flow(*, runtime: Any) -> str:
    return run_live_cam_minimize_flow(
        list(runtime._live_camera_instance_specs()),
        pid_lookup=runtime._pid_for_port,
        state_fetcher=runtime._collect_runtime_state,
        minimize_windows=runtime._minimize_windows_for_pids,
        after_action=runtime._after_window_action_pause,
    )


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


def run_live_cam_raise_windows_host_runtime_flow(*, runtime: Any, pids: list[int]) -> None:
    run_live_cam_raise_windows(
        pids,
        window_id_lookup=runtime._window_id_for_pid,
        build_activate_command=lambda wid: ["xdotool", "windowactivate", "--sync", wid],
        run_command=runtime._run_x11_command,
    )


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


def run_live_cam_close_windows_host_runtime_flow(
    *,
    runtime: Any,
    pids: list[int],
) -> list[str]:
    return run_live_cam_close_windows(
        pids,
        window_id_lookup=runtime._window_id_for_pid,
        build_close_command=lambda wid: ["wmctrl", "-i", "-c", wid],
        run_command=runtime._run_x11_command,
    )


def run_live_cam_minimize_windows(
    pids: list[int],
    *,
    window_id_lookup: Callable[[int], str | None],
    collect_window_ids: LiveCamWindowIdCollector,
    build_script: Callable[[list[int]], str],
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    cleanup: Callable[[str], None],
    plugin_name: str,
) -> list[str]:
    window_ids = collect_window_ids(pids, window_id_lookup=window_id_lookup)
    if not pids:
        return window_ids
    run_live_cam_minimize_runtime(
        pids=pids,
        plugin_name=plugin_name,
        build_script=build_script,
        write_temp_script=write_temp_script,
        command_plan_builder=command_plan_builder,
        run_command=run_command,
        sleep=sleep,
        cleanup=cleanup,
    )
    return window_ids


def run_live_cam_minimize_windows_host_runtime_flow(
    *,
    runtime: Any,
    pids: list[int],
) -> list[str]:
    plugin_name = f"codex_live_cam_minimize_{int(time.time() * 1000) % 1000000}"
    return run_live_cam_minimize_windows(
        pids,
        window_id_lookup=runtime._window_id_for_pid,
        collect_window_ids=collect_window_ids_for_pids,
        build_script=lambda current_pids: "\n".join(
            [
                "var targetPids = {",
                *[f"  {int(pid)}: true," for pid in current_pids],
                "};",
                "var clients = workspace.clientList();",
                "for (var i = 0; i < clients.length; ++i) {",
                "  var c = clients[i];",
                "  if (!targetPids[c.pid]) continue;",
                "  try { c.keepAbove = false; } catch (e1) {}",
                "  try { c.minimized = true; } catch (e2) {}",
                "}",
                "",
            ]
        ),
        write_temp_script=_write_temp_js_script,
        command_plan_builder=lambda path, plugin: {
            "run": [
                [
                    "qdbus",
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting.loadScript",
                    path,
                    plugin,
                ],
                [
                    "qdbus",
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting.start",
                ],
            ],
            "unload": [
                "qdbus",
                "org.kde.KWin",
                "/Scripting",
                "org.kde.kwin.Scripting.unloadScript",
                plugin,
            ],
        },
        run_command=runtime._run_x11_command,
        sleep=runtime._sleep,
        cleanup=runtime._cleanup_temp_path,
        plugin_name=plugin_name,
    )


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


def run_live_cam_start_script_flow(
    spec: dict[str, Any],
    *,
    start_silent_script: str | Path,
    display: str,
    run_command: Callable[[list[str]], Any],
    sink: str = "vacuumtube_silent",
) -> dict[str, Any]:
    return run_live_cam_start_flow(
        spec,
        build_command=lambda current_spec: build_live_cam_start_command(
            start_silent_script,
            current_spec,
            display=display,
            sink=sink,
        ),
        run_command=run_command,
        parse_stdout=parse_key_value_stdout,
        build_result=build_live_cam_started_result,
    )


def run_live_cam_start_script_host_runtime_flow(
    *,
    spec: dict[str, Any],
    runtime: Any,
) -> dict[str, Any]:
    return run_live_cam_start_script_flow(
        spec,
        start_silent_script=runtime.start_silent_script,
        display=runtime._resolve_display(),
        run_command=runtime._run_live_cam_start_command,
    )


def run_live_cam_start_instances_flow(
    specs: list[dict[str, Any]],
    *,
    ensure_scripts_present: Callable[[], None],
    start_instance: Callable[[dict[str, Any]], dict[str, Any]],
    parallel_runner: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ensure_scripts_present()
    return parallel_runner(
        specs,
        worker=start_instance,
        label="live_cam_start",
    )


def run_live_cam_start_instances_host_runtime_flow(*, runtime: Any) -> list[dict[str, Any]]:
    return run_live_cam_start_instances_flow(
        list(runtime._live_camera_instance_specs()),
        ensure_scripts_present=runtime._ensure_scripts_present,
        start_instance=runtime._start_instance,
        parallel_runner=runtime._run_instances_parallel,
    )


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


def run_live_cam_open_instances_flow(
    specs: list[dict[str, Any]],
    *,
    assign_live_camera: Callable[[dict[str, Any]], dict[str, Any]],
    parallel_runner: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return run_live_cam_open_flow(
        specs,
        assign_live_camera=assign_live_camera,
        build_result=build_live_cam_open_result,
        label="live_cam_open",
        parallel_runner=parallel_runner,
    )


def run_live_cam_open_instances_host_runtime_flow(*, runtime: Any) -> list[dict[str, Any]]:
    return run_live_cam_open_instances_flow(
        list(runtime._live_camera_instance_specs()),
        assign_live_camera=runtime._assign_live_camera,
        parallel_runner=runtime._run_instances_parallel,
    )


def run_live_cam_reopen_specs_flow(
    specs: list[dict[str, Any]],
    *,
    assign_live_camera: Callable[[dict[str, Any]], dict[str, Any]],
    parallel_runner: Callable[..., list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return run_live_cam_open_flow(
        specs,
        assign_live_camera=assign_live_camera,
        build_result=build_live_cam_reopen_result,
        label="live_cam_reopen",
        parallel_runner=parallel_runner,
    )


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
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    cleanup: Callable[[str], None],
    build_response: Callable[[list[int]], str],
    plugin_name: str,
) -> str:
    skip_pids = collect_live_cam_skip_pids(instances, pid_lookup=pid_lookup)
    run_minimize_other_windows_runtime(
        skip_pids=skip_pids,
        plugin_name=plugin_name,
        build_script=build_script,
        write_temp_script=write_temp_script,
        command_plan_builder=command_plan_builder,
        run_command=run_command,
        sleep=sleep,
        cleanup=cleanup,
    )
    return build_response(skip_pids)


def run_minimize_other_windows_host_runtime_flow(*, runtime: Any) -> str:
    plugin_name = f"codex_minimize_others_{int(time.time() * 1000) % 1000000}"

    def _run_command(command: list[str]) -> None:
        subprocess.run(
            command,
            env=runtime._vacuumtube_x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return run_minimize_other_windows_flow(
        instances=list(runtime._live_camera_instance_specs()),
        pid_lookup=runtime._live_camera_pid_for_port,
        build_script=build_minimize_other_windows_script,
        write_temp_script=_write_temp_js_script,
        command_plan_builder=cast(
            Callable[[str, str], KWinScriptCommandPlan],
            build_kwin_script_command_plan,
        ),
        run_command=_run_command,
        sleep=time.sleep,
        cleanup=lambda path: Path(path).unlink(missing_ok=True),
        build_response=build_minimize_other_windows_response,
        plugin_name=plugin_name,
    )


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


def run_live_cam_layout_controller_flow(
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
    build_targets_full: Callable[..., list[dict[str, Any]]] | None,
    build_targets_compact: Callable[..., list[dict[str, Any]]] | None,
    kwin_apply_layout: Callable[..., None] | None,
    raise_windows_for_pids: Callable[[list[int]], None],
    collect_runtime_state: Callable[[dict[int, int]], dict[str, Any]],
    resolve_layout_plan: Callable[
        [str, int, int, tuple[int, int, int, int] | None, dict[int, int]],
        dict[str, Any],
    ]
    | None = None,
    apply_layout: Callable[[list[dict[str, Any]], str, bool, bool], None] | None = None,
) -> str:
    if resolve_layout_plan is None:
        if build_targets_full is None or build_targets_compact is None:
            raise RuntimeError("live camera layout builders are required")

        def _resolve_layout_plan(
            mode: str,
            screen_w: int,
            screen_h: int,
            work_area: tuple[int, int, int, int] | None,
            pids_by_port: dict[int, int],
        ) -> dict[str, Any]:
            return resolve_live_cam_layout_plan(
                mode=mode,
                screen_w=screen_w,
                screen_h=screen_h,
                work_area=work_area,
                pids_by_port=pids_by_port,
                full_target_builder=build_targets_full,
                compact_target_builder=build_targets_compact,
            )

        resolve_layout_plan = _resolve_layout_plan

    if apply_layout is None:
        if kwin_apply_layout is None:
            raise RuntimeError("live camera layout applier is required")

        def _apply_layout(
            targets: list[dict[str, Any]],
            plugin_name: str,
            keep_above: bool,
            no_border: bool,
        ) -> None:
            kwin_apply_layout(
                targets=targets,
                plugin_name=plugin_name,
                keep_above=keep_above,
                no_border=no_border,
            )

        apply_layout = _apply_layout

    return run_live_cam_layout_flow(
        mode=mode,
        screen_w=screen_w,
        screen_h=screen_h,
        work_area=work_area,
        pids_by_port=pids_by_port,
        fast_path=fast_path,
        started=started,
        opened=opened,
        open_errors=open_errors,
        resolve_layout_plan=resolve_layout_plan,
        apply_layout=apply_layout,
        raise_windows_for_pids=raise_windows_for_pids,
        collect_runtime_state=collect_runtime_state,
    )


def run_live_cam_layout_runtime_flow(
    *,
    mode: str,
    instances: list[dict[str, Any]],
    resolve_existing_windowed_pids: Callable[[], dict[int, int] | None],
    find_stuck_specs: Callable[[], list[dict[str, Any]]],
    assign_live_camera: Callable[[dict[str, Any]], dict[str, Any]] | None,
    parallel_runner: Callable[..., list[dict[str, Any]]] | None,
    ensure_scripts_present: Callable[[], None],
    ensure_instances_started: Callable[[], list[dict[str, Any]]],
    ensure_targets_opened: Callable[[], list[dict[str, Any]]],
    pid_lookup: Callable[[int], int | None],
    detect_screen_size: Callable[[], tuple[int, int]],
    detect_work_area: Callable[[], tuple[int, int, int, int] | None],
    build_targets_full: Callable[..., list[dict[str, Any]]] | None,
    build_targets_compact: Callable[..., list[dict[str, Any]]] | None,
    kwin_apply_layout: Callable[..., None] | None,
    raise_windows_for_pids: Callable[[list[int]], None],
    collect_runtime_state: Callable[[dict[int, int]], dict[str, Any]],
    reopen_specs: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    resolve_layout_plan: Callable[
        [str, int, int, tuple[int, int, int, int] | None, dict[int, int]],
        dict[str, Any],
    ]
    | None = None,
    apply_layout: Callable[[list[dict[str, Any]], str, bool, bool], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> str:
    if reopen_specs is None:
        if assign_live_camera is None or parallel_runner is None:
            raise RuntimeError("live camera reopen helpers are required")

        def _reopen_specs(stuck_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return run_live_cam_reopen_specs_flow(
                stuck_specs,
                assign_live_camera=assign_live_camera,
                parallel_runner=parallel_runner,
            )

        reopen_specs = _reopen_specs

    bootstrap = resolve_live_cam_layout_bootstrap(
        mode=mode,
        instances=instances,
        resolve_existing_windowed_pids=resolve_existing_windowed_pids,
        find_stuck_specs=find_stuck_specs,
        reopen_specs=reopen_specs,
        ensure_scripts_present=ensure_scripts_present,
        ensure_instances_started=ensure_instances_started,
        ensure_targets_opened=ensure_targets_opened,
        pid_lookup=pid_lookup,
        log=log,
    )
    screen_w, screen_h = detect_screen_size()
    return run_live_cam_layout_controller_flow(
        mode=mode,
        screen_w=screen_w,
        screen_h=screen_h,
        work_area=detect_work_area(),
        pids_by_port=dict(bootstrap["pids_by_port"]),
        fast_path=bool(bootstrap["fast_path"]),
        started=list(bootstrap["started"]),
        opened=list(bootstrap["opened"]),
        open_errors=list(bootstrap["open_errors"]),
        build_targets_full=build_targets_full,
        build_targets_compact=build_targets_compact,
        kwin_apply_layout=kwin_apply_layout,
        raise_windows_for_pids=raise_windows_for_pids,
        collect_runtime_state=collect_runtime_state,
        resolve_layout_plan=resolve_layout_plan,
        apply_layout=apply_layout,
    )


def run_live_cam_layout_host_runtime_flow(
    *,
    mode: str,
    runtime: Any,
) -> str:
    log = runtime.log
    return run_live_cam_layout_runtime_flow(
        mode=mode,
        instances=list(runtime._live_camera_instance_specs()),
        resolve_existing_windowed_pids=runtime._existing_windowed_pids_by_port,
        find_stuck_specs=runtime._find_stuck_instances,
        assign_live_camera=None,
        parallel_runner=None,
        ensure_scripts_present=runtime._ensure_scripts_present,
        ensure_instances_started=runtime._ensure_instances_started,
        ensure_targets_opened=runtime._ensure_tokyo_targets_opened,
        pid_lookup=runtime._pid_for_port,
        detect_screen_size=runtime._detect_screen_size,
        detect_work_area=runtime._detect_work_area,
        build_targets_full=None,
        build_targets_compact=None,
        kwin_apply_layout=None,
        raise_windows_for_pids=runtime._raise_windows_for_pids,
        collect_runtime_state=runtime._collect_runtime_state,
        reopen_specs=runtime._reopen_live_camera_specs,
        resolve_layout_plan=runtime._resolve_layout_plan,
        apply_layout=runtime._apply_live_cam_layout,
        log=log if callable(log) else None,
    )
