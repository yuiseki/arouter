from __future__ import annotations

from arouter import (
    build_xprop_wm_state_command,
    read_window_fullscreen_state,
    run_desktop_size_query,
    run_screen_size_query,
    run_wmctrl_list_query,
    run_work_area_query,
)


def test_run_wmctrl_list_query_builds_command_and_splits_lines() -> None:
    commands: list[list[str]] = []

    lines = run_wmctrl_list_query(
        geometry=True,
        with_pid=True,
        build_command=lambda *, geometry, with_pid: (
            ["wmctrl", "-lpG"] if geometry and with_pid else []
        ),
        run_command=lambda command: commands.append(command) or "0x1\n0x2\n",
    )

    assert lines == ["0x1", "0x2"]
    assert commands == [["wmctrl", "-lpG"]]


def test_run_desktop_size_query_parses_wmctrl_output() -> None:
    commands: list[list[str]] = []

    out = run_desktop_size_query(
        run_command=lambda command: commands.append(command)
        or "0  * DG: 4096x2160  VP: 0,0  WA: 0,28 4096x2132  Workspace 1\n",
        parse_output=lambda stdout: (4096, 2160) if "4096x2160" in stdout else None,
    )

    assert out == (4096, 2160)
    assert commands == [["wmctrl", "-d"]]


def test_run_screen_size_query_parses_xrandr_output() -> None:
    commands: list[list[str]] = []

    out = run_screen_size_query(
        run_command=lambda command: commands.append(command)
        or "DP-0 connected primary 4096x2160+0+0\n",
        parse_output=lambda stdout: (4096, 2160) if "4096x2160" in stdout else None,
    )

    assert out == (4096, 2160)
    assert commands == [["xrandr", "--current"]]


def test_run_work_area_query_parses_wmctrl_output() -> None:
    commands: list[list[str]] = []

    out = run_work_area_query(
        run_command=lambda command: commands.append(command)
        or "0  * DG: 4096x2160  VP: 0,0  WA: 0,28 4096x2132  Workspace 1\n",
        parse_output=lambda stdout: (0, 28, 4096, 2132) if "WA:" in stdout else None,
    )

    assert out == (0, 28, 4096, 2132)
    assert commands == [["wmctrl", "-d"]]


def test_build_xprop_wm_state_command_matches_existing_contract() -> None:
    assert build_xprop_wm_state_command("0x123") == [
        "xprop",
        "-id",
        "0x123",
        "_NET_WM_STATE",
    ]


def test_read_window_fullscreen_state_checks_fullscreen_token() -> None:
    commands: list[list[str]] = []

    out = read_window_fullscreen_state(
        win_id="0x123",
        build_command=build_xprop_wm_state_command,
        run_command=lambda command: commands.append(command)
        or "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n",
    )

    assert out is True
    assert commands == [["xprop", "-id", "0x123", "_NET_WM_STATE"]]


def test_read_window_fullscreen_state_returns_false_without_token() -> None:
    out = read_window_fullscreen_state(
        win_id="0x123",
        build_command=build_xprop_wm_state_command,
        run_command=lambda _command: "_NET_WM_STATE(ATOM) = \n",
    )

    assert out is False
