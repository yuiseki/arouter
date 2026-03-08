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


def build_xprop_wm_state_command(win_id: str) -> list[str]:
    return ["xprop", "-id", win_id, "_NET_WM_STATE"]


def read_window_fullscreen_state(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], str],
) -> bool:
    return "_NET_WM_STATE_FULLSCREEN" in (run_command(build_command(win_id)) or "")
