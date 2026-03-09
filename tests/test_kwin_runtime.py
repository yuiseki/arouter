from __future__ import annotations

from unittest import mock

from arouter import (
    run_kwin_temp_script,
    run_live_cam_layout_host_runtime,
    run_live_cam_layout_runtime,
    run_live_cam_layout_script,
    run_live_cam_minimize_runtime,
    run_live_cam_minimize_script,
    run_minimize_other_windows_runtime,
    run_minimize_other_windows_script,
    run_window_frame_geometry_host_runtime,
    run_window_frame_geometry_runtime,
    run_window_frame_geometry_script,
)


def test_run_kwin_temp_script_runs_commands_then_unloads_and_cleans_up() -> None:
    events: list[str] = []

    def write_temp_script(text: str, prefix: str) -> str:
        events.append(f"write:{prefix}:{text}")
        return "/tmp/demo.js"

    run_kwin_temp_script(
        script_text="SCRIPT",
        plugin_name="plugin-name",
        file_prefix="codex-test-",
        write_temp_script=write_temp_script,
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: events.append("run:" + " ".join(command)),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        sleep_sec=0.8,
        cleanup=lambda path: events.append(f"cleanup:{path}"),
    )

    assert events == [
        "write:codex-test-:SCRIPT",
        "run:qdbus load /tmp/demo.js plugin-name",
        "run:qdbus start",
        "sleep:0.8",
        "run:qdbus unload plugin-name",
        "cleanup:/tmp/demo.js",
    ]


