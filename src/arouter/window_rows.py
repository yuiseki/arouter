from __future__ import annotations


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
