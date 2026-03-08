from __future__ import annotations

import pytest

from arouter import (
    build_window_presentation_snapshot,
    is_window_fullscreenish,
    resolve_window_restore_plan,
    top_right_region_from_screen_and_work_area,
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
