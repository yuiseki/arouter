from __future__ import annotations

import time
from pathlib import Path

from arouter import (
    build_live_cam_hide_response,
    build_live_cam_layout_response,
    build_live_cam_minimize_response,
    build_live_cam_open_result,
    build_live_cam_reopen_result,
    build_live_cam_start_command,
    build_live_cam_started_result,
    build_minimize_other_windows_response,
    collect_live_cam_pids,
    collect_live_cam_skip_pids,
    collect_window_ids_for_pids,
    find_missing_live_cam_window_ports,
    parse_key_value_stdout,
    resolve_existing_live_cam_windowed_pids,
    resolve_live_cam_action_state,
    resolve_live_cam_layout_bootstrap,
    run_live_cam_close_windows,
    run_live_cam_layout_flow,
    run_live_cam_minimize_windows,
    run_live_cam_open_flow,
    run_live_cam_parallel,
    run_live_cam_raise_windows,
    run_live_cam_start_flow,
    run_live_cam_window_action_flow,
    run_minimize_other_windows_flow,
)


def _unexpected_callback(message: str):
    return lambda: (_ for _ in ()).throw(AssertionError(message))


def _unexpected_reopen(message: str):
    return lambda _specs: (_ for _ in ()).throw(RuntimeError(message))


def test_run_live_cam_parallel_preserves_input_order() -> None:
    specs = [
        {"label": "a", "port": 9993},
        {"label": "b", "port": 9994},
        {"label": "c", "port": 9995},
    ]

    def worker(spec: dict[str, int | str]) -> dict[str, int | str]:
        if spec["label"] == "a":
            time.sleep(0.03)
        if spec["label"] == "b":
            time.sleep(0.01)
        return {"label": spec["label"], "port": spec["port"]}

    out = run_live_cam_parallel(specs, worker=worker, label="test")

    assert [x["label"] for x in out] == ["a", "b", "c"]
    assert [x["port"] for x in out] == [9993, 9994, 9995]


def test_run_live_cam_parallel_raises_with_port_context() -> None:
    specs = [
        {"label": "ok", "port": 9993},
        {"label": "ng", "port": 9994},
    ]

    def worker(spec: dict[str, int | str]) -> dict[str, bool]:
        if spec["label"] == "ng":
            raise RuntimeError("boom")
        return {"ok": True}

    try:
        run_live_cam_parallel(specs, worker=worker, label="test")
    except RuntimeError as exc:
        assert "9994" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_run_live_cam_raise_windows_executes_activate_commands_for_visible_windows() -> None:
    commands: list[list[str]] = []

    run_live_cam_raise_windows(
        [101, 102],
        window_id_lookup=lambda pid: {101: "0x1", 102: None}[pid],
        build_activate_command=lambda wid: ["xdotool", "windowactivate", "--sync", wid],
        run_command=commands.append,
    )

    assert commands == [["xdotool", "windowactivate", "--sync", "0x1"]]


def test_run_live_cam_close_windows_returns_only_closed_window_ids() -> None:
    commands: list[list[str]] = []

    closed = run_live_cam_close_windows(
        [201, 202, 203],
        window_id_lookup=lambda pid: {201: "0x10", 202: None, 203: "0x30"}[pid],
        build_close_command=lambda wid: ["wmctrl", "-i", "-c", wid],
        run_command=commands.append,
    )

    assert closed == ["0x10", "0x30"]
    assert commands == [["wmctrl", "-i", "-c", "0x10"], ["wmctrl", "-i", "-c", "0x30"]]


def test_run_live_cam_minimize_windows_collects_window_ids_and_runs_kwin_script() -> None:
    calls: list[object] = []

    out = run_live_cam_minimize_windows(
        [101, 102],
        window_id_lookup=lambda pid: {101: "0x1", 102: None}[pid],
        collect_window_ids=collect_window_ids_for_pids,
        run_minimize_script=lambda *, pids, plugin_name: calls.append(
            {
                "pids": pids,
                "plugin_name": plugin_name,
            }
        ),
        plugin_name="codex_live_cam_minimize_123",
    )

    assert out == ["0x1"]
    assert calls == [
        {
            "pids": [101, 102],
            "plugin_name": "codex_live_cam_minimize_123",
        }
    ]


def test_parse_key_value_stdout_ignores_non_kv_lines() -> None:
    parsed = parse_key_value_stdout("PID=123\njunk\nSESSION = livecam\n")

    assert parsed == {"PID": "123", "SESSION": "livecam"}


def test_build_live_cam_start_command_returns_expected_args() -> None:
    command = build_live_cam_start_command(
        Path("/tmp/start_silent_instance.sh"),
        {
            "session": "vacuumtube-bg-5",
            "port": 9996,
            "instance_dir": "/tmp/instance5",
        },
        display=":0",
    )

    assert command == [
        "bash",
        "/tmp/start_silent_instance.sh",
        "--session",
        "vacuumtube-bg-5",
        "--port",
        "9996",
        "--sink",
        "vacuumtube_silent",
        "--display",
        ":0",
        "--instance-dir",
        "/tmp/instance5",
    ]


