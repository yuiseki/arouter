from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any


def probe_x11_display(
    *,
    run_command: Callable[[list[str]], int],
) -> bool:
    return int(run_command(["xdpyinfo"])) == 0


def probe_x11_display_host_runtime(
    *,
    runtime: Any,
    display: str,
) -> bool:
    return probe_x11_display(
        run_command=lambda command: subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=runtime._env_for_display(display),
        ).returncode
    )
