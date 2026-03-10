from __future__ import annotations

from collections.abc import Callable
from typing import Any


def looks_like_weather_chromium_title(title: str) -> bool:
    normalized = (title or "").lower()
    return "chromium" in normalized and any(
        keyword in normalized
        for keyword in ("アメッシュ", "yahoo!天気", "天気・災害", "tenki.jp")
    )


def select_weather_candidate_window_ids(
    lines: list[str],
    last_weather_window_ids: list[str],
) -> list[str]:
    rows: list[dict[str, str]] = []
    by_id: dict[str, dict[str, str]] = {}
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        row = {"id": parts[0].lower(), "title": parts[3]}
        rows.append(row)
        by_id[row["id"]] = row

    candidate_ids: list[str] = []
    seen: set[str] = set()

    for wid in last_weather_window_ids:
        key = (wid or "").lower()
        if key and key in by_id and key not in seen:
            candidate_ids.append(key)
            seen.add(key)

    for row in rows:
        key = str(row.get("id") or "").lower()
        if not key or key in seen:
            continue
        if looks_like_weather_chromium_title(str(row.get("title") or "")):
            candidate_ids.append(key)
            seen.add(key)

    return candidate_ids


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


def window_rows_for_pids_from_wmctrl_lines(
    lines: list[str],
    *,
    pids: list[int],
) -> list[dict[str, Any]]:
    wanted = {int(pid) for pid in pids}
    rows: list[dict[str, Any]] = []
    for line in lines:
        parts = line.split(None, 8)
        if len(parts) < 8:
            continue
        try:
            pid = int(parts[2])
        except Exception:
            continue
        if pid not in wanted:
            continue
        try:
            row = {
                "id": parts[0],
                "pid": pid,
                "x": int(parts[3]),
                "y": int(parts[4]),
                "w": int(parts[5]),
                "h": int(parts[6]),
                "title": parts[8] if len(parts) >= 9 else "",
            }
        except Exception:
            continue
        rows.append(row)
    return rows


def find_window_row_by_pid_and_title(
    lines: list[str],
    *,
    pid: int,
    title_hint: str,
) -> dict[str, Any] | None:
    for row in window_rows_for_pids_from_wmctrl_lines(lines, pids=[pid]):
        if title_hint not in str(row.get("title") or ""):
            continue
        return row
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


def run_wait_for_window_id_host_runtime(
    *,
    runtime: Any,
    timeout_sec: float,
) -> str:
    return wait_for_window_id(
        current_window_id=runtime.find_window_id,
        timeout_sec=timeout_sec,
        now=runtime._time_now,
        sleep=runtime._sleep,
    )


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


def run_detect_new_window_id_host_runtime(
    *,
    runtime: Any,
    before_ids: set[str],
    timeout_sec: float,
    title_hint: str = "Chromium",
) -> str:
    return detect_new_window_id(
        before_ids=before_ids,
        current_ids=runtime._chromium_window_ids,
        active_window_id=runtime._active_window_id_from_xdotool,
        title_for_window_id=runtime._window_title_from_wmctrl,
        title_hint=title_hint,
        timeout_sec=timeout_sec,
        now=runtime._time_now,
        sleep=runtime._sleep,
    )
