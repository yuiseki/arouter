from __future__ import annotations


def build_wmctrl_list_command(*, geometry: bool = False, with_pid: bool = False) -> list[str]:
    if geometry and with_pid:
        return ["wmctrl", "-lpG"]
    if geometry:
        return ["wmctrl", "-lG"]
    if with_pid:
        return ["wmctrl", "-lp"]
    return ["wmctrl", "-l"]
