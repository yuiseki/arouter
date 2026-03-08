from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from arouter import (
    build_load_check_wmctrl_commands,
    find_konsole_rows_for_tmux_client_pids,
    is_vacuumtube_quadrant_mode_for_load_check,
    load_check_bottom_left_geom,
    parse_konsole_window_rows,
    parse_tmux_client_pids,
    pid_ancestor_chain,
    prepare_load_check_konsole_placement,
    wait_for_new_window_row,
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


def test_wait_for_new_window_row_returns_last_new_row_before_timeout() -> None:
    timeline = [
        [],
        [{"id": "0x00a"}],
        [{"id": "0x00a"}, {"id": "0x00b"}],
    ]
    clock = {"now": 0.0}

    def row_provider() -> list[dict[str, str]]:
        index = min(int(clock["now"] / 0.15), len(timeline) - 1)
        return timeline[index]

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    row = wait_for_new_window_row(
        row_provider=row_provider,
        before_ids={"0x000"},
        timeout_sec=1.0,
        now=now,
        sleep=sleep,
    )

    assert row == {"id": "0x00a"}


def test_wait_for_new_window_row_returns_none_on_timeout() -> None:
    clock = {"now": 0.0}

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    row = wait_for_new_window_row(
        row_provider=lambda: [{"id": "0x000"}],
        before_ids={"0x000"},
        timeout_sec=0.3,
        now=now,
        sleep=sleep,
    )

    assert row is None


def test_prepare_load_check_konsole_placement_rejects_non_quadrant_mode() -> None:
    result = prepare_load_check_konsole_placement(
        quadrant_mode=False,
        screen=(4096, 2160),
        row={"id": "0x00a"},
        before_konsole_ids=None,
        wait_for_row=lambda: None,
        target_geom=load_check_bottom_left_geom,
    )

    assert result == {"applied": False, "reason": "vacuumtube_not_quadrant"}


def test_prepare_load_check_konsole_placement_requires_screen_size() -> None:
    result = prepare_load_check_konsole_placement(
        quadrant_mode=True,
        screen=None,
        row={"id": "0x00a"},
        before_konsole_ids=None,
        wait_for_row=lambda: None,
        target_geom=load_check_bottom_left_geom,
    )

    assert result == {"applied": False, "reason": "screen_size_unknown"}


def test_prepare_load_check_konsole_placement_requires_before_ids_when_row_missing() -> None:
    result = prepare_load_check_konsole_placement(
        quadrant_mode=True,
        screen=(4096, 2160),
        row=None,
        before_konsole_ids=None,
        wait_for_row=lambda: None,
        target_geom=load_check_bottom_left_geom,
    )

    assert result == {"applied": False, "reason": "konsole_window_not_specified"}


def test_prepare_load_check_konsole_placement_waits_for_new_window_when_row_missing() -> None:
    wait_for_row = mock.Mock(return_value={"id": "0x00b"})

    result = prepare_load_check_konsole_placement(
        quadrant_mode=True,
        screen=(4096, 2160),
        row=None,
        before_konsole_ids={"0x00a"},
        wait_for_row=wait_for_row,
        target_geom=load_check_bottom_left_geom,
    )

    assert result == {
        "applied": False,
        "ready": True,
        "window_id": "0x00b",
        "target": {"x": 0, "y": 1080, "w": 2048, "h": 1080},
    }
    wait_for_row.assert_called_once_with()


def test_prepare_load_check_konsole_placement_reports_missing_window_after_wait() -> None:
    result = prepare_load_check_konsole_placement(
        quadrant_mode=True,
        screen=(4096, 2160),
        row=None,
        before_konsole_ids={"0x00a"},
        wait_for_row=lambda: None,
        target_geom=load_check_bottom_left_geom,
    )

    assert result == {"applied": False, "reason": "konsole_window_not_found"}


def test_build_load_check_wmctrl_commands_returns_expected_sequence() -> None:
    commands = build_load_check_wmctrl_commands(
        window_id="0x00a",
        target={"x": 0, "y": 1080, "w": 2048, "h": 1080},
    )

    assert commands == [
        ["wmctrl", "-i", "-r", "0x00a", "-b", "remove,maximized_vert,maximized_horz"],
        ["wmctrl", "-i", "-r", "0x00a", "-b", "remove,fullscreen"],
        ["wmctrl", "-i", "-r", "0x00a", "-e", "0,0,1080,2048,1080"],
        ["wmctrl", "-i", "-r", "0x00a", "-e", "0,0,1080,2048,1080"],
    ]
