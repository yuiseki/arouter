from __future__ import annotations

import pytest

from arouter import (
    build_xprop_wm_state_command,
    read_window_fullscreen_state,
    read_window_fullscreen_state_host_runtime,
    run_desktop_size_host_runtime_query,
    run_desktop_size_query,
    run_screen_size_host_runtime_query,
    run_screen_size_query,
    run_vacuumtube_window_id_query,
    run_window_geometry_query,
    run_window_id_query_by_pid_title,
    run_window_row_by_listen_port,
    run_window_rows_query_for_pids,
    run_window_title_query,
    run_wmctrl_list_host_runtime_query,
    run_wmctrl_list_query,
    run_work_area_host_runtime_query,
    run_work_area_query,
)


def test_run_wmctrl_list_query_builds_command_and_splits_lines() -> None:
    commands: list[list[str]] = []

    lines = run_wmctrl_list_query(
        geometry=True,
        with_pid=True,
        build_command=lambda *, geometry, with_pid: (
            ["wmctrl", "-lpG"] if geometry and with_pid else []
        ),
        run_command=lambda command: commands.append(command) or "0x1\n0x2\n",
    )

    assert lines == ["0x1", "0x2"]
    assert commands == [["wmctrl", "-lpG"]]


def test_run_wmctrl_list_host_runtime_query_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()

    with pytest.MonkeyPatch.context() as mp:
        calls: list[tuple[list[str], dict[str, object]]] = []

        class _CP:
            stdout = "0x1\n0x2\n"

        def _run(command: list[str], **kwargs: object) -> _CP:
            calls.append((command, kwargs))
            return _CP()

        mp.setattr("subprocess.run", _run)

        out = run_wmctrl_list_host_runtime_query(
            runtime=runtime,
            geometry=True,
            with_pid=True,
        )

    assert out == ["0x1", "0x2"]
    assert calls == [
        (
            ["wmctrl", "-lpG"],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "env": {"DISPLAY": ":0"},
            },
        )
    ]


def test_run_desktop_size_query_parses_wmctrl_output() -> None:
    commands: list[list[str]] = []

    out = run_desktop_size_query(
        run_command=lambda command: commands.append(command)
        or "0  * DG: 4096x2160  VP: 0,0  WA: 0,28 4096x2132  Workspace 1\n",
        parse_output=lambda stdout: (4096, 2160) if "4096x2160" in stdout else None,
    )

    assert out == (4096, 2160)
    assert commands == [["wmctrl", "-d"]]


def test_run_desktop_size_host_runtime_query_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()

    with pytest.MonkeyPatch.context() as mp:
        calls: list[tuple[list[str], dict[str, object]]] = []

        class _CP:
            stdout = "0  * DG: 4096x2160  VP: 0,0  WA: 0,28 4096x2132  Workspace 1\n"

        def _run(command: list[str], **kwargs: object) -> _CP:
            calls.append((command, kwargs))
            return _CP()

        mp.setattr("subprocess.run", _run)

        out = run_desktop_size_host_runtime_query(runtime=runtime)

    assert out == (4096, 2160)
    assert calls == [
        (
            ["wmctrl", "-d"],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "env": {"DISPLAY": ":0"},
            },
        )
    ]


def test_run_screen_size_query_parses_xrandr_output() -> None:
    commands: list[list[str]] = []

    out = run_screen_size_query(
        run_command=lambda command: commands.append(command)
        or "DP-0 connected primary 4096x2160+0+0\n",
        parse_output=lambda stdout: (4096, 2160) if "4096x2160" in stdout else None,
    )

    assert out == (4096, 2160)
    assert commands == [["xrandr", "--current"]]


def test_run_screen_size_host_runtime_query_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()

    with pytest.MonkeyPatch.context() as mp:
        calls: list[tuple[list[str], dict[str, object]]] = []

        class _CP:
            stdout = "DP-0 connected primary 4096x2160+0+0\n"

        def _run(command: list[str], **kwargs: object) -> _CP:
            calls.append((command, kwargs))
            return _CP()

        mp.setattr("subprocess.run", _run)

        out = run_screen_size_host_runtime_query(runtime=runtime)

    assert out == (4096, 2160)
    assert calls == [
        (
            ["xrandr", "--current"],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "env": {"DISPLAY": ":0"},
            },
        )
    ]


