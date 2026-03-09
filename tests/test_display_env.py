from __future__ import annotations

from arouter import (
    build_x11_env,
    resolve_x11_display,
    resolve_x11_display_host_runtime,
)


def test_build_x11_env_sets_display_and_optional_xauthority() -> None:
    env = build_x11_env(display=":0", xauthority="/tmp/xauth")

    assert env["DISPLAY"] == ":0"
    assert env["XAUTHORITY"] == "/tmp/xauth"


def test_resolve_x11_display_uses_cached_display_when_probe_passes() -> None:
    out = resolve_x11_display(
        cached_display=":1",
        configured_display=":1",
        probe_display=lambda display: display == ":1",
        logger=lambda _msg: None,
        label="VACUUMTUBE",
    )

    assert out == ":1"


def test_resolve_x11_display_falls_back_and_logs() -> None:
    seen: list[str] = []
    logs: list[str] = []

    out = resolve_x11_display(
        cached_display=None,
        configured_display=":1",
        probe_display=lambda display: seen.append(display) or display == ":0",
        logger=logs.append,
        label="LIVE_CAM",
    )

    assert out == ":0"
    assert seen[:2] == [":1", ":0"]
    assert logs == ["LIVE_CAM display fallback: configured=:1 -> using :0"]


def test_resolve_x11_display_raises_probe_failed_when_probe_errors() -> None:
    def probe(_display: str) -> bool:
        raise RuntimeError("boom")

    try:
        resolve_x11_display(
            cached_display=None,
            configured_display=":1",
            probe_display=probe,
            logger=lambda _msg: None,
            label="VACUUMTUBE",
        )
    except RuntimeError as exc:
        assert "vacuumtube X11 display probe failed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_resolve_x11_display_raises_not_available_without_probe_error() -> None:
    try:
        resolve_x11_display(
            cached_display=None,
            configured_display=":1",
            probe_display=lambda _display: False,
            logger=lambda _msg: None,
            label="LIVE_CAM",
        )
    except RuntimeError as exc:
        assert "live_cam X11 display not available" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_resolve_x11_display_host_runtime_updates_runtime_cache() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self._resolved_display = None
            self.display = ":1"
            self.events: list[str] = []

        def _probe_display(self, display: str) -> bool:
            self.events.append(f"probe:{display}")
            return display == ":0"

        def log(self, message: str) -> None:
            self.events.append(message)

    runtime = FakeRuntime()

    out = resolve_x11_display_host_runtime(runtime=runtime, label="LIVE_CAM")

    assert out == ":0"
    assert runtime._resolved_display == ":0"
    assert runtime.events == [
        "probe::1",
        "probe::0",
        "LIVE_CAM display fallback: configured=:1 -> using :0",
    ]
