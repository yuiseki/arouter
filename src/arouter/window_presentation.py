from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


def geometry_close(actual: dict[str, Any], expected: dict[str, Any], *, tol: int = 24) -> bool:
    try:
        return all(
            abs(int(actual[key]) - int(expected[key])) <= tol
            for key in ("x", "y", "w", "h")
        )
    except Exception:
        return False


def build_window_presentation_snapshot(
    *,
    window_id: str | None,
    fullscreen: bool,
) -> dict[str, Any]:
    return {
        "window_id": window_id,
        "fullscreen": bool(fullscreen),
    }


def build_top_right_position_result(
    *,
    window_id: str,
    target: dict[str, Any],
    before: dict[str, Any] | None,
    tolerance: int,
) -> dict[str, Any]:
    return {
        "window_id": window_id,
        "target": dict(target),
        "before": before,
        "tolerance": int(tolerance),
        "ok": False,
        "method": None,
    }


def build_top_right_position_attempt_plan(
    *,
    retries: int,
    has_main_pid: bool,
) -> list[dict[str, Any]]:
    attempt_count = max(1, int(retries))
    plan: list[dict[str, Any]] = []
    if has_main_pid:
        for attempt in range(attempt_count):
            plan.append(
                {
                    "action": "kwin_frame",
                    "sleep": 0.25,
                    "method": f"kwin_frame_noborder_attempt_{attempt + 1}",
                }
            )
    for attempt in range(attempt_count):
        plan.append(
            {
                "action": "kwin_tile",
                "sleep": 0.35,
                "method": f"kwin_tile_attempt_{attempt + 1}",
            }
        )
    plan.append({"action": "wmctrl_move_resize", "sleep": 0.25, "method": "wmctrl_move_resize"})
    if has_main_pid:
        plan.append(
            {
                "action": "kwin_frame",
                "sleep": 0.25,
                "method": "kwin_frame_noborder_after_wmctrl",
            }
        )
    plan.append({"action": "kwin_tile", "sleep": 0.35, "method": "kwin_tile_after_wmctrl"})
    return plan


def finalize_top_right_position_result(
    result: dict[str, Any],
    *,
    geom: dict[str, Any] | None,
    expected: dict[str, Any],
    tol: int,
    method: str,
) -> dict[str, Any]:
    updated = dict(result)
    updated["after"] = geom
    updated["method"] = method
    updated["ok"] = bool(geom and geometry_close(geom, expected, tol=tol))
    return updated


