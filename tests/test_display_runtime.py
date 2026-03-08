from __future__ import annotations

from arouter import probe_x11_display


def test_probe_x11_display_returns_true_on_zero_exit() -> None:
    commands: list[list[str]] = []

    ok = probe_x11_display(
        run_command=lambda command: commands.append(command) or 0,
    )

    assert ok is True
    assert commands == [["xdpyinfo"]]


def test_probe_x11_display_returns_false_on_nonzero_exit() -> None:
    ok = probe_x11_display(
        run_command=lambda _command: 1,
    )

    assert ok is False
