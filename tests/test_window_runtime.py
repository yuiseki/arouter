from __future__ import annotations

from arouter import (
    run_window_activate,
    run_window_close,
    run_window_fullscreen,
    run_window_key,
    run_window_move_resize,
)


def test_run_window_activate_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_activate(
        win_id="0x123",
        build_command=lambda win_id: ["xdotool", "windowactivate", "--sync", win_id],
        run_command=commands.append,
    )

    assert commands == [["xdotool", "windowactivate", "--sync", "0x123"]]


def test_run_window_key_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_key(
        win_id="0x123",
        key="space",
        build_command=lambda win_id, key: [
            "xdotool",
            "key",
            "--window",
            win_id,
            "--clearmodifiers",
            key,
        ],
        run_command=commands.append,
    )

    assert commands == [["xdotool", "key", "--window", "0x123", "--clearmodifiers", "space"]]


def test_run_window_close_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_close(
        win_id="0xabc",
        build_command=lambda win_id: ["wmctrl", "-i", "-c", win_id],
        run_command=commands.append,
    )

    assert commands == [["wmctrl", "-i", "-c", "0xabc"]]


def test_run_window_move_resize_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_move_resize(
        win_id="0xabc",
        geom={"x": 1, "y": 2, "w": 3, "h": 4},
        build_command=lambda win_id, geom: [
            "wmctrl",
            "-i",
            "-r",
            win_id,
            "-e",
            f"0,{geom['x']},{geom['y']},{geom['w']},{geom['h']}",
        ],
        run_command=commands.append,
    )

    assert commands == [["wmctrl", "-i", "-r", "0xabc", "-e", "0,1,2,3,4"]]


def test_run_window_fullscreen_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_fullscreen(
        win_id="0xabc",
        enabled=False,
        build_command=lambda win_id, enabled: [
            "wmctrl",
            "-i",
            "-r",
            win_id,
            "-b",
            "remove,fullscreen" if not enabled else "add,fullscreen",
        ],
        run_command=commands.append,
    )

    assert commands == [["wmctrl", "-i", "-r", "0xabc", "-b", "remove,fullscreen"]]
