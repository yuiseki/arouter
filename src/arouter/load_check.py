from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class VacuumTubeLoadCheckRuntime(Protocol):
    cdp_port: int | None
    target_geometry: dict[str, Any] | None
    geometry_tolerance: int | None

    def find_window_id(self) -> str | None: ...

    def get_window_geometry(self, win_id: str) -> dict[str, Any] | None: ...

    def _current_window_is_fullscreenish(self, win_id: str) -> bool: ...


def _geometry_close(actual: dict[str, Any], expected: dict[str, Any], *, tol: int = 24) -> bool:
    for key in ("x", "y", "w", "h"):
        try:
            if abs(int(actual.get(key, -999999)) - int(expected.get(key, -999999))) > tol:
                return False
        except Exception:
            return False
    return True


def load_check_bottom_left_geom(*, screen_w: int, screen_h: int) -> dict[str, int]:
    return {
        "x": 0,
        "y": max(0, int(screen_h) // 2),
        "w": max(1, int(screen_w) // 2),
        "h": max(1, int(screen_h) // 2),
    }


def is_vacuumtube_quadrant_mode_for_load_check(
    runtime: VacuumTubeLoadCheckRuntime,
    *,
    row_by_cdp_port: Callable[[int], dict[str, Any] | None],
) -> bool:
    try:
        row: dict[str, Any] | None = None
        wid: str | None = None
        geom: dict[str, Any] | None = None
        cdp_port = getattr(runtime, "cdp_port", None)
        if cdp_port:
            row = row_by_cdp_port(int(cdp_port))
        if row:
            wid = str(row.get("id") or "")
            geom = {"x": row.get("x"), "y": row.get("y"), "w": row.get("w"), "h": row.get("h")}
        else:
            wid = runtime.find_window_id()
            if not wid:
                return False
            geom = runtime.get_window_geometry(wid)
        if not wid:
            return False
        if bool(runtime._current_window_is_fullscreenish(wid)):
            return False
        target = None
        helper = getattr(runtime, "expected_top_right_geometry", None)
        if callable(helper):
            try:
                maybe_target = helper()
                if isinstance(maybe_target, dict):
                    target = maybe_target
            except Exception:
                target = None
        fallback_target = getattr(runtime, "target_geometry", None)
        if target is None and isinstance(fallback_target, dict):
            target = fallback_target
        if not isinstance(geom, dict) or not isinstance(target, dict):
            return False
        tol = int(getattr(runtime, "geometry_tolerance", 24) or 24)
        if _geometry_close(geom, target, tol=tol):
            return True
        if isinstance(fallback_target, dict) and fallback_target is not target:
            return _geometry_close(geom, fallback_target, tol=tol)
        return False
    except Exception:
        return False
