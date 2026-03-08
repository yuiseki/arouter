from __future__ import annotations

from collections.abc import Callable


def run_system_webcam_mode(
    *,
    minimize_live_camera: Callable[[], str],
    god_mode_layout: Callable[[str], str],
) -> str:
    minimize_result = minimize_live_camera()
    webcam_result = god_mode_layout("frontmost")
    return f"{minimize_result}; {webcam_result}"


def run_system_normal_mode(
    *,
    god_mode_layout: Callable[[str], str],
    show_live_camera_compact: Callable[[], str],
    minimize_other_windows: Callable[[], str],
) -> str:
    results: list[str] = []
    try:
        god_mode_layout("full-screen")
        results.append(god_mode_layout("backmost"))
    except Exception as exc:
        results.append(f"god_mode_layout error: {exc}")
    try:
        results.append(show_live_camera_compact())
    except Exception as exc:
        results.append(f"live_cam_wall error: {exc}")
    try:
        results.append(minimize_other_windows())
    except Exception as exc:
        results.append(f"minimize error: {exc}")
    return "; ".join(results)