def run_top_right_position_flow(
    *,
    win_id: str,
    target: dict[str, Any],
    before: dict[str, Any] | None,
    tolerance: int,
    retries: int,
    main_pid: int | None,
    clear_fullscreen_if_needed: Callable[[], None],
    kwin_frame_action: Callable[[int, dict[str, Any]], None],
    kwin_tile_action: Callable[[], None],
    wmctrl_move_resize_action: Callable[[str, dict[str, Any]], None],
    geometry_fetcher: Callable[[str], dict[str, Any] | None],
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    result = build_top_right_position_result(
        window_id=win_id,
        target=target,
        before=before,
        tolerance=tolerance,
    )
    if before and geometry_close(before, target, tol=tolerance):
        return finalize_top_right_position_result(
            result,
            geom=before,
            expected=target,
            tol=tolerance,
            method="already_ok",
        )

    clear_fullscreen_if_needed()

    for step in build_top_right_position_attempt_plan(
        retries=retries,
        has_main_pid=bool(main_pid),
    ):
        if step["action"] == "kwin_frame":
            if not main_pid:
                continue
            try:
                kwin_frame_action(int(main_pid), target)
            except Exception:
                continue
        elif step["action"] == "kwin_tile":
            kwin_tile_action()
        elif step["action"] == "wmctrl_move_resize":
            wmctrl_move_resize_action(win_id, target)
        else:
            continue

        sleep(float(step["sleep"]))
        geom = geometry_fetcher(win_id)
        result = finalize_top_right_position_result(
            result,
            geom=geom,
            expected=target,
            tol=tolerance,
            method=str(step["method"]),
        )
        if result["ok"]:
            return result

    return result


def run_window_restore_flow(
    *,
    presentation: dict[str, Any] | None,
    fallback_window_id: str,
    is_fullscreenish: bool,
    activate_window: Callable[[str], None],
    set_fullscreen: Callable[[str, bool], None],
    wait_fullscreen: Callable[[str, bool, float], bool],
    geometry_fetcher: Callable[[str], dict[str, Any] | None],
    ensure_top_right_position: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    plan = resolve_window_restore_plan(
        presentation,
        fallback_window_id=fallback_window_id,
        is_fullscreenish=is_fullscreenish,
    )
    action = str(plan["action"])
    window_id = str(plan["window_id"])

    if action == "fullscreen":
        activate_window(window_id)
        set_fullscreen(window_id, True)
        ok = wait_fullscreen(window_id, True, 3.0)
        return {
            "action": "fullscreen",
            "window_id": window_id,
            "fullscreen": ok,
            "after": geometry_fetcher(window_id),
        }

    if action == "skip_top_right":
        return {"action": "skip_top_right", "window_id": window_id}

    return {
        "action": "top_right",
        "window_id": window_id,
        "position": ensure_top_right_position(),
    }


def resolve_window_restore_plan(
    presentation: dict[str, Any] | None,
    *,
    fallback_window_id: str,
    is_fullscreenish: bool,
) -> dict[str, Any]:
    snap = presentation if isinstance(presentation, dict) else {}
    window_id = str(snap.get("window_id") or "") or str(fallback_window_id)
    if bool(snap.get("fullscreen")):
        return {"window_id": window_id, "action": "fullscreen"}
    if is_fullscreenish:
        return {"window_id": window_id, "action": "skip_top_right"}
    return {"window_id": window_id, "action": "top_right"}


def parse_desktop_size_from_wmctrl_output(text: str) -> tuple[int, int] | None:
    lines = str(text or "").splitlines()
    if not lines:
        return None
    preferred = [line for line in lines if "*" in line]
    for line in preferred + lines:
        match = re.search(r"DG:\s*(\d+)x(\d+)", line)
        if not match:
            continue
        try:
            return (int(match.group(1)), int(match.group(2)))
        except Exception:
            return None
    return None


def parse_screen_size_from_xrandr_output(text: str) -> tuple[int, int] | None:
    lines = str(text or "").splitlines()
    connected_lines = [line for line in lines if " connected primary " in line]
    if not connected_lines:
        connected_lines = [line for line in lines if " connected " in line]
    for line in connected_lines:
        match = re.search(r"\b(\d+)x(\d+)\+\d+\+\d+\b", line)
        if not match:
            continue
        try:
            width = int(match.group(1))
            height = int(match.group(2))
        except Exception:
            continue
        if width > 0 and height > 0:
            return (width, height)
    return None


def parse_work_area_from_wmctrl_output(text: str) -> tuple[int, int, int, int] | None:
    for line in str(text or "").splitlines():
        if "*" not in line:
            continue
        match = re.search(r"WA:\s*(\d+),(\d+)\s+(\d+)x(\d+)", line)
        if not match:
            continue
        try:
            x = int(match.group(1))
            y = int(match.group(2))
            width = int(match.group(3))
            height = int(match.group(4))
        except Exception:
            continue
        if width > 0 and height > 0:
            return (x, y, width, height)
    return None


def resolve_expected_top_right_geometry(
    *,
    screen: tuple[int, int] | None,
    work_area: tuple[int, int, int, int] | None,
    fallback_geometry: dict[str, int],
) -> dict[str, int]:
    if not screen:
        return dict(fallback_geometry)
    try:
        x, y, w, h = top_right_region_from_screen_and_work_area(
            screen_w=int(screen[0]),
            screen_h=int(screen[1]),
            work_area=work_area,
        )
    except Exception:
        return dict(fallback_geometry)
    if w <= 0 or h <= 0:
        return dict(fallback_geometry)
    return {"x": x, "y": y, "w": w, "h": h}


def top_right_region_from_screen_and_work_area(
    *,
    screen_w: int,
    screen_h: int,
    work_area: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int]:
    qx = int(screen_w) // 2
    qy = 0
    qw = int(screen_w) - qx
    qh = int(screen_h) // 2
    if qw <= 0 or qh <= 0:
        raise ValueError(f"invalid screen size for top-right region: {screen_w}x{screen_h}")
    if not work_area:
        return (qx, qy, qw, qh)
    try:
        wx, wy, ww, wh = (
            int(work_area[0]),
            int(work_area[1]),
            int(work_area[2]),
            int(work_area[3]),
        )
    except Exception:
        return (qx, qy, qw, qh)
    if ww <= 0 or wh <= 0:
        return (qx, qy, qw, qh)
    ix1 = max(qx, wx)
    iy1 = max(qy, wy)
    ix2 = min(qx + qw, wx + ww)
    iy2 = min(qy + qh, wy + wh)
    if ix2 <= ix1 or iy2 <= iy1:
        return (qx, qy, qw, qh)
    return (ix1, iy1, ix2 - ix1, iy2 - iy1)


def is_window_fullscreenish(
    geom: dict[str, Any] | None,
    desktop_size: tuple[int, int] | None,
    *,
    tol: int = 32,
) -> bool:
    if not geom or not desktop_size:
        return False
    try:
        sw, sh = int(desktop_size[0]), int(desktop_size[1])
        x = int(geom.get("x") or 0)
        y = int(geom.get("y") or 0)
        w = int(geom.get("w") or 0)
        h = int(geom.get("h") or 0)
    except Exception:
        return False

    return (
        abs(x - 0) <= tol
        and abs(y - 0) <= tol
        and abs(w - sw) <= tol
        and abs(h - sh) <= tol
    )
