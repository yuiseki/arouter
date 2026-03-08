from __future__ import annotations

import pytest

from arouter import (
    launch_chromium_new_window,
    read_active_window_id,
    run_arrange_script,
    run_kwin_shortcut,
)


def test_launch_chromium_new_window_prefers_chromium_binary() -> None:
    events: list[object] = []

    launch_chromium_new_window(
        url="https://example.com",
        find_binary=lambda name: events.append(("which", name)) or (
            "/usr/bin/chromium" if name == "chromium" else None
        ),
        run_process=lambda command: events.append(("run", command)),
    )

    assert events == [
        ("which", "chromium"),
        ("run", ["/usr/bin/chromium", "--new-window", "https://example.com"]),
    ]


def test_launch_chromium_new_window_falls_back_to_chromium_browser() -> None:
    events: list[object] = []

    launch_chromium_new_window(
        url="https://example.com",
        find_binary=lambda name: events.append(("which", name)) or (
            "/usr/bin/chromium-browser" if name == "chromium-browser" else None
        ),
        run_process=lambda command: events.append(("run", command)),
    )

    assert events == [
        ("which", "chromium"),
        ("which", "chromium-browser"),
        ("run", ["/usr/bin/chromium-browser", "--new-window", "https://example.com"]),
    ]


def test_launch_chromium_new_window_raises_when_binary_missing() -> None:
    with pytest.raises(RuntimeError, match="chromium command not found"):
        launch_chromium_new_window(
            url="https://example.com",
            find_binary=lambda _name: None,
            run_process=lambda _command: None,
        )


def test_read_active_window_id_returns_hex_id() -> None:
    assert read_active_window_id(read_output=lambda: "123\n") == "0x7b"


def test_read_active_window_id_returns_none_for_invalid_output() -> None:
    assert read_active_window_id(read_output=lambda: "not-a-number") is None


def test_run_kwin_shortcut_builds_and_runs_command() -> None:
    commands: list[list[str]] = []

    run_kwin_shortcut(
        shortcut_name="Window Quick Tile Top Right",
        build_command=lambda shortcut_name: ["qdbus", "org.kde.kglobalaccel", shortcut_name],
        run_command=commands.append,
    )

    assert commands == [["qdbus", "org.kde.kglobalaccel", "Window Quick Tile Top Right"]]


class _CompletedProcess:
    def __init__(self, *, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_arrange_script_returns_stdout_when_present() -> None:
    out = run_arrange_script(
        script_path="/tmp/arrange.sh",
        label="weather mode",
        path_exists=lambda path: path == "/tmp/arrange.sh",
        run_command=lambda command: _CompletedProcess(
            returncode=0,
            stdout=f"ran {command[1]}\n",
        ),
    )

    assert out == "ran /tmp/arrange.sh"


def test_run_arrange_script_returns_default_success_text_without_stdout() -> None:
    out = run_arrange_script(
        script_path="/tmp/arrange.sh",
        label="world situation mode",
        path_exists=lambda _path: True,
        run_command=lambda _command: _CompletedProcess(returncode=0),
    )

    assert out == "world situation mode arranged"


def test_run_arrange_script_raises_when_script_missing() -> None:
    with pytest.raises(RuntimeError, match="weather mode script not found"):
        run_arrange_script(
            script_path="/tmp/missing.sh",
            label="weather mode",
            path_exists=lambda _path: False,
            run_command=lambda _command: _CompletedProcess(returncode=0),
        )


def test_run_arrange_script_raises_with_stderr_on_failure() -> None:
    with pytest.raises(RuntimeError, match="world situation mode failed: boom"):
        run_arrange_script(
            script_path="/tmp/arrange.sh",
            label="world situation mode",
            path_exists=lambda _path: True,
            run_command=lambda _command: _CompletedProcess(returncode=1, stderr="boom"),
        )
