from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any, cast

from .listen_ports import run_listen_pid_host_runtime_query
from .window_presentation import (
    parse_desktop_size_from_wmctrl_output,
    parse_screen_size_from_xrandr_output,
    parse_work_area_from_wmctrl_output,
)
from .window_queries import build_wmctrl_list_command
from .window_rows import (
    find_window_geometry_from_wmctrl_lines,
    find_window_id_by_pid_and_title,
    find_window_id_by_title,
    find_window_row_by_pid_and_title,
    window_rows_for_pids_from_wmctrl_lines,
    window_title_from_wmctrl_lines,
)


def run_wmctrl_list_query(
    *,
    geometry: bool,
    with_pid: bool,
    build_command: Callable[..., list[str]],
    run_command: Callable[[list[str]], str],
) -> list[str]:
    return run_command(
        build_command(geometry=geometry, with_pid=with_pid)
    ).splitlines()


def run_wmctrl_list_host_runtime_query(
    *,
    runtime: Any,
    geometry: bool,
    with_pid: bool,
) -> list[str]:
    return run_wmctrl_list_query(
        geometry=geometry,
        with_pid=with_pid,
        build_command=build_wmctrl_list_command,
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=runtime._x11_env(),
        ).stdout
        or "",
    )


def run_desktop_size_query(
    *,
    run_command: Callable[[list[str]], str],
    parse_output: Callable[[str], tuple[int, int] | None],
) -> tuple[int, int]:
    size = parse_output(run_command(["wmctrl", "-d"]))
    if size:
        return size
    raise RuntimeError("desktop size not found via wmctrl -d")


def run_desktop_size_host_runtime_query(*, runtime: Any) -> tuple[int, int]:
    return run_desktop_size_query(
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=runtime._x11_env(),
        ).stdout
        or "",
        parse_output=parse_desktop_size_from_wmctrl_output,
    )


def run_screen_size_query(
    *,
    run_command: Callable[[list[str]], str],
    parse_output: Callable[[str], tuple[int, int] | None],
) -> tuple[int, int]:
    size = parse_output(run_command(["xrandr", "--current"]))
    if size:
        return size
    raise RuntimeError("primary screen size not found via xrandr --current")


def run_screen_size_host_runtime_query(*, runtime: Any) -> tuple[int, int]:
    return run_screen_size_query(
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=runtime._x11_env(),
        ).stdout
        or "",
        parse_output=parse_screen_size_from_xrandr_output,
    )


def run_work_area_query(
    *,
    run_command: Callable[[list[str]], str],
    parse_output: Callable[[str], tuple[int, int, int, int] | None],
) -> tuple[int, int, int, int] | None:
    return parse_output(run_command(["wmctrl", "-d"]))


def run_work_area_host_runtime_query(*, runtime: Any) -> tuple[int, int, int, int] | None:
    return run_work_area_query(
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=runtime._x11_env(),
        ).stdout
        or "",
        parse_output=parse_work_area_from_wmctrl_output,
    )


def run_window_row_by_listen_port(
    *,
    port: int,
    pid_lookup: Callable[[int], int | None],
    row_provider: Callable[[], list[str]],
    find_row: Callable[..., dict[str, object] | None],
) -> dict[str, object] | None:
    pid = pid_lookup(int(port))
    if not pid:
        return None
    return find_row(
        row_provider(),
        pid=int(pid),
        title_hint="VacuumTube",
    )


def run_window_row_by_listen_port_host_runtime(
    *,
    runtime: Any,
    port: int,
) -> dict[str, object] | None:
    return run_window_row_by_listen_port(
        port=port,
        pid_lookup=runtime._pid_listening_on_tcp_port,
        row_provider=lambda: runtime._wmctrl_rows(geometry=True, with_pid=True),
        find_row=find_window_row_by_pid_and_title,
    )


def run_window_id_query_by_pid_title(
    *,
    pid: int,
    row_provider: Callable[[], list[str]],
    find_window_id: Callable[..., str | None],
    title_hint: str,
) -> str | None:
    return find_window_id(
        row_provider(),
        pid=int(pid),
        title_hint=title_hint,
    )


