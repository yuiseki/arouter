from __future__ import annotations

from arouter import build_listen_pid_command, parse_listen_pid_output, resolve_listen_pid


def test_build_listen_pid_command_returns_lsof_listen_query() -> None:
    assert build_listen_pid_command(9992) == [
        "lsof",
        "-nP",
        "-iTCP:9992",
        "-sTCP:LISTEN",
        "-t",
    ]


def test_parse_listen_pid_output_returns_first_valid_pid() -> None:
    assert parse_listen_pid_output("oops\n12345\n67890\n") == 12345


def test_parse_listen_pid_output_returns_none_when_no_valid_pid_exists() -> None:
    assert parse_listen_pid_output("oops\n\n") is None


def test_resolve_listen_pid_uses_shared_command_and_parser() -> None:
    commands: list[list[str]] = []

    out = resolve_listen_pid(
        9992,
        run_command=lambda command: commands.append(command) or "54321\n",
    )

    assert out == 54321
    assert commands == [["lsof", "-nP", "-iTCP:9992", "-sTCP:LISTEN", "-t"]]
