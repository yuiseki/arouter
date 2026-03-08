from __future__ import annotations

import shlex


def build_tmux_has_session_command(session_name: str) -> list[str]:
    return ["tmux", "has-session", "-t", session_name]


def build_tmux_kill_session_command(session_name: str) -> list[str]:
    return ["tmux", "kill-session", "-t", session_name]


def build_vacuumtube_tmux_start_command(
    *,
    session_name: str,
    display: str,
    xauthority: str | None,
    start_script: str,
) -> list[str]:
    export_display = f"export VACUUMTUBE_DISPLAY={shlex.quote(display)}; "
    export_xauthority = f"export XAUTHORITY={shlex.quote(xauthority)}; " if xauthority else ""
    inner = [
        "bash",
        "-lc",
        export_display + export_xauthority + f"exec {shlex.quote(start_script)}",
    ]
    return ["tmux", "new-session", "-d", "-s", session_name, shlex.join(inner)]