def test_build_live_cam_started_result_merges_runtime_fields() -> None:
    result = build_live_cam_started_result(
        {"session": "vacuumtube-bg-5", "port": 9996},
        {"PID": "12345"},
    )

    assert result == {
        "PID": "12345",
        "port": "9996",
        "session_name": "vacuumtube-bg-5",
    }


def test_run_live_cam_start_flow_builds_and_executes_command() -> None:
    out = run_live_cam_start_flow(
        {"session": "vacuumtube-bg-5", "port": 9996},
        build_command=lambda spec: ["bash", f"/tmp/{spec['session']}.sh"],
        run_command=lambda cmd: type("CP", (), {"stdout": f"CMD={' '.join(cmd)}\nPID=12345\n"})(),
        parse_stdout=parse_key_value_stdout,
        build_result=build_live_cam_started_result,
    )

    assert out == {
        "CMD": "bash /tmp/vacuumtube-bg-5.sh",
        "PID": "12345",
        "port": "9996",
        "session_name": "vacuumtube-bg-5",
    }


def test_run_live_cam_open_flow_builds_results_via_parallel_runner() -> None:
    calls: list[dict[str, object]] = []

    def fake_parallel_runner(
        specs: list[dict[str, object]],
        *,
        worker,
        label: str,
    ) -> list[dict[str, object]]:
        calls.append({"specs": specs, "label": label})
        return [worker(spec) for spec in specs]

    specs = [{"label": "akihabara", "port": 9994}]

    out = run_live_cam_open_flow(
        specs,
        assign_live_camera=lambda spec: {"videoId": f"vid-{spec['port']}", "method": "direct-id"},
        build_result=lambda spec, payload: {
            "label": spec["label"],
            "port": spec["port"],
            "videoId": payload["videoId"],
        },
        label="live_cam_open",
        parallel_runner=fake_parallel_runner,
    )

    assert out == [{"label": "akihabara", "port": 9994, "videoId": "vid-9994"}]
    assert calls == [{"specs": specs, "label": "live_cam_open"}]


