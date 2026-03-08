from __future__ import annotations

from arouter import run_kwin_temp_script


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