def test_run_work_area_query_parses_wmctrl_output() -> None:
    commands: list[list[str]] = []

    out = run_work_area_query(
        run_command=lambda command: commands.append(command)
        or "0  * DG: 4096x2160  VP: 0,0  WA: 0,28 4096x2132  Workspace 1\n",
        parse_output=lambda stdout: (0, 28, 4096, 2132) if "WA:" in stdout else None,
    )

    assert out == (0, 28, 4096, 2132)
    assert commands == [["wmctrl", "-d"]]


def test_run_work_area_host_runtime_query_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()

    with pytest.MonkeyPatch.context() as mp:
        calls: list[tuple[list[str], dict[str, object]]] = []

        class _CP:
            stdout = "0  * DG: 4096x2160  VP: 0,0  WA: 0,28 4096x2132  Workspace 1\n"

        def _run(command: list[str], **kwargs: object) -> _CP:
            calls.append((command, kwargs))
            return _CP()

        mp.setattr("subprocess.run", _run)

        out = run_work_area_host_runtime_query(runtime=runtime)

    assert out == (0, 28, 4096, 2132)
    assert calls == [
        (
            ["wmctrl", "-d"],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "env": {"DISPLAY": ":0"},
            },
        )
    ]


def test_run_window_row_by_listen_port_returns_matching_row() -> None:
    calls: list[object] = []

    row = run_window_row_by_listen_port(
        port=9992,
        pid_lookup=lambda port: 456 if port == 9992 else None,
        row_provider=lambda: calls.append("rows")
        or ["0x002 0 456 11 21 31 41 host VacuumTube"],
        find_row=lambda rows, *, pid, title_hint: calls.append((rows, pid, title_hint))
        or {"id": "0x002", "pid": pid},
    )

    assert row == {"id": "0x002", "pid": 456}
    assert calls == [
        "rows",
        (["0x002 0 456 11 21 31 41 host VacuumTube"], 456, "VacuumTube"),
    ]


def test_run_window_row_by_listen_port_returns_none_without_listen_pid() -> None:
    row = run_window_row_by_listen_port(
        port=9992,
        pid_lookup=lambda _port: None,
        row_provider=lambda: ["unused"],
        find_row=lambda _rows, *, pid, title_hint: {
            "id": "0x002",
            "pid": pid,
            "title_hint": title_hint,
        },
    )

    assert row is None


def test_run_window_id_query_by_pid_title_returns_matching_window_id() -> None:
    calls: list[object] = []

    win_id = run_window_id_query_by_pid_title(
        pid=456,
        row_provider=lambda: calls.append("rows")
        or ["0x002 0 456 host VacuumTube"],
        find_window_id=lambda rows, *, pid, title_hint: calls.append((rows, pid, title_hint))
        or "0x002",
        title_hint="VacuumTube",
    )

    assert win_id == "0x002"
    assert calls == [
        "rows",
        (["0x002 0 456 host VacuumTube"], 456, "VacuumTube"),
    ]


def test_run_window_rows_query_for_pids_returns_selected_rows() -> None:
    calls: list[object] = []

    rows = run_window_rows_query_for_pids(
        pids=[123, 456],
        row_provider=lambda: calls.append("rows")
        or ["0x001 0 123 1 2 3 4 host VacuumTube"],
        select_rows=lambda raw_rows, *, pids: calls.append((raw_rows, pids))
        or [{"id": "0x001", "pid": 123}],
    )

    assert rows == [{"id": "0x001", "pid": 123}]
    assert calls == [
        "rows",
        (["0x001 0 123 1 2 3 4 host VacuumTube"], [123, 456]),
    ]


def test_run_vacuumtube_window_id_query_prefers_pid_title_match() -> None:
    calls: list[object] = []

    win_id = run_vacuumtube_window_id_query(
        listen_port=9992,
        pid_lookup=lambda port: 456 if port == 9992 else None,
        rows_with_pid_provider=lambda: calls.append("pid_rows")
        or ["0x002 0 456 host VacuumTube"],
        rows_provider=lambda: calls.append("rows") or ["0x003 0 host VacuumTube"],
        find_by_pid_title=lambda rows, *, pid, title_hint: calls.append(
            ("pid", rows, pid, title_hint)
        )
        or "0x002",
        find_by_title=lambda rows, *, title_hint: calls.append(("title", rows, title_hint))
        or "0x003",
    )

    assert win_id == "0x002"
    assert calls == [
        "pid_rows",
        ("pid", ["0x002 0 456 host VacuumTube"], 456, "VacuumTube"),
    ]


