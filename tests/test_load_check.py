from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from arouter import (
    is_vacuumtube_quadrant_mode_for_load_check,
    load_check_bottom_left_geom,
)


def test_load_check_bottom_left_geom_uses_left_bottom_quadrant() -> None:
    geom = load_check_bottom_left_geom(screen_w=4096, screen_h=2160)

    assert geom == {"x": 0, "y": 1080, "w": 2048, "h": 1080}


def test_is_vacuumtube_quadrant_mode_for_load_check_detects_target_geometry() -> None:
    runtime = SimpleNamespace(
        cdp_port=None,
        find_window_id=mock.Mock(return_value="0x123"),
        get_window_geometry=mock.Mock(return_value={"x": 2048, "y": 28, "w": 2048, "h": 1052}),
        target_geometry={"x": 2048, "y": 28, "w": 2048, "h": 1052},
        geometry_tolerance=24,
        _current_window_is_fullscreenish=mock.Mock(return_value=False),
    )

    result = is_vacuumtube_quadrant_mode_for_load_check(
        runtime,
        row_by_cdp_port=lambda _port: None,
    )

    assert result is True


def test_is_vacuumtube_quadrant_mode_for_load_check_prefers_main_cdp_window_row() -> None:
    runtime = SimpleNamespace(
        cdp_port=9992,
        find_window_id=mock.Mock(return_value="0x999"),
        get_window_geometry=mock.Mock(return_value={"x": 0, "y": 0, "w": 100, "h": 100}),
        target_geometry={"x": 2048, "y": 28, "w": 2048, "h": 1052},
        geometry_tolerance=24,
        _current_window_is_fullscreenish=mock.Mock(return_value=False),
    )
    row_by_cdp_port = mock.Mock(
        return_value={"id": "0x123", "x": 2048, "y": 28, "w": 2048, "h": 1052}
    )

    result = is_vacuumtube_quadrant_mode_for_load_check(
        runtime,
        row_by_cdp_port=row_by_cdp_port,
    )

    assert result is True
    row_by_cdp_port.assert_called_once_with(9992)


def test_is_vacuumtube_quadrant_mode_for_load_check_uses_expected_geometry_helper() -> None:
    runtime = SimpleNamespace(
        cdp_port=9992,
        find_window_id=mock.Mock(return_value="0x999"),
        get_window_geometry=mock.Mock(return_value={"x": 999, "y": 999, "w": 1, "h": 1}),
        target_geometry={"x": 2048, "y": 28, "w": 2048, "h": 1052},
        expected_top_right_geometry=mock.Mock(
            return_value={"x": 2048, "y": 0, "w": 2048, "h": 1080}
        ),
        geometry_tolerance=24,
        _current_window_is_fullscreenish=mock.Mock(return_value=False),
    )
    row_by_cdp_port = mock.Mock(
        return_value={"id": "0x123", "x": 2048, "y": 0, "w": 2048, "h": 1080}
    )

    result = is_vacuumtube_quadrant_mode_for_load_check(
        runtime,
        row_by_cdp_port=row_by_cdp_port,
    )

    assert result is True
    runtime.expected_top_right_geometry.assert_called_once_with()
