from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class VacuumTubeLoadCheckRuntime(Protocol):
    cdp_port: int | None
    target_geometry: dict[str, Any] | None
    geometry_tolerance: int | None

    def find_window_id(self) -> str | None: ...

    def get_window_geometry(self, win_id: str) -> dict[str, Any] | None: ...

    def _current_window_is_fullscreenish(self, win_id: str) -> bool: ...


def _geometry_close(actual: dict[str, Any], expected: dict[str, Any], *, tol: int = 24) -> bool:
    for key in ("x", "y", "w", "h"):
        try:
            if abs(int(actual.get(key, -999999)) - int(expected.get(key, -999999))) > tol:
                return False
        except Exception:
            return False
    return True


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
