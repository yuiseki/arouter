from __future__ import annotations

from collections.abc import Callable


def chromium_window_ids_from_wmctrl_lines(lines: list[str]) -> set[str]:
    ids: set[str] = set()
    for line in lines:
        if "Chromium" not in line:
            continue
        try:
            ids.add(line.split()[0].lower())
        except Exception:
            continue
    return ids


def window_title_from_wmctrl_lines(lines: list[str], win_id: str) -> str:
    target = (win_id or "").lower()
    if not target:
        return ""
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        if parts[0].lower() != target:
            continue
        return parts[3]
    return ""


def detect_new_window_id(
    *,
    before_ids: set[str],
    current_ids: Callable[[], set[str]],
    active_window_id: Callable[[], str | None],
    title_for_window_id: Callable[[str], str],
    title_hint: str,
    timeout_sec: float,
    now: Callable[[], float],
    sleep: Callable[[float], None],
    poll_interval_sec: float = 0.25,
) -> str:
    deadline = now() + timeout_sec
    while now() < deadline:
        after_ids = current_ids()
        new_ids = sorted(after_ids - before_ids)
        if new_ids:
            return new_ids[-1]
        sleep(poll_interval_sec)

    fallback_id = active_window_id()
    if fallback_id:
        title = title_for_window_id(fallback_id)
        if title_hint in title:
            return fallback_id
    raise RuntimeError(f"could not detect newly opened {title_hint} window")
