from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict


class KWinScriptCommandPlan(TypedDict):
    run: list[list[str]]
    unload: list[str]


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
