from __future__ import annotations

import pytest

from arouter import (
    build_live_cam_layout_targets_compact,
    build_live_cam_layout_targets_full,
    compact_live_cam_region_from_screen_and_work_area,
)


def test_build_live_cam_layout_targets_full_tiles_screen_quadrants() -> None:
    targets = build_live_cam_layout_targets_full(
        screen_w=4096,
        screen_h=2160,
        pids_by_port={9993: 1, 9994: 2, 9995: 3, 9996: 4},
    )

    by_pid = {int(target["pid"]): target for target in targets}
    assert by_pid[1] == {"pid": 1, "x": 0, "y": 0, "w": 2048, "h": 1080}
    assert by_pid[2] == {"pid": 2, "x": 2048, "y": 0, "w": 2048, "h": 1080}
    assert by_pid[3] == {"pid": 3, "x": 0, "y": 1080, "w": 2048, "h": 1080}
    assert by_pid[4] == {"pid": 4, "x": 2048, "y": 1080, "w": 2048, "h": 1080}


def test_build_live_cam_layout_targets_compact_fills_given_region() -> None:
    targets = build_live_cam_layout_targets_compact(
        screen_w=2048,
        screen_h=1080,
        pids_by_port={9993: 1, 9994: 2, 9995: 3, 9996: 4},
        origin_x=2048,
        origin_y=1080,
    )

    by_pid = {int(target["pid"]): target for target in targets}
    assert by_pid[1] == {"pid": 1, "x": 2048, "y": 1080, "w": 1024, "h": 540}
    assert by_pid[2] == {"pid": 2, "x": 3072, "y": 1080, "w": 1024, "h": 540}
    assert by_pid[3] == {"pid": 3, "x": 2048, "y": 1620, "w": 1024, "h": 540}
    assert by_pid[4] == {"pid": 4, "x": 3072, "y": 1620, "w": 1024, "h": 540}


def test_build_live_cam_layout_targets_compact_respects_given_region_height() -> None:
    targets = build_live_cam_layout_targets_compact(
        screen_w=2048,
        screen_h=1036,
        pids_by_port={9993: 1, 9994: 2, 9995: 3, 9996: 4},
        origin_x=2048,
        origin_y=1080,
    )

    by_pid = {int(target["pid"]): target for target in targets}
    assert by_pid[1] == {"pid": 1, "x": 2048, "y": 1080, "w": 1024, "h": 518}
    assert by_pid[2] == {"pid": 2, "x": 3072, "y": 1080, "w": 1024, "h": 518}
    assert by_pid[3] == {"pid": 3, "x": 2048, "y": 1598, "w": 1024, "h": 518}
    assert by_pid[4] == {"pid": 4, "x": 3072, "y": 1598, "w": 1024, "h": 518}


def test_compact_live_cam_region_intersects_screen_quadrant_with_work_area() -> None:
    region = compact_live_cam_region_from_screen_and_work_area(
        screen_w=4096,
        screen_h=2160,
        work_area=(0, 0, 4096, 2116),
    )

    assert region == (2048, 1080, 2048, 1036)


def test_build_live_cam_layout_targets_compact_requires_all_ports() -> None:
    with pytest.raises(RuntimeError, match="missing PID for live camera port 9996"):
        build_live_cam_layout_targets_compact(
            screen_w=2048,
            screen_h=1080,
            pids_by_port={9993: 1, 9994: 2, 9995: 3},
        )
