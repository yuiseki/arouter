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
    run_load_check_konsole_placement_host_runtime,
    run_load_check_wmctrl_commands,
    run_system_load_check_flow,
    run_system_load_check_host_runtime,
    run_system_load_check_monitor_open_host_runtime,
    run_tmux_client_pid_query,
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


def test_run_tmux_client_pid_query_runs_tmux_and_parses_output() -> None:
    commands: list[list[str]] = []

    result = run_tmux_client_pid_query(
        "sysmon",
        run_command=lambda command: commands.append(command)
        or SimpleNamespace(stdout="100\n200\n", returncode=0),
        parse_output=lambda stdout, returncode: parse_tmux_client_pids(
            stdout, returncode=returncode
        ),
    )

    assert result == [100, 200]
    assert commands == [["tmux", "list-clients", "-t", "sysmon", "-F", "#{client_pid}"]]


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


def test_run_load_check_wmctrl_commands_executes_built_commands() -> None:
    events: list[list[str]] = []

    result = run_load_check_wmctrl_commands(
        window_id="0x00a",
        target={"x": 0, "y": 1080, "w": 2048, "h": 1080},
        build_commands=build_load_check_wmctrl_commands,
        run_command=events.append,
    )

    assert result == {
        "applied": True,
        "window_id": "0x00a",
        "target": {"x": 0, "y": 1080, "w": 2048, "h": 1080},
    }
    assert events == [
        ["wmctrl", "-i", "-r", "0x00a", "-b", "remove,maximized_vert,maximized_horz"],
        ["wmctrl", "-i", "-r", "0x00a", "-b", "remove,fullscreen"],
        ["wmctrl", "-i", "-r", "0x00a", "-e", "0,0,1080,2048,1080"],
        ["wmctrl", "-i", "-r", "0x00a", "-e", "0,0,1080,2048,1080"],
    ]


def test_run_system_load_check_flow_reuses_existing_session() -> None:
    logger = mock.Mock()
    raise_window_by_id = mock.Mock()
    apply_existing = mock.Mock(return_value={"applied": False})
    get_before_ids = mock.Mock()
    open_monitor = mock.Mock()
    apply_new = mock.Mock()

    result = run_system_load_check_flow(
        existing_rows=[{"id": "0x00c000aa"}],
        get_before_konsole_ids=get_before_ids,
        raise_window_by_id=raise_window_by_id,
        apply_placement_for_existing=apply_existing,
        open_monitor=open_monitor,
        apply_placement_for_new=apply_new,
        logger=logger,
    )

    assert result == "system load monitor reused (tmux=sysmon)"
    raise_window_by_id.assert_called_once_with("0x00c000aa")
    apply_existing.assert_called_once_with({"id": "0x00c000aa"})
    get_before_ids.assert_not_called()
    open_monitor.assert_not_called()
    apply_new.assert_not_called()


def test_run_system_load_check_flow_opens_new_session() -> None:
    logger = mock.Mock()
    get_before_ids = mock.Mock(return_value={"0x00a"})
    open_monitor = mock.Mock(return_value="tmux opened")
    apply_new = mock.Mock(return_value={"applied": True})

    result = run_system_load_check_flow(
        existing_rows=[],
        get_before_konsole_ids=get_before_ids,
        raise_window_by_id=mock.Mock(),
        apply_placement_for_existing=mock.Mock(),
        open_monitor=open_monitor,
        apply_placement_for_new=apply_new,
        logger=logger,
    )

    assert result == "system load monitor opened (tmux=sysmon)"
    get_before_ids.assert_called_once_with()
    open_monitor.assert_called_once_with()
    apply_new.assert_called_once_with({"0x00a"})
    logger.assert_any_call("system_load_check: tmux opened")


def test_run_load_check_konsole_placement_host_runtime_reads_runtime_methods() -> None:
    runtime = SimpleNamespace(
        log=mock.Mock(),
        vacuumtube=SimpleNamespace(
            _desktop_size=mock.Mock(return_value=(4096, 2160)),
            _x11_env=mock.Mock(return_value={"DISPLAY": ":1"}),
        ),
        _is_vacuumtube_quadrant_mode_for_load_check=mock.Mock(return_value=True),
        _wait_new_konsole_window=mock.Mock(return_value={"id": "0x00b"}),
        _load_check_bottom_left_geom=mock.Mock(
            return_value={"x": 0, "y": 1080, "w": 2048, "h": 1080}
        ),
    )

    with mock.patch("arouter.load_check.subprocess.run") as run_command:
        result = run_load_check_konsole_placement_host_runtime(
            runtime=runtime,
            before_konsole_ids={"0x00a"},
        )

    assert result == {
        "applied": True,
        "window_id": "0x00b",
        "target": {"x": 0, "y": 1080, "w": 2048, "h": 1080},
    }
    runtime._wait_new_konsole_window.assert_called_once_with(
        before_ids={"0x00a"},
        timeout_sec=8.0,
    )
    assert run_command.call_count == 4
    runtime.log.assert_called_once()


def test_run_system_load_check_monitor_open_host_runtime_uses_tmux_helper() -> None:
    with mock.patch("arouter.load_check.run_tmux_konsole_open", return_value="opened") as helper:
        out = run_system_load_check_monitor_open_host_runtime(
            script_path="/tmp/sysmon.sh",
            cwd="/work",
        )

    assert out == "opened"
    helper.assert_called_once()
    kwargs = helper.call_args.kwargs
    assert kwargs["script_path"] == "/tmp/sysmon.sh"
    assert kwargs["session_name"] == "sysmon"
    assert kwargs["cwd"] == "/work"
    assert callable(kwargs["path_exists"])
    assert callable(kwargs["run_command"])


def test_run_system_load_check_host_runtime_reads_runtime_methods() -> None:
    runtime = SimpleNamespace(
        log=mock.Mock(),
        _find_konsole_rows_for_tmux_session=mock.Mock(return_value=[{"id": "0x00c000aa"}]),
        _konsole_window_rows=mock.Mock(return_value=[{"id": "0x00c000aa"}]),
        _raise_window_by_id=mock.Mock(),
        _open_system_load_check_monitor=mock.Mock(return_value="opened"),
    )

    with mock.patch(
        "arouter.load_check.run_load_check_konsole_placement_host_runtime",
        return_value={"applied": False},
    ) as placement:
        out = run_system_load_check_host_runtime(runtime=runtime)

    assert out == "system load monitor reused (tmux=sysmon)"
    runtime._find_konsole_rows_for_tmux_session.assert_called_once_with("sysmon")
    runtime._raise_window_by_id.assert_called_once_with("0x00c000aa")
    placement.assert_called_once_with(runtime=runtime, row={"id": "0x00c000aa"})
