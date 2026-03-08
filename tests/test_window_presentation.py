from __future__ import annotations

import pytest

from arouter import (
    build_window_presentation_snapshot,
    geometry_close,
    is_window_fullscreenish,
    parse_desktop_size_from_wmctrl_output,
    parse_screen_size_from_xrandr_output,
    parse_work_area_from_wmctrl_output,
    resolve_expected_top_right_geometry,
    resolve_window_restore_plan,
    top_right_region_from_screen_and_work_area,
)


def test_geometry_close_within_tolerance() -> None:
    assert geometry_close(
        {"x": 2055, "y": 30, "w": 2038, "h": 1048},
        {"x": 2048, "y": 28, "w": 2048, "h": 1052},
        tol=12,
    )


def test_geometry_close_outside_tolerance() -> None:
    assert not geometry_close(
        {"x": 1448, "y": 720, "w": 1199, "h": 677},
        {"x": 2048, "y": 28, "w": 2048, "h": 1052},
        tol=24,
    )


def test_build_window_presentation_snapshot_sets_fields() -> None:
    assert build_window_presentation_snapshot(window_id="0x123", fullscreen=True) == {
        "window_id": "0x123",
        "fullscreen": True,
    }


def test_resolve_window_restore_plan_prefers_fullscreen() -> None:
    assert resolve_window_restore_plan(
        {"window_id": "0x123", "fullscreen": True},
        fallback_window_id="0x999",
        is_fullscreenish=False,
    ) == {"window_id": "0x123", "action": "fullscreen"}


def test_resolve_window_restore_plan_skips_top_right_when_current_window_looks_fullscreen() -> None:
    assert resolve_window_restore_plan(
        {"window_id": "0x123", "fullscreen": False},
        fallback_window_id="0x999",
        is_fullscreenish=True,
    ) == {"window_id": "0x123", "action": "skip_top_right"}


def test_resolve_window_restore_plan_uses_fallback_window_id_for_top_right() -> None:
    assert resolve_window_restore_plan(
        {"fullscreen": False},
        fallback_window_id="0x999",
        is_fullscreenish=False,
    ) == {"window_id": "0x999", "action": "top_right"}


def test_resolve_expected_top_right_geometry_uses_intersection_when_available() -> None:
    assert resolve_expected_top_right_geometry(
        screen=(4096, 2160),
        work_area=(0, 0, 4096, 2116),
        fallback_geometry={"x": 1, "y": 2, "w": 3, "h": 4},
    ) == {"x": 2048, "y": 0, "w": 2048, "h": 1080}


def test_resolve_expected_top_right_geometry_falls_back_when_screen_missing() -> None:
    assert resolve_expected_top_right_geometry(
        screen=None,
        work_area=None,
        fallback_geometry={"x": 1, "y": 2, "w": 3, "h": 4},
    ) == {"x": 1, "y": 2, "w": 3, "h": 4}


def test_parse_desktop_size_from_wmctrl_output_prefers_current_desktop() -> None:
    assert parse_desktop_size_from_wmctrl_output(
        "0  - DG: 1280x720 VP: 0,0 WA: 0,0 1280x680\n"
        "1  * DG: 1920x1080 VP: 0,0 WA: 0,0 1920x1040\n"
    ) == (1920, 1080)


def test_parse_screen_size_from_xrandr_output_prefers_primary_then_connected() -> None:
    assert parse_screen_size_from_xrandr_output(
        "HDMI-0 connected 1280x720+0+0\n"
        "DP-0 connected primary 4096x2160+0+0\n"
    ) == (4096, 2160)


def test_parse_work_area_from_wmctrl_output_returns_current_desktop_work_area() -> None:
    assert parse_work_area_from_wmctrl_output(
        "0  * DG: 4096x2160 VP: 0,0 WA: 0,0 4096x2116\n"
    ) == (0, 0, 4096, 2116)


def test_top_right_region_intersects_work_area() -> None:
    assert top_right_region_from_screen_and_work_area(
        screen_w=4096,
        screen_h=2160,
        work_area=(0, 0, 4096, 2116),
    ) == (2048, 0, 2048, 1080)


def test_top_right_region_rejects_invalid_screen_size() -> None:
    with pytest.raises(ValueError, match="invalid screen size"):
        top_right_region_from_screen_and_work_area(
            screen_w=0,
            screen_h=2160,
            work_area=None,
        )


def test_is_window_fullscreenish_matches_near_fullscreen_geometry() -> None:
    assert is_window_fullscreenish(
        {"x": 0, "y": 8, "w": 1910, "h": 1080},
        (1920, 1080),
        tol=16,
    )


def test_is_window_fullscreenish_rejects_small_window() -> None:
    assert not is_window_fullscreenish(
        {"x": 100, "y": 100, "w": 640, "h": 480},
        (1920, 1080),
    )
