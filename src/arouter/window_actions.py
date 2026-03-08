from __future__ import annotations


def build_window_activate_command(win_id: str) -> list[str]:
    return ["xdotool", "windowactivate", "--sync", win_id]


def build_window_key_command(win_id: str, key: str) -> list[str]:
    return ["xdotool", "key", "--window", win_id, "--clearmodifiers", key]


def build_window_minimize_command(win_id: str) -> list[str]:
    return ["xdotool", "windowminimize", win_id]