def test_run_vacuumtube_window_id_query_falls_back_to_title_lookup() -> None:
    calls: list[object] = []

    win_id = run_vacuumtube_window_id_query(
        listen_port=9992,
        pid_lookup=lambda _port: None,
        rows_with_pid_provider=lambda: calls.append("pid_rows") or ["unused"],
        rows_provider=lambda: calls.append("rows") or ["0x003 0 host VacuumTube"],
        find_by_pid_title=lambda rows, *, pid, title_hint: calls.append(
            ("pid", rows, pid, title_hint)
        )
        or "0x002",
        find_by_title=lambda rows, *, title_hint: calls.append(("title", rows, title_hint))
        or "0x003",
    )

    assert win_id == "0x003"
    assert calls == [
        "rows",
        ("title", ["0x003 0 host VacuumTube"], "VacuumTube"),
    ]


def test_run_window_geometry_query_returns_geometry() -> None:
    calls: list[object] = []

    geometry = run_window_geometry_query(
        win_id="0xABC",
        row_provider=lambda: calls.append("rows")
        or ["0xabc 0 10 20 30 40 host VacuumTube"],
        find_geometry=lambda rows, target: calls.append((rows, target))
        or {"x": 10, "y": 20, "w": 30, "h": 40},
    )

    assert geometry == {"x": 10, "y": 20, "w": 30, "h": 40}
    assert calls == [
        "rows",
        (["0xabc 0 10 20 30 40 host VacuumTube"], "0xabc"),
    ]


def test_run_window_title_query_returns_title() -> None:
    calls: list[object] = []

    title = run_window_title_query(
        win_id="0x050000b5",
        row_provider=lambda: calls.append("rows")
        or ["0x050000b5 0 host 東京アメッシュ - Chromium"],
        title_lookup=lambda rows, win_id: calls.append((rows, win_id))
        or "東京アメッシュ - Chromium",
    )

    assert title == "東京アメッシュ - Chromium"
    assert calls == [
        "rows",
        (["0x050000b5 0 host 東京アメッシュ - Chromium"], "0x050000b5"),
    ]


def test_build_xprop_wm_state_command_matches_existing_contract() -> None:
    assert build_xprop_wm_state_command("0x123") == [
        "xprop",
        "-id",
        "0x123",
        "_NET_WM_STATE",
    ]


def test_read_window_fullscreen_state_checks_fullscreen_token() -> None:
    commands: list[list[str]] = []

    out = read_window_fullscreen_state(
        win_id="0x123",
        build_command=build_xprop_wm_state_command,
        run_command=lambda command: commands.append(command)
        or "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n",
    )

    assert out is True
    assert commands == [["xprop", "-id", "0x123", "_NET_WM_STATE"]]


def test_read_window_fullscreen_state_returns_false_without_token() -> None:
    out = read_window_fullscreen_state(
        win_id="0x123",
        build_command=build_xprop_wm_state_command,
        run_command=lambda _command: "_NET_WM_STATE(ATOM) = \n",
    )

    assert out is False


def test_read_window_fullscreen_state_host_runtime_uses_runtime_env() -> None:
    runtime = type("_Runtime", (), {"_x11_env": lambda self: {"DISPLAY": ":0"}})()

    with pytest.MonkeyPatch.context() as mp:
        calls: list[tuple[list[str], dict[str, object]]] = []

        class _CP:
            stdout = "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n"

        def _run(command: list[str], **kwargs: object) -> _CP:
            calls.append((command, kwargs))
            return _CP()

        mp.setattr("subprocess.run", _run)

        out = read_window_fullscreen_state_host_runtime(
            runtime=runtime,
            win_id="0x123",
        )

    assert out is True
    assert calls == [
        (
            ["xprop", "-id", "0x123", "_NET_WM_STATE"],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "env": {"DISPLAY": ":0"},
            },
        )
    ]
