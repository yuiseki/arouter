from __future__ import annotations

from arouter import (
    build_vacuumtube_context_base,
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
