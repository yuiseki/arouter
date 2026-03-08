from __future__ import annotations

from typing import Any


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
