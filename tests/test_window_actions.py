from __future__ import annotations

from arouter import (
    build_window_activate_command,
    build_window_key_command,
    build_window_minimize_command,
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
