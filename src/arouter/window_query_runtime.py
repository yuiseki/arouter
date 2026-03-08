from __future__ import annotations

from collections.abc import Callable


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


def run_desktop_size_query(
    *,
    run_command: Callable[[list[str]], str],
    parse_output: Callable[[str], tuple[int, int] | None],
) -> tuple[int, int]:
    size = parse_output(run_command(["wmctrl", "-d"]))
    if size:
        return size
    raise RuntimeError("desktop size not found via wmctrl -d")


def run_screen_size_query(
    *,
    run_command: Callable[[list[str]], str],
    parse_output: Callable[[str], tuple[int, int] | None],
) -> tuple[int, int]:
    size = parse_output(run_command(["xrandr", "--current"]))
    if size:
        return size
    raise RuntimeError("primary screen size not found via xrandr --current")


def run_work_area_query(
    *,
    run_command: Callable[[list[str]], str],
    parse_output: Callable[[str], tuple[int, int, int, int] | None],
) -> tuple[int, int, int, int] | None:
    return parse_output(run_command(["wmctrl", "-d"]))


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


def build_xprop_wm_state_command(win_id: str) -> list[str]:
    return ["xprop", "-id", win_id, "_NET_WM_STATE"]


def read_window_fullscreen_state(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], str],
) -> bool:
    return "_NET_WM_STATE_FULLSCREEN" in (run_command(build_command(win_id)) or "")
