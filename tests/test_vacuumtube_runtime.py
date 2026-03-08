from __future__ import annotations

from typing import Any

import pytest

from arouter import (
    build_vacuumtube_context_base,
    ensure_vacuumtube_started_and_positioned,
    finalize_vacuumtube_context,
    is_recoverable_vacuumtube_error,
    merge_vacuumtube_cdp_state,
    merge_vacuumtube_window_snapshot,
)


def test_build_vacuumtube_context_base_returns_expected_defaults() -> None:
    context = build_vacuumtube_context_base(ts=123.4)

    assert context == {
        "ts": 123.4,
        "available": False,
        "windowFound": False,
        "fullscreenish": False,
        "quadrantish": False,
        "watchRoute": False,
        "homeRoute": False,
        "videoPlaying": False,
        "videoPaused": None,
    }


def test_merge_vacuumtube_window_snapshot_normalizes_geometry() -> None:
    merged = merge_vacuumtube_window_snapshot(
        build_vacuumtube_context_base(ts=1.0),
        window_id="0x123",
        geom={"x": "10", "y": 20.9, "w": "300", "h": 400},
        fullscreenish=True,
        quadrantish=True,
    )

    assert merged["windowFound"] is True
    assert merged["fullscreenish"] is True
    assert merged["quadrantish"] is True
    assert merged["geom"] == {"x": 10, "y": 20, "w": 300, "h": 400}


def test_merge_vacuumtube_cdp_state_sets_routes_and_video_flags() -> None:
    merged = merge_vacuumtube_cdp_state(
        build_vacuumtube_context_base(ts=1.0),
        {
            "hash": "#/watch?v=abc",
            "video": {"paused": False, "currentTime": 12.0},
            "accountSelectHint": False,
            "homeHint": False,
            "watchUiHint": True,
        },
    )

    assert merged["hash"] == "#/watch?v=abc"
    assert merged["watchRoute"] is True
    assert merged["homeRoute"] is False
    assert merged["videoPlaying"] is True
    assert merged["videoPaused"] is False
    assert merged["watchUiHint"] is True


def test_finalize_vacuumtube_context_marks_available_from_window_or_hash() -> None:
    merged = finalize_vacuumtube_context({"windowFound": False, "hash": "#/"})
    assert merged["available"] is True


def test_is_recoverable_vacuumtube_error_accepts_socket_timeout() -> None:
    assert is_recoverable_vacuumtube_error(TimeoutError("timeout"))


def test_is_recoverable_vacuumtube_error_accepts_custom_timeout_type() -> None:
    class DummyTimeoutError(Exception):
        pass

    assert is_recoverable_vacuumtube_error(
        DummyTimeoutError("boom"),
        timeout_exception_type=DummyTimeoutError,
    )


def test_is_recoverable_vacuumtube_error_accepts_known_message() -> None:
    assert is_recoverable_vacuumtube_error(RuntimeError("CDP not ready yet"))


def test_is_recoverable_vacuumtube_error_rejects_unknown_error() -> None:
    assert not is_recoverable_vacuumtube_error(RuntimeError("unexpected failure"))


def test_ensure_vacuumtube_started_and_positioned_restarts_when_window_missing() -> None:
    events: list[str] = []
    presentations = iter(
        [
            {"fullscreen": False, "window_id": "0x123", "stage": "before"},
            {"fullscreen": False, "window_id": "0x123", "stage": "after"},
        ]
    )

    def ensure_top_right_position() -> dict[str, Any]:
        events.append("ensure_top_right")
        return {"ok": True, "window_id": "0x123"}

    def wait_window(timeout: float) -> str:
        events.append(f"wait_window:{timeout}")
        if "restart" not in events:
            raise RuntimeError("missing")
        return "0x123"

    result = ensure_vacuumtube_started_and_positioned(
        ensure_running=lambda: events.append("ensure_running"),
        wait_window=wait_window,
        restart_tmux_session=lambda: events.append("restart"),
        wait_cdp_ready=lambda timeout: events.append(f"wait_cdp_ready:{timeout}") or True,
        select_account_if_needed=lambda: events.append("select_account"),
        capture_window_presentation=lambda win_id: (
            events.append(f"capture:{win_id}") or next(presentations)
        ),
        ensure_top_right_position=ensure_top_right_position,
        log=events.append,
        base_url="http://127.0.0.1:9992",
    )

    assert result == {"fullscreen": False, "window_id": "0x123", "stage": "after"}
    assert events[:5] == [
        "ensure_running",
        "wait_window:20.0",
        "VacuumTube window missing after startup; restarting session: missing",
        "restart",
        "wait_cdp_ready:35.0",
    ]
    assert "ensure_top_right" in events
    assert any(event.startswith("VacuumTube window position check: ") for event in events)


def test_ensure_vacuumtube_started_and_positioned_raises_when_cdp_never_returns() -> None:
    with pytest.raises(RuntimeError, match="VacuumTube CDP not ready at http://127.0.0.1:9992"):
        ensure_vacuumtube_started_and_positioned(
            ensure_running=lambda: None,
            wait_window=lambda _timeout: (_ for _ in ()).throw(RuntimeError("missing")),
            restart_tmux_session=lambda: None,
            wait_cdp_ready=lambda _timeout: False,
            select_account_if_needed=lambda: None,
            capture_window_presentation=lambda _win_id: {"fullscreen": False},
            ensure_top_right_position=lambda: {"ok": True},
            log=lambda _msg: None,
            base_url="http://127.0.0.1:9992",
        )


def test_ensure_vacuumtube_started_and_positioned_preserves_fullscreen_window() -> None:
    events: list[str] = []

    def unexpected_top_right() -> dict[str, Any]:
        raise AssertionError("unexpected top-right")

    result = ensure_vacuumtube_started_and_positioned(
        ensure_running=lambda: events.append("ensure_running"),
        wait_window=lambda timeout: events.append(f"wait_window:{timeout}") or "0x123",
        restart_tmux_session=lambda: events.append("restart"),
        wait_cdp_ready=lambda timeout: events.append(f"wait_cdp_ready:{timeout}") or True,
        select_account_if_needed=lambda: events.append("select_account"),
        capture_window_presentation=lambda win_id: (
            events.append(f"capture:{win_id}") or {"fullscreen": True, "window_id": win_id}
        ),
        ensure_top_right_position=unexpected_top_right,
        log=events.append,
        base_url="http://127.0.0.1:9992",
    )

    assert result == {"fullscreen": True, "window_id": "0x123"}
    assert any(
        event.startswith("VacuumTube window position preserved (fullscreen): ")
        for event in events
    )
