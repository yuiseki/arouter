from __future__ import annotations

import pytest

from arouter import (
    launch_chromium_new_window,
    read_active_window_id,
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
