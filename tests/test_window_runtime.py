from __future__ import annotations

import subprocess

import pytest

from arouter import (
    build_window_fullscreen_command,
    run_window_activate,
    run_window_activate_host_runtime,
    run_window_close,
    run_window_close_host_runtime,
    run_window_fullscreen,
    run_window_fullscreen_host_runtime,
    run_window_key,
    run_window_key_host_runtime,
    run_window_move_resize,
    run_window_move_resize_host_runtime,
)


def test_run_window_activate_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_activate(
        win_id="0x123",
        build_command=lambda win_id: ["xdotool", "windowactivate", "--sync", win_id],
        run_command=commands.append,
    )

    assert commands == [["xdotool", "windowactivate", "--sync", "0x123"]]


def test_run_window_activate_host_runtime_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("subprocess.run", _run)
        run_window_activate_host_runtime(runtime=runtime, win_id="0x123")

    assert calls == [
        (
            ["xdotool", "windowactivate", "--sync", "0x123"],
            {
                "env": {"DISPLAY": ":0"},
                "check": False,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


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


def test_run_window_key_host_runtime_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("subprocess.run", _run)
        run_window_key_host_runtime(runtime=runtime, win_id="0x123", key="space")

    assert calls == [
        (
            ["xdotool", "key", "--window", "0x123", "--clearmodifiers", "space"],
            {
                "env": {"DISPLAY": ":0"},
                "check": False,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


def test_run_window_close_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_window_close(
        win_id="0xabc",
        build_command=lambda win_id: ["wmctrl", "-i", "-c", win_id],
        run_command=commands.append,
    )

    assert commands == [["wmctrl", "-i", "-c", "0xabc"]]


def test_run_window_close_host_runtime_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("subprocess.run", _run)
        run_window_close_host_runtime(runtime=runtime, win_id="0xabc")

    assert calls == [
        (
            ["wmctrl", "-i", "-c", "0xabc"],
            {
                "env": {"DISPLAY": ":0"},
                "check": False,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


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


def test_run_window_move_resize_host_runtime_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("subprocess.run", _run)
        run_window_move_resize_host_runtime(
            runtime=runtime,
            win_id="0xabc",
            geom={"x": 1, "y": 2, "w": 3, "h": 4},
        )

    assert calls == [
        (
            ["wmctrl", "-i", "-r", "0xabc", "-e", "0,1,2,3,4"],
            {
                "env": {"DISPLAY": ":0"},
                "check": False,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


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


def test_run_window_fullscreen_host_runtime_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("subprocess.run", _run)
        run_window_fullscreen_host_runtime(runtime=runtime, win_id="0xabc", enabled=False)

    assert calls == [
        (
            ["wmctrl", "-i", "-r", "0xabc", "-b", "remove,fullscreen"],
            {
                "env": {"DISPLAY": ":0"},
                "check": False,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


def test_run_window_fullscreen_supports_keyword_only_builder() -> None:
    commands: list[list[str]] = []

    run_window_fullscreen(
        win_id="0xabc",
        enabled=True,
        build_command=build_window_fullscreen_command,
        run_command=commands.append,
    )

    assert commands == [["wmctrl", "-i", "-r", "0xabc", "-b", "add,fullscreen"]]
