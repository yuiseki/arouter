from __future__ import annotations

from collections.abc import Callable


def build_listen_pid_command(port: int) -> list[str]:
    return ["lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN", "-t"]


def parse_listen_pid_output(stdout: str) -> int | None:
    for line in (stdout or "").splitlines():
        try:
            return int(line.strip())
        except Exception:
            continue
    return None


def resolve_listen_pid(
    port: int,
    *,
    run_command: Callable[[list[str]], str],
) -> int | None:
    return parse_listen_pid_output(run_command(build_listen_pid_command(port)))
