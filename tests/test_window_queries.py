from __future__ import annotations

from arouter import build_wmctrl_list_command


def test_build_wmctrl_list_command_defaults_to_title_listing() -> None:
    assert build_wmctrl_list_command() == ["wmctrl", "-l"]


def test_build_wmctrl_list_command_supports_geometry_and_pid_modes() -> None:
    assert build_wmctrl_list_command(geometry=True) == ["wmctrl", "-lG"]
    assert build_wmctrl_list_command(with_pid=True) == ["wmctrl", "-lp"]
    assert build_wmctrl_list_command(geometry=True, with_pid=True) == ["wmctrl", "-lpG"]
