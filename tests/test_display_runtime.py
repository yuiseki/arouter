from __future__ import annotations

import pytest

from arouter import probe_x11_display, probe_x11_display_host_runtime


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


def test_probe_x11_display_host_runtime_uses_runtime_env() -> None:
    runtime = type(
        "_Runtime",
        (),
        {"_env_for_display": lambda self, display: {"DISPLAY": display, "XAUTHORITY": "/tmp/auth"}},
    )()

    with pytest.MonkeyPatch.context() as mp:
        calls: list[tuple[list[str], dict[str, object]]] = []

        class _CP:
            returncode = 0

        def _run(command: list[str], **kwargs: object) -> _CP:
            calls.append((command, kwargs))
            return _CP()

        mp.setattr("subprocess.run", _run)

        ok = probe_x11_display_host_runtime(runtime=runtime, display=":0")

    assert ok is True
    assert calls == [
        (
            ["xdpyinfo"],
            {
                "check": False,
                "text": True,
                "capture_output": True,
                "env": {"DISPLAY": ":0", "XAUTHORITY": "/tmp/auth"},
            },
        )
    ]
