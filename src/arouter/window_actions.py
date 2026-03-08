from __future__ import annotations


def build_window_close_command(win_id: str) -> list[str]:
    return ["wmctrl", "-i", "-c", win_id]


def build_window_activate_command(win_id: str) -> list[str]:
    return ["xdotool", "windowactivate", "--sync", win_id]


def build_window_key_command(win_id: str, key: str) -> list[str]:
    return ["xdotool", "key", "--window", win_id, "--clearmodifiers", key]


def build_window_minimize_command(win_id: str) -> list[str]:
    return ["xdotool", "windowminimize", win_id]


def build_window_move_resize_command(win_id: str, geom: dict[str, int]) -> list[str]:
    spec = f"0,{geom['x']},{geom['y']},{geom['w']},{geom['h']}"
    return ["wmctrl", "-i", "-r", win_id, "-e", spec]


def build_window_fullscreen_command(win_id: str, *, enabled: bool) -> list[str]:
    op = "add,fullscreen" if enabled else "remove,fullscreen"
    return ["wmctrl", "-i", "-r", win_id, "-b", op]
