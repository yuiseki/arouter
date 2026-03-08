from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from arouter import (
    find_konsole_rows_for_tmux_client_pids,
    is_vacuumtube_quadrant_mode_for_load_check,
    load_check_bottom_left_geom,
    parse_konsole_window_rows,
    parse_tmux_client_pids,
    pid_ancestor_chain,
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


def test_parse_konsole_window_rows_filters_non_konsole_and_bad_rows() -> None:
    rows = parse_konsole_window_rows(
        "\n".join(
            [
                "0x00a 0 111 1 2 3 4 host Konsole - sysmon",
                "0x00b 0 222 5 6 7 8 host Chromium",
                "broken row",
            ]
        )
    )

    assert rows == [
        {
            "id": "0x00a",
            "pid": 111,
            "x": 1,
            "y": 2,
            "w": 3,
            "h": 4,
            "title": "Konsole - sysmon",
        }
    ]


def test_parse_tmux_client_pids_ignores_invalid_lines_and_failures() -> None:
    assert parse_tmux_client_pids("123\nabc\n0\n456\n", returncode=0) == [123, 456]
    assert parse_tmux_client_pids("123\n", returncode=1) == []


def test_pid_ancestor_chain_walks_parent_lookup_without_loops() -> None:
    parent_pid_for_pid = mock.Mock(side_effect=lambda pid: {500: 400, 400: 300, 300: 1}.get(pid))

    chain = pid_ancestor_chain(500, parent_pid_for_pid=parent_pid_for_pid)

    assert chain == [500, 400, 300]


def test_find_konsole_rows_for_tmux_client_pids_matches_ancestor_window_rows() -> None:
    rows = [
        {"id": "0x00a", "pid": 400, "title": "Konsole - sysmon"},
        {"id": "0x00b", "pid": 700, "title": "Konsole - other"},
    ]

    matched = find_konsole_rows_for_tmux_client_pids(
        rows,
        [500, 800],
        parent_pid_for_pid=lambda pid: {500: 450, 450: 400, 400: 1, 800: 700, 700: 1}.get(pid),
    )

    assert matched == [
        {"id": "0x00a", "pid": 400, "title": "Konsole - sysmon"},
        {"id": "0x00b", "pid": 700, "title": "Konsole - other"},
    ]
