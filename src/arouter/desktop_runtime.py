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


def run_arrange_script(
    *,
    script_path: str,
    label: str,
    path_exists: Callable[[str], bool],
    run_command: Callable[[list[str]], Any],
) -> str:
    if not path_exists(script_path):
        raise RuntimeError(f"{label} script not found: {script_path}")
    cp = run_command(["bash", script_path])
    if int(getattr(cp, "returncode", 1)) != 0:
        err = (getattr(cp, "stderr", "") or getattr(cp, "stdout", "") or "").strip()
        raise RuntimeError(f"{label} failed: {err}")
    out = (getattr(cp, "stdout", "") or "").strip()
    if out:
        return out
    return f"{label} arranged"


def run_tmp_main_layout(
    *,
    script_path: str,
    mode: str,
    path_exists: Callable[[str], bool],
    run_command: Callable[[list[str]], Any],
) -> str:
    if not path_exists(script_path):
        raise RuntimeError(f"tmp_main.sh layout script not found: {script_path}")
    flag = f"--{mode}"
    cp = run_command(["bash", script_path, "layout", flag])
    if int(getattr(cp, "returncode", 1)) != 0:
        err = (getattr(cp, "stderr", "") or "").strip()
        raise RuntimeError(f"tmp_main.sh layout {flag} failed: {err}")
    return f"god_mode layout {mode}: ok"
