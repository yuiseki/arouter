from __future__ import annotations

from collections.abc import Callable


def probe_x11_display(
    *,
    run_command: Callable[[list[str]], int],
) -> bool:
    return int(run_command(["xdpyinfo"])) == 0
