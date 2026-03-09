from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any, Protocol

from .window_actions import (
    build_window_activate_command,
    build_window_close_command,
    build_window_fullscreen_command,
    build_window_key_command,
    build_window_move_resize_command,
)


class WindowFullscreenCommandBuilder(Protocol):
    def __call__(self, win_id: str, *, enabled: bool) -> list[str]: ...


def run_window_activate(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id))


def run_window_activate_host_runtime(*, runtime: Any, win_id: str) -> None:
    run_window_activate(
        win_id=win_id,
        build_command=build_window_activate_command,
        run_command=lambda command: subprocess.run(
            command,
            env=runtime._x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    )


def run_window_key(
    *,
    win_id: str,
    key: str,
    build_command: Callable[[str, str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id, key))


def run_window_key_host_runtime(*, runtime: Any, win_id: str, key: str) -> None:
    run_window_key(
        win_id=win_id,
        key=key,
        build_command=build_window_key_command,
        run_command=lambda command: subprocess.run(
            command,
            env=runtime._x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    )


def run_window_close(
    *,
    win_id: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id))


def run_window_close_host_runtime(*, runtime: Any, win_id: str) -> None:
    run_window_close(
        win_id=win_id,
        build_command=build_window_close_command,
        run_command=lambda command: subprocess.run(
            command,
            env=runtime._x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    )


def run_window_move_resize(
    *,
    win_id: str,
    geom: dict[str, int],
    build_command: Callable[[str, dict[str, int]], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id, geom))


def run_window_move_resize_host_runtime(
    *,
    runtime: Any,
    win_id: str,
    geom: dict[str, int],
) -> None:
    run_window_move_resize(
        win_id=win_id,
        geom=geom,
        build_command=build_window_move_resize_command,
        run_command=lambda command: subprocess.run(
            command,
            env=runtime._x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    )


def run_window_fullscreen(
    *,
    win_id: str,
    enabled: bool,
    build_command: WindowFullscreenCommandBuilder,
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(win_id, enabled=enabled))


def run_window_fullscreen_host_runtime(
    *,
    runtime: Any,
    win_id: str,
    enabled: bool,
) -> None:
    run_window_fullscreen(
        win_id=win_id,
        enabled=enabled,
        build_command=build_window_fullscreen_command,
        run_command=lambda command: subprocess.run(
            command,
            env=runtime._x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    )
