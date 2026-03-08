from __future__ import annotations

import os
from collections.abc import Callable


def build_x11_env(*, display: str, xauthority: str | None) -> dict[str, str]:
    env = os.environ.copy()
    env["DISPLAY"] = display
    if xauthority:
        env["XAUTHORITY"] = xauthority
    return env


def resolve_x11_display(
    *,
    cached_display: str | None,
    configured_display: str | None,
    probe_display: Callable[[str], bool],
    logger: Callable[[str], None],
    label: str,
    fallback_candidates: tuple[str, ...] = (":0", ":1", ":2"),
) -> str:
    if cached_display and probe_display(cached_display):
        return cached_display

    candidates: list[str] = []
    configured = str(configured_display or "").strip()
    if configured:
        candidates.append(configured)
    for display in fallback_candidates:
        if display not in candidates:
            candidates.append(display)

    last_err: Exception | None = None
    for display in candidates:
        try:
            if probe_display(display):
                if configured and display != configured:
                    logger(f"{label} display fallback: configured={configured} -> using {display}")
                return display
        except Exception as exc:
            last_err = exc
            continue

    if last_err:
        raise RuntimeError(
            f"{label.lower()} X11 display probe failed "
            f"(configured={configured}): {last_err}"
        )
    raise RuntimeError(
        f"{label.lower()} X11 display not available "
        f"(tried: {', '.join(candidates)})"
    )
