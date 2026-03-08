from __future__ import annotations

from arouter import (
    build_tmux_has_session_command,
    build_tmux_kill_session_command,
    build_vacuumtube_tmux_start_command,
)


def test_build_tmux_has_session_command() -> None:
    assert build_tmux_has_session_command("vacuumtube-main") == [
        "tmux",
        "has-session",
        "-t",
        "vacuumtube-main",
    ]


def test_build_tmux_kill_session_command() -> None:
    assert build_tmux_kill_session_command("vacuumtube-main") == [
        "tmux",
        "kill-session",
        "-t",
        "vacuumtube-main",
    ]


def test_build_vacuumtube_tmux_start_command_includes_display_and_optional_xauthority() -> None:
    cmd = build_vacuumtube_tmux_start_command(
        session_name="vacuumtube-main",
        display=":0",
        xauthority="/tmp/xauth",
        start_script="/opt/VacuumTube/start.sh",
    )

    assert cmd[:5] == ["tmux", "new-session", "-d", "-s", "vacuumtube-main"]
    assert "VACUUMTUBE_DISPLAY=:0" in cmd[5]
    assert "XAUTHORITY=/tmp/xauth" in cmd[5]
    assert "exec /opt/VacuumTube/start.sh" in cmd[5]