def test_collect_live_cam_pids_returns_none_when_any_pid_missing() -> None:
    out = collect_live_cam_pids(
        [{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101}.get(port),
    )

    assert out is None


def test_collect_live_cam_skip_pids_sorts_unique_pid_values() -> None:
    out = collect_live_cam_skip_pids(
        [{"port": 9993}, {"port": 9994}, {"port": 9995}],
        pid_lookup=lambda port: {9993: 101, 9994: 101, 9995: 103}.get(port),
    )

    assert out == [101, 103]


def test_find_missing_live_cam_window_ports_uses_visible_window_ids() -> None:
    missing = find_missing_live_cam_window_ports(
        {9993: 101, 9994: 102, 9995: 103},
        [{"id": "0x1", "pid": 101}, {"id": "0x2", "pid": 103}, {"pid": 102}],
    )

    assert missing == [9994]


def test_resolve_existing_live_cam_windowed_pids_returns_none_when_any_window_is_missing() -> None:
    out = resolve_existing_live_cam_windowed_pids(
        {9993: 101, 9994: 102},
        expected_count=2,
        rows=[{"id": "0x1", "pid": 101}],
    )

    assert out is None


def test_resolve_existing_live_cam_windowed_pids_returns_pid_map_when_all_windows_visible() -> None:
    out = resolve_existing_live_cam_windowed_pids(
        {9993: 101, 9994: 102},
        expected_count=2,
        rows=[{"id": "0x1", "pid": 101}, {"id": "0x2", "pid": 102}],
    )

    assert out == {9993: 101, 9994: 102}


def test_resolve_live_cam_action_state_fetches_state_when_pids_exist() -> None:
    out = resolve_live_cam_action_state(
        [{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101, 9994: 102}.get(port),
        state_fetcher=lambda pids: {"windows": [{"pid": 101}], "urls": [], "ports": sorted(pids)},
    )

    assert out == {
        "pids_by_port": {9993: 101, 9994: 102},
        "state": {"windows": [{"pid": 101}], "urls": [], "ports": [9993, 9994]},
    }


def test_resolve_live_cam_action_state_returns_empty_state_when_pid_missing() -> None:
    out = resolve_live_cam_action_state(
        [{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101}.get(port),
        state_fetcher=lambda _pids: {"unexpected": True},
    )

    assert out == {
        "pids_by_port": {},
        "state": {"windows": [], "urls": []},
    }


def test_resolve_live_cam_layout_bootstrap_uses_fast_path_when_windows_exist() -> None:
    logs: list[str] = []

    out = resolve_live_cam_layout_bootstrap(
        mode="compact",
        instances=[{"label": "shibuya", "port": 9993}],
        resolve_existing_windowed_pids=lambda: {9993: 101},
        find_stuck_specs=lambda: [],
        reopen_specs=lambda specs: [{"label": specs[0]["label"], "port": specs[0]["port"]}],
        ensure_scripts_present=_unexpected_callback("should not start cold"),
        ensure_instances_started=_unexpected_callback("should not start cold"),
        ensure_targets_opened=_unexpected_callback("should not open cold"),
        pid_lookup=lambda _port: 101,
        log=logs.append,
    )

    assert out == {
        "fast_path": True,
        "started": [],
        "opened": [],
        "open_errors": [],
        "pids_by_port": {9993: 101},
    }
    assert logs == ["LIVE_CAM compact fast-path: reusing existing windows and applying layout only"]


def test_resolve_live_cam_layout_bootstrap_reopen_failure_is_non_fatal() -> None:
    logs: list[str] = []

    out = resolve_live_cam_layout_bootstrap(
        mode="compact",
        instances=[{"label": "akihabara", "port": 9996}],
        resolve_existing_windowed_pids=lambda: {9996: 404},
        find_stuck_specs=lambda: [{"label": "akihabara", "port": 9996}],
        reopen_specs=_unexpected_reopen(
            "live_cam_reopen failed (akihabara:9996): timed out"
        ),
        ensure_scripts_present=lambda: None,
        ensure_instances_started=lambda: [],
        ensure_targets_opened=lambda: [],
        pid_lookup=lambda _port: 404,
        log=logs.append,
    )

    assert out["fast_path"] is True
    assert out["opened"] == []
    assert out["open_errors"] == ["live_cam_reopen failed (akihabara:9996): timed out"]
    assert any("re-opening 1 stuck instance(s): akihabara" in entry for entry in logs)


def test_resolve_live_cam_layout_bootstrap_cold_start_collects_pids_and_open_errors() -> None:
    started = [{"port": "9993"}]

    out = resolve_live_cam_layout_bootstrap(
        mode="compact",
        instances=[{"label": "shibuya", "port": 9993}, {"label": "shinjuku", "port": 9994}],
        resolve_existing_windowed_pids=lambda: None,
        find_stuck_specs=lambda: [],
        reopen_specs=lambda _specs: [],
        ensure_scripts_present=lambda: None,
        ensure_instances_started=lambda: started,
        ensure_targets_opened=lambda: (_ for _ in ()).throw(
            RuntimeError("live_cam_open failed (shinjuku:9994): timed out after 45.0 seconds")
        ),
        pid_lookup=lambda port: {9993: 601, 9994: 602}.get(port),
        log=lambda _message: None,
    )

    assert out == {
        "fast_path": False,
        "started": started,
        "opened": [],
        "open_errors": ["live_cam_open failed (shinjuku:9994): timed out after 45.0 seconds"],
        "pids_by_port": {9993: 601, 9994: 602},
    }


def test_run_live_cam_window_action_flow_uses_action_state_and_response_builder() -> None:
    acted_on: list[int] = []
    after_action_calls: list[str] = []

    result = run_live_cam_window_action_flow(
        [{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101, 9994: 102}.get(port),
        state_fetcher=lambda pids: {"windows": [], "urls": [], "ports": sorted(pids)},
        perform_window_action=lambda pids: acted_on.extend(pids) or ["0x1", "0x2"],
        build_response=lambda window_ids, ports, state: (
            f"ids={window_ids};ports={ports};state_ports={state['ports']}"
        ),
        after_action=lambda: after_action_calls.append("done"),
    )

    assert acted_on == [101, 102]
    assert after_action_calls == ["done"]
    assert result == "ids=['0x1', '0x2'];ports=[9993, 9994];state_ports=[9993, 9994]"


def test_collect_window_ids_for_pids_skips_missing_window_ids() -> None:
    out = collect_window_ids_for_pids(
        [123, 456, 789],
        window_id_lookup=lambda pid: {123: "0x1", 789: "0x3"}.get(pid),
    )

    assert out == ["0x1", "0x3"]


def test_build_live_cam_open_result_extracts_final_href() -> None:
    result = build_live_cam_open_result(
        {"label": "akihabara", "port": 9994},
        {
            "videoId": "abc123DEF45",
            "method": "direct-id",
            "final": {"href": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
        },
    )

    assert result == {
        "label": "akihabara",
        "port": 9994,
        "videoId": "abc123DEF45",
        "finalHref": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "method": "direct-id",
    }


def test_build_live_cam_reopen_result_keeps_reopen_fields() -> None:
    result = build_live_cam_reopen_result(
        {"label": "akihabara", "port": 9996},
        {"videoId": "abc123DEF45", "method": "direct-id"},
    )

    assert result == {
        "label": "akihabara",
        "port": 9996,
        "videoId": "abc123DEF45",
        "method": "direct-id",
    }


def test_build_live_cam_layout_response_includes_optional_open_errors() -> None:
    result = build_live_cam_layout_response(
        mode="compact",
        fast_path=True,
        screen_w=4096,
        screen_h=2160,
        work_area=(0, 0, 4096, 2116),
        started=[],
        opened=[{"label": "akihabara", "port": 9996}],
        state={"windows": [{"id": "0x1"}], "urls": []},
        open_errors=["live_cam_reopen failed (akihabara:9996): timed out"],
    )

    assert result == (
        'live camera wall {"mode": "compact", "fastPath": true, '
        '"screen": {"w": 4096, "h": 2160}, '
        '"workArea": {"x": 0, "y": 0, "w": 4096, "h": 2116}, '
        '"started": [], "opened": [{"label": "akihabara", "port": 9996}], '
        '"windows": [{"id": "0x1"}], "urls": [], '
        '"openErrors": ["live_cam_reopen failed (akihabara:9996): timed out"]}'
    )


def test_build_live_cam_hide_response_serializes_closed_windows() -> None:
    result = build_live_cam_hide_response(
        window_ids=["0x1", "0x2"],
        ports=[9993, 9994],
        state={"windows": [], "urls": []},
    )

    assert result == (
        'live camera wall hide {"closed": 2, "windowIds": ["0x1", "0x2"], '
        '"ports": [9993, 9994], "windows": [], "urls": []}'
    )


def test_build_live_cam_minimize_response_serializes_minimized_windows() -> None:
    result = build_live_cam_minimize_response(
        window_ids=["0x1"],
        ports=[9993],
        state={"windows": [], "urls": []},
    )

    assert result == (
        'live camera wall minimize {"minimized": 1, "windowIds": ["0x1"], '
        '"ports": [9993], "windows": [], "urls": []}'
    )


def test_build_minimize_other_windows_response_includes_skip_pid_list() -> None:
    assert (
        build_minimize_other_windows_response([101, 103])
        == "minimize other windows via KWin: ok (skipped live_cam pids=[101, 103])"
    )


def test_run_minimize_other_windows_flow_collects_skip_pids_and_runs_script() -> None:
    events: list[tuple[str, object]] = []

    result = run_minimize_other_windows_flow(
        instances=[{"port": "9993"}, {"port": "9994"}],
        pid_lookup=lambda port: {9993: 101, 9994: 202}.get(port),
        run_minimize_script=lambda *, skip_pids, plugin_name: events.append(
            ("run", {"skip_pids": list(skip_pids), "plugin_name": plugin_name})
        ),
        build_response=lambda skip_pids: events.append(("response", list(skip_pids))) or "done",
        plugin_name="plugin-name",
    )

    assert result == "done"
    assert events == [
        (
            "run",
            {
                "plugin_name": "plugin-name",
                "skip_pids": [101, 202],
            },
        ),
        ("response", [101, 202]),
    ]


def test_run_live_cam_layout_flow_applies_layout_raises_windows_and_builds_response() -> None:
    events: list[str] = []

    result = run_live_cam_layout_flow(
        mode="full",
        screen_w=4096,
        screen_h=2160,
        work_area=(0, 0, 4096, 2116),
        pids_by_port={9993: 101, 9994: 102},
        fast_path=True,
        started=[],
        opened=[{"label": "shibuya", "port": 9993}],
        open_errors=[],
        resolve_layout_plan=lambda mode, screen_w, screen_h, work_area, pids_by_port: {
            "work_area": {"x": 0, "y": 0, "w": 4096, "h": 2116},
            "targets": [{"pid": 101, "x": 1, "y": 2, "w": 3, "h": 4}],
            "plugin_name": "plugin-name",
            "keep_above": True,
        },
        apply_layout=lambda targets, plugin_name, keep_above, no_border: events.append(
            f"apply:{plugin_name}:{keep_above}:{no_border}:{targets[0]['pid']}"
        ),
        raise_windows_for_pids=lambda pids: events.append(f"raise:{pids}"),
        collect_runtime_state=lambda pids_by_port: {
            "windows": [{"pid": pids_by_port[9993]}],
            "urls": [],
        },
    )

    assert events == [
        "apply:plugin-name:True:True:101",
        "raise:[101, 102]",
    ]
    assert result == (
        'live camera wall {"mode": "full", "fastPath": true, '
        '"screen": {"w": 4096, "h": 2160}, '
        '"workArea": {"x": 0, "y": 0, "w": 4096, "h": 2116}, '
        '"started": [], "opened": [{"label": "shibuya", "port": 9993}], '
        '"windows": [{"pid": 101}], "urls": []}'
    )
