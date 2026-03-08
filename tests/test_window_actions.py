from __future__ import annotations

from arouter import (
    build_window_activate_command,
    build_window_close_command,
    build_window_fullscreen_command,
    build_window_key_command,
    build_window_minimize_command,
    build_window_move_resize_command,
)


def test_build_window_activate_command_matches_existing_xdotool_contract() -> None:
    assert build_window_activate_command("0x123") == [
        "xdotool",
        "windowactivate",
        "--sync",
        "0x123",
    ]


def test_build_window_key_command_matches_existing_xdotool_contract() -> None:
    assert build_window_key_command("0x123", "space") == [
        "xdotool",
        "key",
        "--window",
        "0x123",
        "--clearmodifiers",
        "space",
    ]


def test_build_window_minimize_command_matches_existing_xdotool_contract() -> None:
    assert build_window_minimize_command("0x123") == [
        "xdotool",
        "windowminimize",
        "0x123",
    ]


def test_build_window_close_command_matches_existing_wmctrl_contract() -> None:
    assert build_window_close_command("0x123") == [
        "wmctrl",
        "-i",
        "-c",
        "0x123",
    ]


def test_build_window_move_resize_command_matches_existing_wmctrl_contract() -> None:
    assert build_window_move_resize_command("0x123", {"x": 1, "y": 2, "w": 3, "h": 4}) == [
        "wmctrl",
        "-i",
        "-r",
        "0x123",
        "-e",
        "0,1,2,3,4",
    ]


def test_build_window_fullscreen_command_switches_add_and_remove_modes() -> None:
    assert build_window_fullscreen_command("0x123", enabled=True) == [
        "wmctrl",
        "-i",
        "-r",
        "0x123",
        "-b",
        "add,fullscreen",
    ]
    assert build_window_fullscreen_command("0x123", enabled=False) == [
        "wmctrl",
        "-i",
        "-r",
        "0x123",
        "-b",
        "remove,fullscreen",
    ]
