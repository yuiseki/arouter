from __future__ import annotations

import time
from pathlib import Path
from unittest import mock

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
    run_live_cam_close_windows_host_runtime_flow,
    run_live_cam_existing_windowed_pids_host_runtime_query,
    run_live_cam_existing_windowed_pids_query,
    run_live_cam_hide_flow,
    run_live_cam_hide_host_runtime_flow,
    run_live_cam_layout_controller_flow,
    run_live_cam_layout_flow,
    run_live_cam_layout_host_runtime_flow,
    run_live_cam_layout_runtime_flow,
    run_live_cam_minimize_flow,
    run_live_cam_minimize_host_runtime_flow,
    run_live_cam_minimize_windows,
    run_live_cam_minimize_windows_host_runtime_flow,
    run_live_cam_open_flow,
    run_live_cam_open_instances_flow,
    run_live_cam_open_instances_host_runtime_flow,
    run_live_cam_parallel,
    run_live_cam_raise_windows,
    run_live_cam_raise_windows_host_runtime_flow,
    run_live_cam_reopen_specs_flow,
    run_live_cam_start_flow,
    run_live_cam_start_instances_flow,
    run_live_cam_start_instances_host_runtime_flow,
    run_live_cam_start_script_flow,
    run_live_cam_start_script_host_runtime_flow,
    run_live_cam_window_action_flow,
    run_minimize_other_windows_flow,
    run_minimize_other_windows_host_runtime_flow,
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
        build_script=lambda pids: (calls.append(("build", pids)) or "SCRIPT"),
        write_temp_script=lambda text, prefix: (
            calls.append(("write", text, prefix)) or "/tmp/demo.js"
        ),
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: calls.append(("run", command)),
        sleep=lambda seconds: calls.append(("sleep", seconds)),
        cleanup=lambda path: calls.append(("cleanup", path)),
        plugin_name="codex_live_cam_minimize_123",
    )

    assert out == ["0x1"]
    assert calls == [
        ("build", [101, 102]),
        ("write", "SCRIPT", "codex-kwin-livecam-minimize-"),
        ("run", ["qdbus", "load", "/tmp/demo.js", "codex_live_cam_minimize_123"]),
        ("run", ["qdbus", "start"]),
        ("sleep", 0.4),
        ("run", ["qdbus", "unload", "codex_live_cam_minimize_123"]),
        ("cleanup", "/tmp/demo.js"),
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


def test_run_live_cam_start_script_flow_uses_default_build_parse_and_result_helpers() -> None:
    out = run_live_cam_start_script_flow(
        {"session": "vacuumtube-bg-5", "port": 9996, "instance_dir": "/tmp/instance5"},
        start_silent_script=Path("/tmp/start_silent_instance.sh"),
        display=":0",
        run_command=lambda cmd: type("CP", (), {"stdout": f"CMD={' '.join(cmd)}\nPID=12345\n"})(),
    )

    assert out == {
        "CMD": (
            "bash /tmp/start_silent_instance.sh --session vacuumtube-bg-5 --port 9996 "
            "--sink vacuumtube_silent --display :0 --instance-dir /tmp/instance5"
        ),
        "PID": "12345",
        "port": "9996",
        "session_name": "vacuumtube-bg-5",
    }


def test_run_live_cam_start_script_host_runtime_flow_reads_runtime_methods() -> None:
    class FakeRuntime:
        start_silent_script = Path("/tmp/start_silent_instance.sh")

        def _resolve_display(self) -> str:
            return ":0"

        def _run_live_cam_start_command(self, command: list[str]) -> object:
            return type("CP", (), {"stdout": f"CMD={' '.join(command)}\nPID=12345\n"})()

    out = run_live_cam_start_script_host_runtime_flow(
        spec={
            "session": "vacuumtube-bg-5",
            "port": 9996,
            "instance_dir": "/tmp/instance5",
        },
        runtime=FakeRuntime(),
    )

    assert out == {
        "CMD": (
            "bash /tmp/start_silent_instance.sh --session vacuumtube-bg-5 --port 9996 "
            "--sink vacuumtube_silent --display :0 --instance-dir /tmp/instance5"
        ),
        "PID": "12345",
        "port": "9996",
        "session_name": "vacuumtube-bg-5",
    }


def test_run_live_cam_start_instances_flow_ensures_scripts_and_runs_parallel() -> None:
    events: list[str] = []
    specs = [{"port": 9993}, {"port": 9994}]

    def fake_parallel_runner(current_specs, *, worker, label: str):
        events.append(f"parallel:{label}:{len(current_specs)}")
        return [worker(spec) for spec in current_specs]

    out = run_live_cam_start_instances_flow(
        specs,
        ensure_scripts_present=lambda: events.append("ensure_scripts"),
        start_instance=lambda spec: (
            events.append(f"start:{spec['port']}") or {"port": spec["port"]}
        ),
        parallel_runner=fake_parallel_runner,
    )

    assert out == [{"port": 9993}, {"port": 9994}]
    assert events == [
        "ensure_scripts",
        "parallel:live_cam_start:2",
        "start:9993",
        "start:9994",
    ]


def test_run_live_cam_start_instances_host_runtime_flow_reads_runtime_methods() -> None:
    events: list[str] = []

    class FakeRuntime:
        def _live_camera_instance_specs(self) -> list[dict[str, int]]:
            return [{"port": 9993}, {"port": 9994}]

        def _ensure_scripts_present(self) -> None:
            events.append("ensure_scripts")

        def _start_instance(self, spec: dict[str, int]) -> dict[str, int]:
            events.append(f"start:{spec['port']}")
            return {"port": spec["port"]}

        def _run_instances_parallel(self, current_specs, *, worker, label: str):
            events.append(f"parallel:{label}:{len(current_specs)}")
            return [worker(spec) for spec in current_specs]

    out = run_live_cam_start_instances_host_runtime_flow(runtime=FakeRuntime())

    assert out == [{"port": 9993}, {"port": 9994}]
    assert events == [
        "ensure_scripts",
        "parallel:live_cam_start:2",
        "start:9993",
        "start:9994",
    ]


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


def test_run_live_cam_open_instances_flow_uses_default_open_result_builder() -> None:
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

    out = run_live_cam_open_instances_flow(
        specs,
        assign_live_camera=lambda spec: {
            "videoId": f"vid-{spec['port']}",
            "method": "direct-id",
            "final": {"href": f"https://www.youtube.com/tv#/watch?v=vid-{spec['port']}"},
        },
        parallel_runner=fake_parallel_runner,
    )

    assert out == [
        {
            "label": "akihabara",
            "port": 9994,
            "videoId": "vid-9994",
            "finalHref": "https://www.youtube.com/tv#/watch?v=vid-9994",
            "method": "direct-id",
        }
    ]
    assert calls == [{"specs": specs, "label": "live_cam_open"}]


def test_run_live_cam_open_instances_host_runtime_flow_reads_runtime_methods() -> None:
    calls: list[dict[str, object]] = []

    class FakeRuntime:
        def _live_camera_instance_specs(self) -> list[dict[str, int | str]]:
            return [{"label": "akihabara", "port": 9994}]

        def _assign_live_camera(self, spec: dict[str, object]) -> dict[str, object]:
            return {
                "videoId": f"vid-{spec['port']}",
                "method": "direct-id",
                "final": {"href": f"https://www.youtube.com/tv#/watch?v=vid-{spec['port']}"},
            }

        def _run_instances_parallel(self, specs, *, worker, label: str):
            calls.append({"specs": specs, "label": label})
            return [worker(spec) for spec in specs]

    out = run_live_cam_open_instances_host_runtime_flow(runtime=FakeRuntime())

    assert out == [
        {
            "label": "akihabara",
            "port": 9994,
            "videoId": "vid-9994",
            "finalHref": "https://www.youtube.com/tv#/watch?v=vid-9994",
            "method": "direct-id",
        }
    ]
    assert calls == [{"specs": [{"label": "akihabara", "port": 9994}], "label": "live_cam_open"}]


def test_run_live_cam_raise_windows_host_runtime_flow_reads_runtime_methods() -> None:
    calls: list[list[str]] = []

    class FakeRuntime:
        def _window_id_for_pid(self, pid: int) -> str | None:
            return {101: "0x1", 102: None}.get(pid)

        def _run_x11_command(self, command: list[str]) -> object:
            calls.append(command)
            return object()

    run_live_cam_raise_windows_host_runtime_flow(runtime=FakeRuntime(), pids=[101, 102])

    assert calls == [["xdotool", "windowactivate", "--sync", "0x1"]]


def test_run_live_cam_close_windows_host_runtime_flow_reads_runtime_methods() -> None:
    calls: list[list[str]] = []

    class FakeRuntime:
        def _window_id_for_pid(self, pid: int) -> str | None:
            return {201: "0x10", 202: None, 203: "0x30"}.get(pid)

        def _run_x11_command(self, command: list[str]) -> object:
            calls.append(command)
            return object()

    closed = run_live_cam_close_windows_host_runtime_flow(
        runtime=FakeRuntime(),
        pids=[201, 202, 203],
    )

    assert closed == ["0x10", "0x30"]
    assert calls == [
        ["wmctrl", "-i", "-c", "0x10"],
        ["wmctrl", "-i", "-c", "0x30"],
    ]


def test_run_live_cam_minimize_windows_host_runtime_flow_reads_runtime_methods() -> None:
    calls: list[object] = []

    class FakeRuntime:
        def _window_id_for_pid(self, pid: int) -> str | None:
            return {101: "0x1", 102: None}.get(pid)

        def _run_x11_command(self, command: list[str]) -> object:
            calls.append(("run", command))
            return object()

        def _sleep(self, seconds: float) -> None:
            calls.append(("sleep", seconds))

        def _cleanup_temp_path(self, path: str) -> None:
            calls.append(("cleanup", path))

    with mock.patch("arouter.live_cam_runtime.time.time", return_value=0.0):
        out = run_live_cam_minimize_windows_host_runtime_flow(
            runtime=FakeRuntime(),
            pids=[101, 102],
        )

    assert out == ["0x1"]
    assert calls == [
        (
            "run",
            [
                "qdbus",
                "org.kde.KWin",
                "/Scripting",
                "org.kde.kwin.Scripting.loadScript",
                mock.ANY,
                "codex_live_cam_minimize_0",
            ],
        ),
        ("run", ["qdbus", "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start"]),
        ("sleep", 0.4),
        (
            "run",
            [
                "qdbus",
                "org.kde.KWin",
                "/Scripting",
                "org.kde.kwin.Scripting.unloadScript",
                "codex_live_cam_minimize_0",
            ],
        ),
        ("cleanup", mock.ANY),
    ]


def test_run_live_cam_reopen_specs_flow_uses_default_reopen_result_builder() -> None:
    calls: list[dict[str, object]] = []

    def fake_parallel_runner(
        specs: list[dict[str, object]],
        *,
        worker,
        label: str,
    ) -> list[dict[str, object]]:
        calls.append({"specs": specs, "label": label})
        return [worker(spec) for spec in specs]

    specs = [{"label": "akihabara", "port": 9996}]

    out = run_live_cam_reopen_specs_flow(
        specs,
        assign_live_camera=lambda spec: {
            "videoId": f"vid-{spec['port']}",
            "method": "direct-id",
            "final": {"href": f"https://www.youtube.com/tv#/watch?v=vid-{spec['port']}"},
        },
        parallel_runner=fake_parallel_runner,
    )

    assert out == [
        {
            "label": "akihabara",
            "port": 9996,
            "videoId": "vid-9996",
            "method": "direct-id",
        }
    ]
    assert calls == [{"specs": specs, "label": "live_cam_reopen"}]


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


def test_run_live_cam_existing_windowed_pids_query_logs_and_returns_none_when_windows_missing(
) -> None:
    logs: list[str] = []

    out = run_live_cam_existing_windowed_pids_query(
        instances=[{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101, 9994: 102}.get(port),
        row_provider=lambda pids: [{"id": "0x1", "pid": 101}],
        log=logs.append,
    )

    assert out is None
    assert logs == ["LIVE_CAM layout fast-path skipped (missing windows for ports: 9994)"]


def test_run_live_cam_existing_windowed_pids_query_returns_pid_map_when_all_windows_visible(
) -> None:
    logs: list[str] = []

    out = run_live_cam_existing_windowed_pids_query(
        instances=[{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101, 9994: 102}.get(port),
        row_provider=lambda pids: [{"id": "0x1", "pid": 101}, {"id": "0x2", "pid": 102}],
        log=logs.append,
    )

    assert out == {9993: 101, 9994: 102}


def test_run_live_cam_existing_windowed_pids_host_runtime_query_reads_runtime_methods() -> None:
    class FakeRuntime:
        def _live_camera_instance_specs(self) -> list[dict[str, int]]:
            return [{"port": 9993}, {"port": 9994}]

        def _pid_for_port(self, port: int) -> int | None:
            return {9993: 101, 9994: 102}.get(int(port))

        def _window_rows_by_pids(self, pids: list[int]) -> list[dict[str, int | str]]:
            assert pids == [101, 102]
            return [{"id": "0x1", "pid": 101}, {"id": "0x2", "pid": 102}]

        def log(self, _message: str) -> None:
            raise AssertionError("log unused when all windows are visible")

    out = run_live_cam_existing_windowed_pids_host_runtime_query(runtime=FakeRuntime())

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


def test_run_live_cam_hide_flow_uses_hide_response_builder() -> None:
    result = run_live_cam_hide_flow(
        [{"port": 9993}, {"port": 9994}],
        pid_lookup=lambda port: {9993: 101, 9994: 102}.get(port),
        state_fetcher=lambda _pids: {"windows": [], "urls": []},
        close_windows=lambda _pids: ["0x1", "0x2"],
        after_action=lambda: None,
    )

    assert result == (
        'live camera wall hide {"closed": 2, "windowIds": ["0x1", "0x2"], '
        '"ports": [9993, 9994], "windows": [], "urls": []}'
    )


def test_run_live_cam_hide_host_runtime_flow_reads_runtime_methods() -> None:
    events: list[object] = []

    class FakeRuntime:
        def _live_camera_instance_specs(self) -> list[dict[str, int]]:
            return [{"port": 9993}, {"port": 9994}]

        def _pid_for_port(self, port: int) -> int | None:
            return {9993: 101, 9994: 102}.get(int(port))

        def _collect_runtime_state(self, pids_by_port: dict[int, int]) -> dict[str, object]:
            events.append(("state", dict(pids_by_port)))
            return {"windows": [], "urls": []}

        def _close_windows_for_pids(self, pids: list[int]) -> list[str]:
            events.append(("close", list(pids)))
            return ["0x1", "0x2"]

        def _after_window_action_pause(self) -> None:
            events.append(("sleep", 0.2))

    result = run_live_cam_hide_host_runtime_flow(runtime=FakeRuntime())

    assert result == (
        'live camera wall hide {"closed": 2, "windowIds": ["0x1", "0x2"], '
        '"ports": [9993, 9994], "windows": [], "urls": []}'
    )
    assert events == [
        ("state", {9993: 101, 9994: 102}),
        ("close", [101, 102]),
        ("sleep", 0.2),
    ]


def test_run_live_cam_minimize_flow_uses_minimize_response_builder() -> None:
    result = run_live_cam_minimize_flow(
        [{"port": 9993}],
        pid_lookup=lambda port: {9993: 101}.get(port),
        state_fetcher=lambda _pids: {"windows": [], "urls": []},
        minimize_windows=lambda _pids: ["0x1"],
        after_action=lambda: None,
    )

    assert result == (
        'live camera wall minimize {"minimized": 1, "windowIds": ["0x1"], '
        '"ports": [9993], "windows": [], "urls": []}'
    )


def test_run_live_cam_minimize_host_runtime_flow_reads_runtime_methods() -> None:
    events: list[object] = []

    class FakeRuntime:
        def _live_camera_instance_specs(self) -> list[dict[str, int]]:
            return [{"port": 9993}]

        def _pid_for_port(self, port: int) -> int | None:
            return 101 if int(port) == 9993 else None

        def _collect_runtime_state(self, pids_by_port: dict[int, int]) -> dict[str, object]:
            events.append(("state", dict(pids_by_port)))
            return {"windows": [], "urls": []}

        def _minimize_windows_for_pids(self, pids: list[int]) -> list[str]:
            events.append(("minimize", list(pids)))
            return ["0x1"]

        def _after_window_action_pause(self) -> None:
            events.append(("sleep", 0.2))

    result = run_live_cam_minimize_host_runtime_flow(runtime=FakeRuntime())

    assert result == (
        'live camera wall minimize {"minimized": 1, "windowIds": ["0x1"], '
        '"ports": [9993], "windows": [], "urls": []}'
    )
    assert events == [
        ("state", {9993: 101}),
        ("minimize", [101]),
        ("sleep", 0.2),
    ]


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
        build_script=lambda skip_pids: events.append(("build", list(skip_pids))) or "SCRIPT",
        write_temp_script=lambda text, prefix: (
            events.append(("write", {"text": text, "prefix": prefix})) or "/tmp/demo.js"
        ),
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: events.append(("run", command)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
        cleanup=lambda path: events.append(("cleanup", path)),
        build_response=lambda skip_pids: events.append(("response", list(skip_pids))) or "done",
        plugin_name="plugin-name",
    )

    assert result == "done"
    assert events == [
        ("build", [101, 202]),
        (
            "write",
            {
                "text": "SCRIPT",
                "prefix": "codex-kwin-minimize-",
            },
        ),
        ("run", ["qdbus", "load", "/tmp/demo.js", "plugin-name"]),
        ("run", ["qdbus", "start"]),
        ("sleep", 0.3),
        ("run", ["qdbus", "unload", "plugin-name"]),
        ("cleanup", "/tmp/demo.js"),
        ("response", [101, 202]),
    ]


def test_run_minimize_other_windows_host_runtime_flow_reads_runtime_methods() -> None:
    class FakeRuntime:
        _live_camera_instance_specs = mock.Mock(return_value=[{"port": "9993"}])
        _live_camera_pid_for_port = mock.Mock(return_value=974790)
        _vacuumtube_x11_env = mock.Mock(return_value={"DISPLAY": ":1"})
        _write_temp_js_script = mock.Mock(return_value="/tmp/codex-kwin.js")

    with mock.patch(
        "arouter.live_cam_runtime.run_minimize_other_windows_flow",
        return_value="delegated",
    ) as helper:
        result = run_minimize_other_windows_host_runtime_flow(runtime=FakeRuntime())

    assert result == "delegated"
    helper.assert_called_once()
    kwargs = helper.call_args.kwargs
    assert kwargs["instances"] == [{"port": "9993"}]
    assert kwargs["pid_lookup"](9993) == 974790
    FakeRuntime._live_camera_instance_specs.assert_called_once_with()
    assert callable(kwargs["write_temp_script"])
    assert callable(kwargs["run_command"])
    with mock.patch("subprocess.run") as mock_run:
        kwargs["run_command"](["qdbus", "start"])
    FakeRuntime._vacuumtube_x11_env.assert_called_once_with()
    mock_run.assert_called_once()
    assert callable(kwargs["cleanup"])
    assert kwargs["plugin_name"].startswith("codex_minimize_others_")


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


def test_run_live_cam_layout_controller_flow_uses_layout_plan_helper() -> None:
    events: list[object] = []

    def _unused_full_targets(**_kwargs: object) -> list[dict[str, int]]:
        raise AssertionError("full targets unused")

    def _compact_targets(**kwargs: object) -> list[dict[str, int]]:
        pids_by_port = kwargs["pids_by_port"]
        assert isinstance(pids_by_port, dict)
        return [{"pid": int(pids_by_port[9993]), "x": 1, "y": 2, "w": 3, "h": 4}]

    def _runtime_state(pids_by_port: dict[int, int]) -> dict[str, object]:
        return {"windows": [{"pid": pids_by_port[9993]}], "urls": []}

    result = run_live_cam_layout_controller_flow(
        mode="compact",
        screen_w=4096,
        screen_h=2160,
        work_area=(0, 0, 4096, 2116),
        pids_by_port={9993: 101},
        fast_path=True,
        started=[],
        opened=[],
        open_errors=[],
        build_targets_full=_unused_full_targets,
        build_targets_compact=_compact_targets,
        kwin_apply_layout=lambda **kwargs: events.append(
            (
                "apply",
                kwargs["plugin_name"],
                kwargs["keep_above"],
                kwargs["no_border"],
                kwargs["targets"][0]["pid"],
            )
        ),
        raise_windows_for_pids=lambda pids: events.append(("raise", pids)),
        collect_runtime_state=_runtime_state,
    )

    assert events == [
        ("apply", "codex_live_cam_wall_compact", False, True, 101),
    ]
    assert result == (
        'live camera wall {"mode": "compact", "fastPath": true, '
        '"screen": {"w": 4096, "h": 2160}, '
        '"workArea": {"x": 0, "y": 0, "w": 4096, "h": 2116}, '
        '"started": [], "opened": [], "windows": [{"pid": 101}], "urls": []}'
    )


def test_run_live_cam_layout_runtime_flow_uses_bootstrap_and_controller_helpers() -> None:
    events: list[object] = []

    def _compact_targets(**kwargs: object) -> list[dict[str, int]]:
        pids_by_port = kwargs["pids_by_port"]
        assert isinstance(pids_by_port, dict)
        return [{"pid": int(pids_by_port[9993]), "x": 1, "y": 2, "w": 3, "h": 4}]

    result = run_live_cam_layout_runtime_flow(
        mode="compact",
        instances=[{"label": "shibuya", "port": 9993}],
        resolve_existing_windowed_pids=lambda: {9993: 101},
        find_stuck_specs=lambda: [],
        assign_live_camera=_unexpected_callback("assign_live_camera unused"),
        parallel_runner=_unexpected_callback("parallel_runner unused"),
        ensure_scripts_present=_unexpected_callback("ensure_scripts_present unused"),
        ensure_instances_started=_unexpected_callback("ensure_instances_started unused"),
        ensure_targets_opened=_unexpected_callback("ensure_targets_opened unused"),
        pid_lookup=lambda port: 101 if port == 9993 else None,
        detect_screen_size=lambda: (4096, 2160),
        detect_work_area=lambda: (0, 0, 4096, 2116),
        build_targets_full=_unexpected_callback("full target builder unused"),
        build_targets_compact=_compact_targets,
        kwin_apply_layout=lambda **kwargs: events.append(
            (
                "apply",
                kwargs["plugin_name"],
                kwargs["keep_above"],
                kwargs["no_border"],
                kwargs["targets"][0]["pid"],
            )
        ),
        raise_windows_for_pids=lambda pids: events.append(("raise", pids)),
        collect_runtime_state=lambda pids_by_port: {
            "windows": [{"pid": pids_by_port[9993]}],
            "urls": [],
        },
        log=lambda message: events.append(("log", message)),
    )

    assert events == [
        ("log", "LIVE_CAM compact fast-path: reusing existing windows and applying layout only"),
        ("apply", "codex_live_cam_wall_compact", False, True, 101),
    ]
    assert result == (
        'live camera wall {"mode": "compact", "fastPath": true, '
        '"screen": {"w": 4096, "h": 2160}, '
        '"workArea": {"x": 0, "y": 0, "w": 4096, "h": 2116}, '
        '"started": [], "opened": [], "windows": [{"pid": 101}], "urls": []}'
    )


def test_run_live_cam_layout_host_runtime_flow_reads_runtime_methods() -> None:
    events: list[object] = []

    class FakeRuntime:
        def _live_camera_instance_specs(self) -> list[dict[str, int | str]]:
            return [{"label": "shibuya", "port": 9993}]

        def log(self, message: str) -> None:
            events.append(("log", message))

        def _existing_windowed_pids_by_port(self) -> dict[int, int] | None:
            return {9993: 101}

        def _find_stuck_instances(self) -> list[dict[str, int]]:
            return []

        def _assign_live_camera(self, spec: dict[str, object]) -> dict[str, object]:
            raise AssertionError(f"assign_live_camera unused for {spec}")

        def _run_instances_parallel(self, specs, *, worker, label: str):
            raise AssertionError(f"parallel_runner unused for {specs}/{label}")

        def _ensure_scripts_present(self) -> None:
            raise AssertionError("ensure_scripts_present unused")

        def _ensure_instances_started(self) -> list[dict[str, object]]:
            raise AssertionError("ensure_instances_started unused")

        def _ensure_tokyo_targets_opened(self) -> list[dict[str, object]]:
            raise AssertionError("ensure_targets_opened unused")

        def _pid_for_port(self, port: int) -> int | None:
            return 101 if int(port) == 9993 else None

        def _detect_screen_size(self) -> tuple[int, int]:
            return (4096, 2160)

        def _detect_work_area(self) -> tuple[int, int, int, int] | None:
            return (0, 0, 4096, 2116)

        def _layout_targets_full(self, **kwargs: object) -> list[dict[str, int]]:
            raise AssertionError(f"full target builder unused: {kwargs}")

        def _layout_targets_compact(self, **kwargs: object) -> list[dict[str, int]]:
            pids_by_port = kwargs["pids_by_port"]
            assert isinstance(pids_by_port, dict)
            return [{"pid": int(pids_by_port[9993]), "x": 1, "y": 2, "w": 3, "h": 4}]

        def _kwin_apply_layout(self, **kwargs: object) -> None:
            events.append(
                (
                    "apply",
                    kwargs["plugin_name"],
                    kwargs["keep_above"],
                    kwargs["no_border"],
                    kwargs["targets"][0]["pid"],
                )
            )

        def _raise_windows_for_pids(self, pids: list[int]) -> None:
            events.append(("raise", pids))

        def _collect_runtime_state(self, pids_by_port: dict[int, int]) -> dict[str, object]:
            return {"windows": [{"pid": pids_by_port[9993]}], "urls": []}

    result = run_live_cam_layout_host_runtime_flow(mode="compact", runtime=FakeRuntime())

    assert events == [
        ("log", "LIVE_CAM compact fast-path: reusing existing windows and applying layout only"),
        ("apply", "codex_live_cam_wall_compact", False, True, 101),
    ]
    assert result == (
        'live camera wall {"mode": "compact", "fastPath": true, '
        '"screen": {"w": 4096, "h": 2160}, '
        '"workArea": {"x": 0, "y": 0, "w": 4096, "h": 2116}, '
        '"started": [], "opened": [], "windows": [{"pid": 101}], "urls": []}'
    )
