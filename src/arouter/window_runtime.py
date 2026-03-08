from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class WindowFullscreenCommandBuilder(Protocol):
    def __call__(self, win_id: str, *, enabled: bool) -> list[str]: ...


def run_window_activate(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id))


def run_window_key(
    *,
    win_id: str,
    key: str,
    build_command: Callable[[str, str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id, key))


def run_window_close(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id))


def run_window_move_resize(
    *,
    win_id: str,
    geom: dict[str, int],
    build_command: Callable[[str, dict[str, int]], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id, geom))


def run_window_fullscreen(
    *,
    win_id: str,
    enabled: bool,
    build_command: WindowFullscreenCommandBuilder,
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id, enabled=enabled))
