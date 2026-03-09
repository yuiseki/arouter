from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from typing import Any, TypedDict, cast

from .kwin_scripts import (
    build_kwin_script_command_plan,
    build_live_cam_layout_script,
    build_window_frame_geometry_script,
)


class KWinScriptCommandPlan(TypedDict):
    run: list[list[str]]
    unload: list[str]


def _write_temp_js_script(script_text: str, prefix: str) -> str:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".js",
        prefix=prefix,
        delete=False,
    ) as temp_file:
        temp_file.write(script_text)
        return temp_file.name


def run_kwin_temp_script(
    *,
    script_text: str,
    plugin_name: str,
    file_prefix: str,
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    sleep_sec: float,
    cleanup: Callable[[str], None],
) -> None:
    script_path = write_temp_script(script_text, file_prefix)
    command_plan = command_plan_builder(script_path, plugin_name)
    try:
        for command in command_plan["run"]:
            run_command(command)
        sleep(float(sleep_sec))
    finally:
        try:
            run_command(command_plan["unload"])
        except Exception:
            pass
        try:
            cleanup(script_path)
        except Exception:
            pass


def run_live_cam_layout_script(
    targets: list[dict[str, object]],
    *,
    plugin_name: str,
    keep_above: bool,
    no_border: bool,
    build_script: Callable[..., str],
    run_script: Callable[..., None],
) -> None:
    run_script(
        script_text=build_script(
            targets,
            keep_above=keep_above,
            no_border=no_border,
        ),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-livecam-",
        sleep_sec=0.8,
    )


def run_live_cam_layout_runtime(
    targets: list[dict[str, object]],
    *,
    plugin_name: str,
    keep_above: bool,
    no_border: bool,
    build_script: Callable[..., str],
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    cleanup: Callable[[str], None],
) -> None:
    run_kwin_temp_script(
        script_text=build_script(
            targets,
            keep_above=keep_above,
            no_border=no_border,
        ),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-livecam-",
        write_temp_script=write_temp_script,
        command_plan_builder=command_plan_builder,
        run_command=run_command,
        sleep=sleep,
        sleep_sec=0.8,
        cleanup=cleanup,
    )


def run_live_cam_layout_host_runtime(
    targets: list[dict[str, object]],
    *,
    runtime: Any,
    plugin_name: str,
    keep_above: bool,
    no_border: bool,
) -> None:
    def _run_command(command: list[str]) -> None:
        runtime._run(
            command,
            env=runtime._x11_env(),
            timeout=8.0,
        )

    run_live_cam_layout_runtime(
        targets,
        plugin_name=plugin_name,
        keep_above=keep_above,
        no_border=no_border,
        build_script=build_live_cam_layout_script,
        write_temp_script=_write_temp_js_script,
        command_plan_builder=cast(
            Callable[[str, str], KWinScriptCommandPlan],
            build_kwin_script_command_plan,
        ),
        run_command=_run_command,
        sleep=time.sleep,
        cleanup=os.unlink,
    )


def run_window_frame_geometry_script(
    *,
    pid: int,
    geom: dict[str, int],
    no_border: bool,
    plugin_name: str,
    build_script: Callable[..., str],
    run_script: Callable[..., None],
) -> None:
    run_script(
        script_text=build_script(
            pid=pid,
            geom=geom,
            no_border=no_border,
        ),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-vacuumtube-main-",
        sleep_sec=0.5,
    )


def run_window_frame_geometry_runtime(
    *,
    pid: int,
    geom: dict[str, int],
    no_border: bool,
    plugin_name: str,
    build_script: Callable[..., str],
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    cleanup: Callable[[str], None],
) -> None:
    run_kwin_temp_script(
        script_text=build_script(
            pid=pid,
            geom=geom,
            no_border=no_border,
        ),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-vacuumtube-main-",
        write_temp_script=write_temp_script,
        command_plan_builder=command_plan_builder,
        run_command=run_command,
        sleep=sleep,
        sleep_sec=0.5,
        cleanup=cleanup,
    )


def run_window_frame_geometry_host_runtime(
    *,
    runtime: Any,
    pid: int,
    geom: dict[str, int],
    no_border: bool,
    plugin_name: str,
) -> None:
    env = runtime._x11_env()

    def _run_command(command: list[str]) -> None:
        subprocess.run(
            command,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )

    run_window_frame_geometry_runtime(
        pid=pid,
        geom=geom,
        no_border=no_border,
        plugin_name=plugin_name,
        build_script=build_window_frame_geometry_script,
        write_temp_script=_write_temp_js_script,
        command_plan_builder=cast(
            Callable[[str, str], KWinScriptCommandPlan],
            build_kwin_script_command_plan,
        ),
        run_command=_run_command,
        sleep=time.sleep,
        cleanup=os.unlink,
    )


def run_live_cam_minimize_script(
    *,
    pids: list[int],
    plugin_name: str,
    build_script: Callable[[list[int]], str],
    run_script: Callable[..., None],
) -> None:
    run_script(
        script_text=build_script(pids),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-livecam-minimize-",
        sleep_sec=0.4,
    )


def run_live_cam_minimize_runtime(
    *,
    pids: list[int],
    plugin_name: str,
    build_script: Callable[[list[int]], str],
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    cleanup: Callable[[str], None],
) -> None:
    run_kwin_temp_script(
        script_text=build_script(pids),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-livecam-minimize-",
        write_temp_script=write_temp_script,
        command_plan_builder=command_plan_builder,
        run_command=run_command,
        sleep=sleep,
        sleep_sec=0.4,
        cleanup=cleanup,
    )


def run_minimize_other_windows_script(
    *,
    skip_pids: list[int],
    plugin_name: str,
    build_script: Callable[[list[int]], str],
    run_script: Callable[..., None],
) -> None:
    run_script(
        script_text=build_script(skip_pids),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-minimize-",
        sleep_sec=0.3,
    )


def run_minimize_other_windows_runtime(
    *,
    skip_pids: list[int],
    plugin_name: str,
    build_script: Callable[[list[int]], str],
    write_temp_script: Callable[[str, str], str],
    command_plan_builder: Callable[[str, str], KWinScriptCommandPlan],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    cleanup: Callable[[str], None],
) -> None:
    run_kwin_temp_script(
        script_text=build_script(skip_pids),
        plugin_name=plugin_name,
        file_prefix="codex-kwin-minimize-",
        write_temp_script=write_temp_script,
        command_plan_builder=command_plan_builder,
        run_command=run_command,
        sleep=sleep,
        sleep_sec=0.3,
        cleanup=cleanup,
    )
