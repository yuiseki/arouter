from __future__ import annotations

from typing import Any


def build_live_cam_layout_targets_full(
    *,
    screen_w: int,
    screen_h: int,
    pids_by_port: dict[int, int],
    origin_x: int = 0,
    origin_y: int = 0,
) -> list[dict[str, Any]]:
    cell_w = max(1, screen_w // 2)
    cell_h = max(1, screen_h // 2)
    by_port = {
        9993: {"x": origin_x + 0, "y": origin_y + 0, "w": cell_w, "h": cell_h},
        9994: {"x": origin_x + cell_w, "y": origin_y + 0, "w": cell_w, "h": cell_h},
        9995: {"x": origin_x + 0, "y": origin_y + cell_h, "w": cell_w, "h": cell_h},
        9996: {"x": origin_x + cell_w, "y": origin_y + cell_h, "w": cell_w, "h": cell_h},
    }
    targets: list[dict[str, Any]] = []
    for port, geom in by_port.items():
        pid = pids_by_port.get(port)
        if not pid:
            raise RuntimeError(f"missing PID for live camera port {port}")
        targets.append({"pid": pid, **geom})
    return targets


def build_live_cam_layout_targets_compact(
    *,
    screen_w: int,
    screen_h: int,
    pids_by_port: dict[int, int],
    origin_x: int = 0,
    origin_y: int = 0,
) -> list[dict[str, Any]]:
    region_w = max(1, screen_w)
    region_h = max(1, screen_h)
    cell_w = max(1, region_w // 2)
    cell_h = max(1, region_h // 2)
    by_port = {
        9993: {"x": origin_x, "y": origin_y, "w": cell_w, "h": cell_h},
        9994: {"x": origin_x + cell_w, "y": origin_y, "w": cell_w, "h": cell_h},
        9995: {"x": origin_x, "y": origin_y + cell_h, "w": cell_w, "h": cell_h},
        9996: {"x": origin_x + cell_w, "y": origin_y + cell_h, "w": cell_w, "h": cell_h},
    }
    targets: list[dict[str, Any]] = []
    for port, geom in by_port.items():
        pid = pids_by_port.get(port)
        if not pid:
            raise RuntimeError(f"missing PID for live camera port {port}")
        targets.append({"pid": pid, **geom})
    return targets


def compact_live_cam_region_from_screen_and_work_area(
    *,
    screen_w: int,
    screen_h: int,
    work_area: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int]:
    qx = max(0, int(screen_w) // 2)
    qy = max(0, int(screen_h) // 2)
    qx2 = max(qx + 1, int(screen_w))
    qy2 = max(qy + 1, int(screen_h))

    if not work_area:
        return (qx, qy, max(1, qx2 - qx), max(1, qy2 - qy))

    wx, wy, ww, wh = [int(value) for value in work_area]
    wx2 = wx + max(1, ww)
    wy2 = wy + max(1, wh)
    x0 = max(qx, wx)
    y0 = max(qy, wy)
    x1 = min(qx2, wx2)
    y1 = min(qy2, wy2)
    if x1 <= x0 or y1 <= y0:
        return (qx, qy, max(1, qx2 - qx), max(1, qy2 - qy))
    return (x0, y0, max(1, x1 - x0), max(1, y1 - y0))
