from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from .desktop_runtime import run_tmux_konsole_open
from .window_presentation import geometry_close as _geometry_close


class VacuumTubeLoadCheckRuntime(Protocol):
    cdp_port: int | None
    target_geometry: dict[str, Any] | None
    geometry_tolerance: int | None

    def find_window_id(self) -> str | None: ...

    def get_window_geometry(self, win_id: str) -> dict[str, Any] | None: ...

    def _current_window_is_fullscreenish(self, win_id: str) -> bool: ...


def load_check_bottom_left_geom(*, screen_w: int, screen_h: int) -> dict[str, int]:
    return {
        "x": 0,
        "y": max(0, int(screen_h) // 2),
        "w": max(1, int(screen_w) // 2),
        "h": max(1, int(screen_h) // 2),
    }


def parse_konsole_window_rows(wmctrl_output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in (wmctrl_output or "").splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        title = parts[8]
        if "Konsole" not in title:
            continue
        try:
            rows.append(
                {
                    "id": parts[0],
                    "pid": int(parts[2]),
                    "x": int(parts[3]),
                    "y": int(parts[4]),
                    "w": int(parts[5]),
                    "h": int(parts[6]),
                    "title": title,
                }
            )
        except Exception:
            continue
    return rows


def parse_tmux_client_pids(stdout: str, *, returncode: int) -> list[int]:
    if returncode != 0:
        return []
    out: list[int] = []
    for line in (stdout or "").splitlines():
        try:
            pid = int(line.strip())
        except Exception:
            continue
        if pid > 0:
            out.append(pid)
    return out


def run_tmux_client_pid_query(
    session_name: str,
    *,
    run_command: Callable[[list[str]], Any],
    parse_output: Callable[[str, int], list[int]],
) -> list[int]:
    cp = run_command(
        ["tmux", "list-clients", "-t", session_name, "-F", "#{client_pid}"]
    )
    return parse_output(
        str(getattr(cp, "stdout", "") or ""),
        int(getattr(cp, "returncode", 1)),
    )


def run_tmux_client_pid_query_host_runtime(*, runtime: Any, session_name: str) -> list[int]:
    del runtime
    return run_tmux_client_pid_query(
        session_name,
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        ),
        parse_output=lambda stdout, returncode: parse_tmux_client_pids(
            stdout,
            returncode=returncode,
        ),
    )


def pid_ancestor_chain(
    pid: int,
    *,
    parent_pid_for_pid: Callable[[int], int | None],
    max_depth: int = 32,
) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    cur = int(pid)
    for _ in range(max_depth):
        if cur <= 1 or cur in seen:
            break
        seen.add(cur)
        out.append(cur)
        ppid = parent_pid_for_pid(cur)
        if not ppid:
            break
        cur = int(ppid)
    return out


def find_konsole_rows_for_tmux_client_pids(
    rows: list[dict[str, Any]],
    client_pids: list[int],
    *,
    parent_pid_for_pid: Callable[[int], int | None],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    by_pid: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            by_pid[int(row["pid"])] = row
        except Exception:
            continue
    matched: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for client_pid in client_pids:
        for ancestor_pid in pid_ancestor_chain(
            client_pid,
            parent_pid_for_pid=parent_pid_for_pid,
        ):
            matched_row: dict[str, Any] | None = by_pid.get(int(ancestor_pid))
            if not matched_row:
                continue
            wid = str(matched_row.get("id") or "")
            if wid and wid not in seen_ids:
                matched.append(matched_row)
                seen_ids.add(wid)
            break
    return matched


def find_konsole_rows_for_tmux_session_host_runtime(
    *,
    runtime: Any,
    session_name: str,
) -> list[dict[str, Any]]:
    return find_konsole_rows_for_tmux_client_pids(
        runtime._konsole_window_rows(),
        runtime._tmux_client_pids_for_session(session_name),
        parent_pid_for_pid=runtime._parent_pid,
    )


def wait_for_new_window_row(
    *,
    row_provider: Callable[[], list[dict[str, Any]]],
    before_ids: set[str],
    timeout_sec: float,
    now: Callable[[], float],
    sleep: Callable[[float], None],
    poll_interval_sec: float = 0.15,
    ) -> dict[str, Any] | None:
    deadline = now() + timeout_sec
    while now() < deadline:
        rows = row_provider()
        new_rows = [row for row in rows if str(row.get("id") or "").lower() not in before_ids]
        if new_rows:
            return new_rows[-1]
        sleep(poll_interval_sec)
    return None


def wait_for_new_window_row_host_runtime(
    *,
    runtime: Any,
    before_ids: set[str],
    timeout_sec: float,
) -> dict[str, Any] | None:
    return wait_for_new_window_row(
        row_provider=runtime._konsole_window_rows,
        before_ids=before_ids,
        timeout_sec=timeout_sec,
        now=time.time,
        sleep=time.sleep,
    )


def prepare_load_check_konsole_placement(
    *,
    quadrant_mode: bool,
    screen: tuple[int, int] | None,
    row: dict[str, Any] | None,
    before_konsole_ids: set[str] | None,
    wait_for_row: Callable[[], dict[str, Any] | None],
    target_geom: Callable[..., dict[str, int]],
) -> dict[str, Any]:
    if not quadrant_mode:
        return {"applied": False, "reason": "vacuumtube_not_quadrant"}
    if not screen:
        return {"applied": False, "reason": "screen_size_unknown"}

    selected_row = row
    if selected_row is None:
        if before_konsole_ids is None:
            return {"applied": False, "reason": "konsole_window_not_specified"}
        selected_row = wait_for_row()
    if not selected_row:
        return {"applied": False, "reason": "konsole_window_not_found"}

    geom = target_geom(screen_w=int(screen[0]), screen_h=int(screen[1]))
    return {
        "applied": False,
        "ready": True,
        "window_id": str(selected_row["id"]),
        "target": geom,
    }


def build_load_check_wmctrl_commands(
    *,
    window_id: str,
    target: dict[str, int],
) -> list[list[str]]:
    spec = f"0,{target['x']},{target['y']},{target['w']},{target['h']}"
    return [
        ["wmctrl", "-i", "-r", window_id, "-b", "remove,maximized_vert,maximized_horz"],
        ["wmctrl", "-i", "-r", window_id, "-b", "remove,fullscreen"],
        ["wmctrl", "-i", "-r", window_id, "-e", spec],
        ["wmctrl", "-i", "-r", window_id, "-e", spec],
    ]


def run_load_check_wmctrl_commands(
    *,
    window_id: str,
    target: dict[str, int],
    build_commands: Callable[..., list[list[str]]],
    run_command: Callable[[list[str]], Any],
) -> dict[str, Any]:
    commands = build_commands(window_id=window_id, target=target)
    for command in commands:
        run_command(command)
    return {"applied": True, "window_id": window_id, "target": target}


def run_system_load_check_flow(
    *,
    existing_rows: list[dict[str, Any]],
    get_before_konsole_ids: Callable[[], set[str]],
    raise_window_by_id: Callable[[str], None],
    apply_placement_for_existing: Callable[[dict[str, Any]], dict[str, Any]],
    open_monitor: Callable[[], str],
    apply_placement_for_new: Callable[[set[str]], dict[str, Any]],
    logger: Callable[[str], None],
) -> str:
    if existing_rows:
        row = existing_rows[-1]
        wid = str(row.get("id") or "")
        if wid:
            raise_window_by_id(wid)
        try:
            placement = apply_placement_for_existing(row)
            logger(f"system_load_check placement: {json.dumps(placement, ensure_ascii=False)}")
        except Exception as exc:
            logger(f"system_load_check placement skipped: {exc}")
        return "system load monitor reused (tmux=sysmon)"

    before_konsole_ids = get_before_konsole_ids()
    out = open_monitor()
    if out:
        logger(f"system_load_check: {out}")
    try:
        placement = apply_placement_for_new(before_konsole_ids)
        logger(f"system_load_check placement: {json.dumps(placement, ensure_ascii=False)}")
    except Exception as exc:
        logger(f"system_load_check placement skipped: {exc}")
    return "system load monitor opened (tmux=sysmon)"


def run_load_check_konsole_placement_host_runtime(
    *,
    runtime: Any,
    before_konsole_ids: set[str] | None = None,
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prepared = prepare_load_check_konsole_placement(
        quadrant_mode=runtime._is_vacuumtube_quadrant_mode_for_load_check(),
        screen=runtime.vacuumtube._desktop_size(),
        row=row,
        before_konsole_ids=before_konsole_ids,
        wait_for_row=lambda: runtime._wait_new_konsole_window(
            before_ids=before_konsole_ids or set(),
            timeout_sec=8.0,
        ),
        target_geom=runtime._load_check_bottom_left_geom,
    )
    if not prepared.get("ready"):
        return prepared

    geom = dict(prepared["target"])
    wid = str(prepared["window_id"])
    env = runtime.vacuumtube._x11_env()
    try:
        result = run_load_check_wmctrl_commands(
            window_id=wid,
            target=geom,
            build_commands=build_load_check_wmctrl_commands,
            run_command=lambda command: subprocess.run(
                command,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            ),
        )
        runtime.log(f"system_load_check Konsole repositioned to left-bottom: wid={wid} geom={geom}")
        return result
    except Exception as exc:
        runtime.log(f"system_load_check Konsole reposition failed: {exc}")
        return {"applied": False, "reason": str(exc)}


def run_system_load_check_monitor_open_host_runtime(
    *,
    script_path: str,
    cwd: str,
) -> str:
    return run_tmux_konsole_open(
        script_path=script_path,
        session_name="sysmon",
        cwd=cwd,
        path_exists=lambda path: Path(path).exists(),
        run_command=lambda command, cwd: subprocess.run(
            command,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        ),
    )


def run_system_load_check_host_runtime(*, runtime: Any) -> str:
    return run_system_load_check_flow(
        existing_rows=runtime._find_konsole_rows_for_tmux_session("sysmon"),
        get_before_konsole_ids=lambda: {
            str(row.get("id") or "").lower() for row in runtime._konsole_window_rows()
        },
        raise_window_by_id=runtime._raise_window_by_id,
        apply_placement_for_existing=lambda row: run_load_check_konsole_placement_host_runtime(
            runtime=runtime,
            row=row,
        ),
        open_monitor=runtime._open_system_load_check_monitor,
        apply_placement_for_new=lambda before_ids: run_load_check_konsole_placement_host_runtime(
            runtime=runtime,
            before_konsole_ids=before_ids,
        ),
        logger=runtime.log,
    )


def is_vacuumtube_quadrant_mode_for_load_check(
    runtime: VacuumTubeLoadCheckRuntime,
    *,
    row_by_cdp_port: Callable[[int], dict[str, Any] | None],
) -> bool:
    try:
        row: dict[str, Any] | None = None
        wid: str | None = None
        geom: dict[str, Any] | None = None
        cdp_port = getattr(runtime, "cdp_port", None)
        if cdp_port:
            row = row_by_cdp_port(int(cdp_port))
        if row:
            wid = str(row.get("id") or "")
            geom = {"x": row.get("x"), "y": row.get("y"), "w": row.get("w"), "h": row.get("h")}
        else:
            wid = runtime.find_window_id()
            if not wid:
                return False
            geom = runtime.get_window_geometry(wid)
        if not wid:
            return False
        if bool(runtime._current_window_is_fullscreenish(wid)):
            return False
        target = None
        helper = getattr(runtime, "expected_top_right_geometry", None)
        if callable(helper):
            try:
                maybe_target = helper()
                if isinstance(maybe_target, dict):
                    target = maybe_target
            except Exception:
                target = None
        fallback_target = getattr(runtime, "target_geometry", None)
        if target is None and isinstance(fallback_target, dict):
            target = fallback_target
        if not isinstance(geom, dict) or not isinstance(target, dict):
            return False
        tol = int(getattr(runtime, "geometry_tolerance", 24) or 24)
        if _geometry_close(geom, target, tol=tol):
            return True
        if isinstance(fallback_target, dict) and fallback_target is not target:
            return _geometry_close(geom, fallback_target, tol=tol)
        return False
    except Exception:
        return False