def run_window_rows_query_for_pids(
    *,
    pids: list[int],
    row_provider: Callable[[], list[str]],
    select_rows: Callable[..., list[dict[str, object]]],
) -> list[dict[str, object]]:
    return list(
        select_rows(
            row_provider(),
            pids=[int(pid) for pid in pids],
        )
    )


def run_vacuumtube_window_id_query(
    *,
    listen_port: int,
    pid_lookup: Callable[[int], int | None],
    rows_with_pid_provider: Callable[[], list[str]],
    rows_provider: Callable[[], list[str]],
    find_by_pid_title: Callable[..., str | None],
    find_by_title: Callable[..., str | None],
) -> str | None:
    main_pid = pid_lookup(int(listen_port))
    if main_pid:
        try:
            win_id = find_by_pid_title(
                rows_with_pid_provider(),
                pid=int(main_pid),
                title_hint="VacuumTube",
            )
            if win_id:
                return win_id
        except Exception:
            pass
    return find_by_title(rows_provider(), title_hint="VacuumTube")


def run_vacuumtube_window_id_host_runtime_query(
    *,
    runtime: Any,
    listen_port: int,
) -> str | None:
    return run_vacuumtube_window_id_query(
        listen_port=listen_port,
        pid_lookup=run_listen_pid_host_runtime_query,
        rows_with_pid_provider=lambda: run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=False,
            with_pid=True,
        ),
        rows_provider=lambda: run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=False,
            with_pid=False,
        ),
        find_by_pid_title=find_window_id_by_pid_and_title,
        find_by_title=find_window_id_by_title,
    )


def run_window_geometry_query(
    *,
    win_id: str,
    row_provider: Callable[[], list[str]],
    find_geometry: Callable[[list[str], str], dict[str, object] | None],
) -> dict[str, object] | None:
    return find_geometry(row_provider(), str(win_id).lower())


def run_window_geometry_host_runtime_query(
    *,
    runtime: Any,
    win_id: str,
) -> dict[str, object] | None:
    find_geometry = cast(
        Callable[[list[str], str], dict[str, object] | None],
        find_window_geometry_from_wmctrl_lines,
    )
    return run_window_geometry_query(
        win_id=win_id,
        row_provider=lambda: run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=True,
            with_pid=False,
        ),
        find_geometry=find_geometry,
    )


def run_window_title_query(
    *,
    win_id: str,
    row_provider: Callable[[], list[str]],
    title_lookup: Callable[[list[str], str], str],
) -> str:
    return title_lookup(row_provider(), str(win_id))


def run_window_title_host_runtime_query(
    *,
    runtime: Any,
    win_id: str,
) -> str:
    return run_window_title_query(
        win_id=win_id,
        row_provider=lambda: run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=False,
            with_pid=False,
        ),
        title_lookup=window_title_from_wmctrl_lines,
    )


def run_window_id_by_pid_title_host_runtime_query(
    *,
    runtime: Any,
    pid: int,
    title_hint: str,
) -> str | None:
    return run_window_id_query_by_pid_title(
        pid=pid,
        row_provider=lambda: run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=False,
            with_pid=True,
        ),
        find_window_id=find_window_id_by_pid_and_title,
        title_hint=title_hint,
    )


def run_window_rows_for_pids_host_runtime_query(
    *,
    runtime: Any,
    pids: list[int],
) -> list[dict[str, object]]:
    return run_window_rows_query_for_pids(
        pids=pids,
        row_provider=lambda: run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=True,
            with_pid=True,
        ),
        select_rows=window_rows_for_pids_from_wmctrl_lines,
    )


def build_xprop_wm_state_command(win_id: str) -> list[str]:
    return ["xprop", "-id", win_id, "_NET_WM_STATE"]


def read_window_fullscreen_state(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], str],
) -> bool:
    return "_NET_WM_STATE_FULLSCREEN" in (run_command(build_command(win_id)) or "")


def read_window_fullscreen_state_host_runtime(
    *,
    runtime: Any,
    win_id: str,
) -> bool:
    return read_window_fullscreen_state(
        win_id=win_id,
        build_command=build_xprop_wm_state_command,
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=runtime._x11_env(),
        ).stdout
        or "",
    )
