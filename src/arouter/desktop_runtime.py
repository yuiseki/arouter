from __future__ import annotations

from collections.abc import Callable
from typing import Any


def launch_chromium_new_window(
    *,
    url: str,
    find_binary: Callable[[str], str | None],
    run_process: Callable[[list[str]], Any],
) -> None:
    bin_path = find_binary("chromium") or find_binary("chromium-browser")
    if not bin_path:
        raise RuntimeError("chromium command not found")
    run_process([bin_path, "--new-window", url])


def read_active_window_id(
    *,
    read_output: Callable[[], str],
) -> str | None:
    try:
        active_id = int((read_output() or "").strip())
    except Exception:
        return None
    if active_id <= 0:
        return None
    return f"0x{active_id:x}"


def run_kwin_shortcut(
    *,
    shortcut_name: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(shortcut_name))
