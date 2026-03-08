from __future__ import annotations

from arouter import (
    build_xprop_wm_state_command,
    read_window_fullscreen_state,
    run_wmctrl_list_query,
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
