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


def find_window_id_by_pid_and_title(lines: list[str], *, pid: int, title_hint: str) -> str | None:
    for line in lines:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            row_pid = int(parts[2])
        except Exception:
            continue
        if row_pid != pid:
            continue
        if title_hint not in parts[4]:
            continue
        return parts[0]
    return None


def find_window_id_by_title(lines: list[str], *, title_hint: str) -> str | None:
    for line in lines:
        if title_hint in line:
            try:
                return line.split()[0]
            except Exception:
                continue
    return None


def find_window_geometry_from_wmctrl_lines(
    lines: list[str],
    win_id: str,
) -> dict[str, int] | None:
    target = (win_id or "").lower()
    if not target:
        return None
    for line in lines:
        parts = line.split(None, 7)
        if len(parts) < 7:
            continue
        if parts[0].lower() != target:
            continue
        try:
            return {
                "x": int(parts[2]),
                "y": int(parts[3]),
                "w": int(parts[4]),
                "h": int(parts[5]),
            }
        except Exception:
            return None
    return None


def wait_for_window_id(
    *,
    current_window_id: Callable[[], str | None],
    timeout_sec: float,
    now: Callable[[], float],
    sleep: Callable[[float], None],
    poll_interval_sec: float = 0.4,
) -> str:
    deadline = now() + timeout_sec
    while now() < deadline:
        win_id = current_window_id()
        if win_id:
            return win_id
        sleep(poll_interval_sec)
    raise RuntimeError("VacuumTube window not found")


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