def test_run_kwin_temp_script_still_unloads_and_cleans_up_after_run_failure() -> None:
    events: list[str] = []

    def run_command(command: list[str]) -> None:
        rendered = " ".join(command)
        events.append("run:" + rendered)
        if rendered == "qdbus start":
            raise RuntimeError("boom")

    try:
        run_kwin_temp_script(
            script_text="SCRIPT",
            plugin_name="plugin-name",
            file_prefix="codex-test-",
            write_temp_script=lambda text, prefix: "/tmp/demo.js",
            command_plan_builder=lambda path, plugin: {
                "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
                "unload": ["qdbus", "unload", plugin],
            },
            run_command=run_command,
            sleep=lambda seconds: events.append(f"sleep:{seconds}"),
            sleep_sec=0.8,
            cleanup=lambda path: events.append(f"cleanup:{path}"),
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")

    assert events == [
        "run:qdbus load /tmp/demo.js plugin-name",
        "run:qdbus start",
        "run:qdbus unload plugin-name",
        "cleanup:/tmp/demo.js",
    ]


def test_run_live_cam_layout_script_builds_script_and_uses_kwin_runner() -> None:
    events: list[object] = []

    run_live_cam_layout_script(
        [{"pid": 123, "x": 1, "y": 2, "w": 3, "h": 4}],
        plugin_name="plugin-name",
        keep_above=False,
        no_border=True,
        build_script=lambda targets, *, keep_above, no_border: (
            events.append(("build", targets, keep_above, no_border)) or "SCRIPT"
        ),
        run_script=lambda **kwargs: events.append(kwargs),
    )

    assert events == [
        ("build", [{"pid": 123, "x": 1, "y": 2, "w": 3, "h": 4}], False, True),
        {
            "script_text": "SCRIPT",
            "plugin_name": "plugin-name",
            "file_prefix": "codex-kwin-livecam-",
            "sleep_sec": 0.8,
        },
    ]


def test_run_live_cam_layout_runtime_builds_script_and_runs_kwin_temp_script() -> None:
    events: list[object] = []

    run_live_cam_layout_runtime(
        [{"pid": 123, "x": 1, "y": 2, "w": 3, "h": 4}],
        plugin_name="plugin-name",
        keep_above=False,
        no_border=True,
        build_script=lambda targets, *, keep_above, no_border: (
            events.append(("build", targets, keep_above, no_border)) or "SCRIPT"
        ),
        write_temp_script=lambda text, prefix: (
            events.append(("write", text, prefix)) or "/tmp/demo.js"
        ),
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: events.append(("run", command)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
        cleanup=lambda path: events.append(("cleanup", path)),
    )

    assert events == [
        ("build", [{"pid": 123, "x": 1, "y": 2, "w": 3, "h": 4}], False, True),
        ("write", "SCRIPT", "codex-kwin-livecam-"),
        ("run", ["qdbus", "load", "/tmp/demo.js", "plugin-name"]),
        ("run", ["qdbus", "start"]),
        ("sleep", 0.8),
        ("run", ["qdbus", "unload", "plugin-name"]),
        ("cleanup", "/tmp/demo.js"),
    ]


def test_run_live_cam_layout_host_runtime_uses_runtime_runner() -> None:
    events: list[object] = []

    class Runtime:
        @staticmethod
        def _x11_env() -> dict[str, str]:
            return {"DISPLAY": ":1"}

        @staticmethod
        def _run(command: list[str], **kwargs: object) -> None:
            events.append((command, kwargs))

    runtime = Runtime()

    run_live_cam_layout_host_runtime(
        [{"pid": 123, "x": 1, "y": 2, "w": 3, "h": 4}],
        runtime=runtime,
        plugin_name="plugin-name",
        keep_above=False,
        no_border=True,
        build_script=lambda targets, *, keep_above, no_border: "SCRIPT",
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
    )

    assert len(events) == 3
    assert events[0][0][0] == "qdbus"
    assert events[0][1]["env"] == {"DISPLAY": ":1"}
    assert events[1][0] == ["qdbus", "start"]
    assert events[2][0] == ["qdbus", "unload", "plugin-name"]


def test_run_window_frame_geometry_script_builds_script_and_uses_kwin_runner() -> None:
    events: list[object] = []

    run_window_frame_geometry_script(
        pid=123,
        geom={"x": 1, "y": 2, "w": 3, "h": 4},
        no_border=False,
        plugin_name="plugin-name",
        build_script=lambda *, pid, geom, no_border: (
            events.append(("build", pid, geom, no_border)) or "SCRIPT"
        ),
        run_script=lambda **kwargs: events.append(kwargs),
    )

    assert events == [
        ("build", 123, {"x": 1, "y": 2, "w": 3, "h": 4}, False),
        {
            "script_text": "SCRIPT",
            "plugin_name": "plugin-name",
            "file_prefix": "codex-kwin-vacuumtube-main-",
            "sleep_sec": 0.5,
        },
    ]


def test_run_window_frame_geometry_runtime_builds_script_and_runs_kwin_temp_script() -> None:
    events: list[object] = []

    run_window_frame_geometry_runtime(
        pid=123,
        geom={"x": 1, "y": 2, "w": 3, "h": 4},
        no_border=False,
        plugin_name="plugin-name",
        build_script=lambda *, pid, geom, no_border: (
            events.append(("build", pid, geom, no_border)) or "SCRIPT"
        ),
        write_temp_script=lambda text, prefix: (
            events.append(("write", text, prefix)) or "/tmp/demo.js"
        ),
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: events.append(("run", command)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
        cleanup=lambda path: events.append(("cleanup", path)),
    )

    assert events == [
        ("build", 123, {"x": 1, "y": 2, "w": 3, "h": 4}, False),
        ("write", "SCRIPT", "codex-kwin-vacuumtube-main-"),
        ("run", ["qdbus", "load", "/tmp/demo.js", "plugin-name"]),
        ("run", ["qdbus", "start"]),
        ("sleep", 0.5),
        ("run", ["qdbus", "unload", "plugin-name"]),
        ("cleanup", "/tmp/demo.js"),
    ]


def test_run_window_frame_geometry_host_runtime_uses_runtime_env() -> None:
    runtime = type(
        "Runtime",
        (),
        {"_x11_env": staticmethod(lambda: {"DISPLAY": ":1"})},
    )()
    events: list[object] = []

    with mock.patch("arouter.kwin_runtime.subprocess.run") as run_command:
        run_command.side_effect = lambda command, **kwargs: events.append((command, kwargs))
        run_window_frame_geometry_host_runtime(
            runtime=runtime,
            pid=123,
            geom={"x": 1, "y": 2, "w": 3, "h": 4},
            no_border=False,
            plugin_name="plugin-name",
            build_script=lambda *, pid, geom, no_border: "SCRIPT",
            command_plan_builder=lambda path, plugin: {
                "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
                "unload": ["qdbus", "unload", plugin],
            },
        )

    assert len(events) == 3
    assert events[0][1]["env"] == {"DISPLAY": ":1"}
    assert events[1][0] == ["qdbus", "start"]
    assert events[2][0] == ["qdbus", "unload", "plugin-name"]


def test_run_live_cam_minimize_script_builds_script_and_uses_kwin_runner() -> None:
    events: list[object] = []

    run_live_cam_minimize_script(
        pids=[123, 456],
        plugin_name="plugin-name",
        build_script=lambda pids: (events.append(("build", pids)) or "SCRIPT"),
        run_script=lambda **kwargs: events.append(kwargs),
    )

    assert events == [
        ("build", [123, 456]),
        {
            "script_text": "SCRIPT",
            "plugin_name": "plugin-name",
            "file_prefix": "codex-kwin-livecam-minimize-",
            "sleep_sec": 0.4,
        },
    ]


def test_run_live_cam_minimize_runtime_builds_script_and_runs_kwin_temp_script() -> None:
    events: list[object] = []

    run_live_cam_minimize_runtime(
        pids=[123, 456],
        plugin_name="plugin-name",
        build_script=lambda pids: (events.append(("build", pids)) or "SCRIPT"),
        write_temp_script=lambda text, prefix: (
            events.append(("write", text, prefix)) or "/tmp/demo.js"
        ),
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: events.append(("run", command)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
        cleanup=lambda path: events.append(("cleanup", path)),
    )

    assert events == [
        ("build", [123, 456]),
        ("write", "SCRIPT", "codex-kwin-livecam-minimize-"),
        ("run", ["qdbus", "load", "/tmp/demo.js", "plugin-name"]),
        ("run", ["qdbus", "start"]),
        ("sleep", 0.4),
        ("run", ["qdbus", "unload", "plugin-name"]),
        ("cleanup", "/tmp/demo.js"),
    ]


def test_run_minimize_other_windows_script_builds_script_and_uses_kwin_runner() -> None:
    events: list[object] = []

    run_minimize_other_windows_script(
        skip_pids=[101, 202],
        plugin_name="plugin-name",
        build_script=lambda skip_pids: (events.append(("build", skip_pids)) or "SCRIPT"),
        run_script=lambda **kwargs: events.append(kwargs),
    )

    assert events == [
        ("build", [101, 202]),
        {
            "script_text": "SCRIPT",
            "plugin_name": "plugin-name",
            "file_prefix": "codex-kwin-minimize-",
            "sleep_sec": 0.3,
        },
    ]


def test_run_minimize_other_windows_runtime_builds_script_and_runs_kwin_temp_script() -> None:
    events: list[object] = []

    run_minimize_other_windows_runtime(
        skip_pids=[101, 202],
        plugin_name="plugin-name",
        build_script=lambda skip_pids: (events.append(("build", skip_pids)) or "SCRIPT"),
        write_temp_script=lambda text, prefix: (
            events.append(("write", text, prefix)) or "/tmp/demo.js"
        ),
        command_plan_builder=lambda path, plugin: {
            "run": [["qdbus", "load", path, plugin], ["qdbus", "start"]],
            "unload": ["qdbus", "unload", plugin],
        },
        run_command=lambda command: events.append(("run", command)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
        cleanup=lambda path: events.append(("cleanup", path)),
    )

    assert events == [
        ("build", [101, 202]),
        ("write", "SCRIPT", "codex-kwin-minimize-"),
        ("run", ["qdbus", "load", "/tmp/demo.js", "plugin-name"]),
        ("run", ["qdbus", "start"]),
        ("sleep", 0.3),
        ("run", ["qdbus", "unload", "plugin-name"]),
        ("cleanup", "/tmp/demo.js"),
    ]
