from __future__ import annotations


def build_listen_pid_command(port: int) -> list[str]:
    return ["lsof", "-nP", f"-iTCP:{int(port)}", "-sTCP:LISTEN", "-t"]


def parse_listen_pid_output(stdout: str) -> int | None:
    for line in (stdout or "").splitlines():
        try:
            return int(line.strip())
        except Exception:
            continue
    return None
