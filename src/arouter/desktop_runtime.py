from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .kwin_scripts import build_kwin_invoke_shortcut_command
from .tmux_commands import build_tmux_has_session_command


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


def run_active_window_id_query(
    *,
    read_output: Callable[[], str],
    parse_output: Callable[..., str | None],
) -> str | None:
    return parse_output(read_output=read_output)


def run_active_window_id_host_runtime_query(*, runtime: Any) -> str | None:
    return run_active_window_id_query(
        read_output=lambda: subprocess.run(
            ["xdotool", "getactivewindow"],
            env=runtime._x11_env(),
            check=False,
            text=True,
            capture_output=True,
        ).stdout
        or "",
        parse_output=read_active_window_id,
    )


def run_tmux_has_session_query(
    *,
    session_name: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> bool:
    cp = run_command(build_command(session_name))
    return int(getattr(cp, "returncode", 1)) == 0


def run_tmux_has_session_host_runtime(*, runtime: Any) -> bool:
    return run_tmux_has_session_query(
        session_name=str(runtime.tmux_session),
        build_command=build_tmux_has_session_command,
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        ),
    )


def run_kwin_shortcut(
    *,
    shortcut_name: str,
    build_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], Any],
) -> None:
    run_command(build_command(shortcut_name))


def run_kwin_shortcut_host_runtime(
    *,
    runtime: Any,
    shortcut_name: str,
) -> None:
    run_kwin_shortcut(
        shortcut_name=shortcut_name,
        build_command=build_kwin_invoke_shortcut_command,
        run_command=lambda command: subprocess.run(
            command,
            env=runtime._x11_env(),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    )


def run_launch_chromium_new_window_host_runtime(*, runtime: Any, url: str) -> None:
    launch_chromium_new_window(
        url=url,
        find_binary=shutil.which,
        run_process=lambda command: subprocess.Popen(
            command,
            env=runtime._x11_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        ),
    )


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


def run_arrange_script_host_runtime(
    *,
    script_path: str,
    label: str,
    env: dict[str, str] | None = None,
) -> str:
    return run_arrange_script(
        script_path=script_path,
        label=label,
        path_exists=lambda path: Path(path).is_file(),
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        ),
    )


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


def run_tmp_main_layout_host_runtime(
    *,
    script_path: str,
    mode: str,
) -> str:
    return run_tmp_main_layout(
        script_path=script_path,
        mode=mode,
        path_exists=lambda path: Path(path).is_file(),
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        ),
    )


def run_tmux_konsole_open(
    *,
    script_path: str,
    session_name: str,
    cwd: str,
    path_exists: Callable[[str], bool],
    run_command: Callable[[list[str], str], Any],
) -> str:
    if not path_exists(script_path):
        raise RuntimeError(f"tmux konsole script not found: {script_path}")
    cp = run_command(
        ["bash", script_path, "open", "--session", session_name, "--recreate"],
        cwd,
    )
    if int(getattr(cp, "returncode", 1)) != 0:
        err = (getattr(cp, "stderr", "") or getattr(cp, "stdout", "") or "").strip()
        raise RuntimeError(f"tmux konsole open failed: {err}")
    return (getattr(cp, "stdout", "") or "").strip()
