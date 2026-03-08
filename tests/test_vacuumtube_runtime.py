from __future__ import annotations

import json
from typing import Any

import pytest

from arouter import (
    build_vacuumtube_context_base,
    ensure_vacuumtube_started_and_positioned,
    finalize_vacuumtube_context,
    is_recoverable_vacuumtube_error,
    merge_vacuumtube_cdp_state,
    merge_vacuumtube_window_snapshot,
    run_vacuumtube_fullscreen,
    run_vacuumtube_go_home,
    run_vacuumtube_minimize,
    run_vacuumtube_play_bgm,
    run_vacuumtube_play_news,
    run_vacuumtube_quadrant,
    run_vacuumtube_resume_playback,
    run_vacuumtube_stop_music,
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


def test_run_vacuumtube_resume_playback_returns_noop_when_window_missing() -> None:
    result = run_vacuumtube_resume_playback(
        find_window_id=lambda: None,
        snapshot_state=lambda: {"hash": "#/watch"},
        is_watch_state=lambda state: bool(state),
        confirm_already_playing=lambda: None,
        try_resume_current_video=lambda: None,
        confirm_dom_resume=lambda: None,
        send_space_key=lambda: None,
        confirm_space_resume=lambda: None,
        ensure_top_right_position=lambda: {"ok": True},
        log=lambda _msg: None,
    )

    assert result == "VacuumTube window not found (no-op)"


def test_run_vacuumtube_resume_playback_skips_when_not_on_watch_route() -> None:
    events: list[str] = []

    result = run_vacuumtube_resume_playback(
        find_window_id=lambda: "0x123",
        snapshot_state=lambda: {"hash": "#/"},
        is_watch_state=lambda _state: False,
        confirm_already_playing=lambda: (_ for _ in ()).throw(AssertionError("unexpected")),
        try_resume_current_video=lambda: (_ for _ in ()).throw(AssertionError("unexpected")),
        confirm_dom_resume=lambda: (_ for _ in ()).throw(AssertionError("unexpected")),
        send_space_key=lambda: (_ for _ in ()).throw(AssertionError("unexpected")),
        confirm_space_resume=lambda: (_ for _ in ()).throw(AssertionError("unexpected")),
        ensure_top_right_position=lambda: (_ for _ in ()).throw(AssertionError("unexpected")),
        log=events.append,
    )

    assert result == "not on watch route (no-op)"
    assert events == ["resume_playback skipped: not on watch route"]


def test_run_vacuumtube_resume_playback_uses_space_toggle_after_dom_resume_fails() -> None:
    events: list[str] = []

    result = run_vacuumtube_resume_playback(
        find_window_id=lambda: "0x123",
        snapshot_state=lambda: {"hash": "#/watch?v=abc"},
        is_watch_state=lambda _state: True,
        confirm_already_playing=lambda: (_ for _ in ()).throw(RuntimeError("still paused")),
        try_resume_current_video=lambda: events.append("try_resume"),
        confirm_dom_resume=lambda: (_ for _ in ()).throw(RuntimeError("dom failed")),
        send_space_key=lambda: events.append("space"),
        confirm_space_resume=lambda: events.append("confirm_space"),
        ensure_top_right_position=lambda: (
            events.append("ensure_top_right") or {"ok": True, "window_id": "0x123"}
        ),
        log=events.append,
    )

    assert result == "resumed playback via Space toggle (0x123)"
    assert events[:4] == ["try_resume", "space", "confirm_space", "ensure_top_right"]
    assert any(event.startswith("RESUME space-toggle window position: ") for event in events)


def test_run_vacuumtube_go_home_restores_presentation() -> None:
    events: list[str] = []

    result = run_vacuumtube_go_home(
        presentation_before={"fullscreen": True, "window_id": "0x123"},
        hide_overlay_if_needed=lambda: events.append("hide_overlay"),
        ensure_home=lambda: {"hash": "#/", "tilesCount": 8},
        restore_window_presentation=lambda presentation, *, label: events.append(
            f"restore:{presentation['window_id']}:{label}"
        ),
        log=events.append,
    )

    assert result == 'youtube home verified {"hash": "#/", "tiles": 8}'
    assert events == ["hide_overlay", "restore:0x123:YOUTUBE_HOME"]


def test_run_vacuumtube_go_home_logs_restore_failure_and_returns_snapshot() -> None:
    events: list[str] = []

    result = run_vacuumtube_go_home(
        presentation_before={"fullscreen": False, "window_id": "0x123"},
        hide_overlay_if_needed=lambda: events.append("hide_overlay"),
        ensure_home=lambda: {"hash": "#/", "tilesCount": 3},
        restore_window_presentation=lambda _presentation, *, label: (_ for _ in ()).throw(
            RuntimeError(f"{label}: failed")
        ),
        log=events.append,
    )

    assert result == 'youtube home verified {"hash": "#/", "tiles": 3}'
    assert events == [
        "hide_overlay",
        "YOUTUBE_HOME presentation restore skipped: YOUTUBE_HOME: failed",
    ]


def test_run_vacuumtube_play_bgm_opens_home_flow_when_not_on_watch_route() -> None:
    events: list[str] = []

    def confirm_watch_playback(
        *,
        timeout_sec: float,
        allow_soft_confirm_when_unpaused: bool,
    ) -> None:
        events.append(f"confirm:{timeout_sec}:{allow_soft_confirm_when_unpaused}")

    result = run_vacuumtube_play_bgm(
        get_state=lambda: {"accountSelectHint": False, "hash": "#/"},
        send_return_key=lambda: events.append("return"),
        send_space_key=lambda: events.append("space"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        try_resume_current_video=lambda: events.append("resume"),
        confirm_watch_playback=confirm_watch_playback,
        open_from_home=lambda: events.append("open_home") or "opened watch route #/watch?v=bgm",
        ensure_top_right_position=lambda: {"ok": True},
        log=events.append,
    )

    assert result == "opened watch route #/watch?v=bgm"
    assert events == ["open_home"]


def test_run_vacuumtube_play_bgm_watch_route_uses_resume_path() -> None:
    events: list[str] = []

    def confirm_watch_playback(
        *,
        timeout_sec: float,
        allow_soft_confirm_when_unpaused: bool,
    ) -> None:
        events.append(f"confirm:{timeout_sec}:{allow_soft_confirm_when_unpaused}")

    def ensure_top_right_position() -> dict[str, Any]:
        events.append("ensure_top_right")
        return {"ok": True, "window_id": "0x123"}

    result = run_vacuumtube_play_bgm(
        get_state=lambda: {"accountSelectHint": False, "hash": "#/watch?v=abc"},
        send_return_key=lambda: events.append("return"),
        send_space_key=lambda: events.append("space"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        try_resume_current_video=lambda: events.append("resume"),
        confirm_watch_playback=confirm_watch_playback,
        open_from_home=lambda: (_ for _ in ()).throw(AssertionError("unexpected home open")),
        ensure_top_right_position=ensure_top_right_position,
        log=events.append,
    )

    assert result == "watch page detected; confirmed playback"
    assert events[:3] == ["resume", "confirm:4.0:True", "ensure_top_right"]
    assert any(event.startswith("BGM watch-resume window position: ") for event in events)


def test_run_vacuumtube_play_bgm_nudges_account_selection_before_home_open() -> None:
    events: list[str] = []
    states = iter(
        [
            {"accountSelectHint": True, "hash": "#/"},
            {"accountSelectHint": False, "hash": "#/"},
        ]
    )

    def confirm_watch_playback(
        *,
        timeout_sec: float,
        allow_soft_confirm_when_unpaused: bool,
    ) -> None:
        events.append(f"confirm:{timeout_sec}:{allow_soft_confirm_when_unpaused}")

    result = run_vacuumtube_play_bgm(
        get_state=lambda: next(states),
        send_return_key=lambda: events.append("return"),
        send_space_key=lambda: events.append("space"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        try_resume_current_video=lambda: events.append("resume"),
        confirm_watch_playback=confirm_watch_playback,
        open_from_home=lambda: events.append("open_home") or "opened watch route #/watch?v=bgm",
        ensure_top_right_position=lambda: {"ok": True},
        log=events.append,
    )

    assert result == "opened watch route #/watch?v=bgm"
    assert events == ["return", "sleep:0.6", "open_home"]


def test_run_vacuumtube_fullscreen_returns_before_after_geometry() -> None:
    events: list[str] = []
    geometries = iter(
        [
            {"x": 100, "y": 100, "w": 1280, "h": 720},
            {"x": 0, "y": 0, "w": 1920, "h": 1080},
        ]
    )

    result = run_vacuumtube_fullscreen(
        ensure_started_and_positioned=lambda: events.append("ensure_started"),
        wait_window=lambda: events.append("wait_window") or "0x123",
        activate_window=lambda win_id: events.append(f"activate:{win_id}"),
        get_window_geometry=lambda _win_id: next(geometries),
        set_fullscreen=lambda win_id, *, enabled: events.append(
            f"fullscreen:{win_id}:{enabled}"
        ),
        wait_fullscreen=lambda win_id, *, enabled, timeout_sec: (
            events.append(f"wait_fullscreen:{win_id}:{enabled}:{timeout_sec}") or True
        ),
    )

    assert json.loads(result.removeprefix("youtube fullscreen ")) == {
        "fullscreen": True,
        "before": {"x": 100, "y": 100, "w": 1280, "h": 720},
        "after": {"x": 0, "y": 0, "w": 1920, "h": 1080},
    }
    assert events == [
        "ensure_started",
        "wait_window",
        "activate:0x123",
        "fullscreen:0x123:True",
        "wait_fullscreen:0x123:True:3.0",
    ]


def test_run_vacuumtube_quadrant_wraps_position_result() -> None:
    events: list[str] = []

    result = run_vacuumtube_quadrant(
        ensure_started_and_positioned=lambda: events.append("ensure_started"),
        ensure_top_right_position=lambda: events.append("ensure_top_right")
        or {"ok": True, "window_id": "0x123"},
    )

    assert result == 'youtube quadrant {"ok": true, "window_id": "0x123"}'
    assert events == ["ensure_started", "ensure_top_right"]


def test_run_vacuumtube_stop_music_returns_noop_when_window_missing() -> None:
    result = run_vacuumtube_stop_music(
        find_window_id=lambda: None,
        snapshot_state=lambda: {"hash": "#/watch?v=abc"},
        is_watch_state=lambda state: bool(state),
        send_space_key=lambda: None,
        time_now=lambda: 100.0,
        sleep=lambda _seconds: None,
        ensure_top_right_position=lambda: {"ok": True},
        log=lambda _msg: None,
    )

    assert result == "VacuumTube window not found (no-op)"


def test_run_vacuumtube_stop_music_skips_when_not_on_watch_route() -> None:
    events: list[str] = []

    result = run_vacuumtube_stop_music(
        find_window_id=lambda: "0x123",
        snapshot_state=lambda: {"hash": "#/"},
        is_watch_state=lambda _state: False,
        send_space_key=lambda: events.append("space"),
        time_now=lambda: 100.0,
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        ensure_top_right_position=lambda: {"ok": True},
        log=events.append,
    )

    assert result == "not on watch route (no-op)"
    assert events == ["stop_music skipped: not on watch route"]


def test_run_vacuumtube_stop_music_confirms_pause_and_logs_position() -> None:
    events: list[str] = []
    states = iter(
        [
            {"hash": "#/watch?v=abc", "video": {"paused": False}},
            {"hash": "#/watch?v=abc", "video": {"paused": True}},
        ]
    )

    result = run_vacuumtube_stop_music(
        find_window_id=lambda: "0x123",
        snapshot_state=lambda: next(states),
        is_watch_state=lambda state: str(state.get("hash", "")).startswith("#/watch"),
        send_space_key=lambda: events.append("space"),
        time_now=iter([100.0, 100.1]).__next__,
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        ensure_top_right_position=lambda: (
            events.append("ensure_top_right") or {"ok": True, "window_id": "0x123"}
        ),
        log=events.append,
    )

    assert result == "sent Space toggle to VacuumTube (0x123); pause confirmed"
    assert events[:2] == ["space", "ensure_top_right"]
    assert any(event.startswith("STOP post-action window position: ") for event in events)


def test_run_vacuumtube_stop_music_returns_last_snapshot_when_pause_not_confirmed() -> None:
    events: list[str] = []
    last_state = {"hash": "#/watch?v=abc", "video": {"paused": False}}

    result = run_vacuumtube_stop_music(
        find_window_id=lambda: "0x123",
        snapshot_state=lambda: last_state,
        is_watch_state=lambda state: str(state.get("hash", "")).startswith("#/watch"),
        send_space_key=lambda: events.append("space"),
        time_now=iter([100.0, 100.1, 104.2]).__next__,
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        ensure_top_right_position=lambda: {"ok": True},
        log=events.append,
    )

    assert result == (
        'sent Space toggle to VacuumTube (0x123); pause not confirmed ({"hash": "#/watch?v=abc", '
        '"video": {"paused": false}})'
    )
    assert events == ["space", "sleep:0.25"]


def test_run_vacuumtube_play_news_opens_with_expected_label() -> None:
    events: list[str] = []

    def open_from_home(label: str) -> str:
        events.append(f"open:{label}")
        return "opened watch route #/watch?v=abc"

    result = run_vacuumtube_play_news(
        slot="generic",
        get_state=lambda: {"accountSelectHint": False},
        send_return_key=lambda: events.append("return"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        open_from_home=open_from_home,
    )

    assert result == "opened watch route #/watch?v=abc"
    assert events == ["open:NEWS"]


def test_run_vacuumtube_play_news_nudges_account_selection() -> None:
    events: list[str] = []
    states = iter(
        [
            {"accountSelectHint": True},
            {"accountSelectHint": False},
        ]
    )

    def open_from_home(label: str) -> str:
        events.append(f"open:{label}")
        return "opened watch route #/watch?v=morning"

    result = run_vacuumtube_play_news(
        slot="morning",
        get_state=lambda: next(states),
        send_return_key=lambda: events.append("return"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        open_from_home=open_from_home,
    )

    assert result == "opened watch route #/watch?v=morning"
    assert events == ["return", "sleep:0.6", "open:NEWS-MORNING"]


def test_run_vacuumtube_minimize_is_noop_when_window_is_missing() -> None:
    result = run_vacuumtube_minimize(
        find_window_id=lambda: None,
        build_minimize_command=lambda _: pytest.fail("builder should not be called"),
        run_command=lambda _: pytest.fail("runner should not be called"),
    )

    assert result == "VacuumTube window not found (no-op)"


def test_run_vacuumtube_minimize_runs_built_command() -> None:
    commands: list[list[str]] = []

    result = run_vacuumtube_minimize(
        find_window_id=lambda: "0x123",
        build_minimize_command=lambda win_id: ["xdotool", "windowminimize", win_id],
        run_command=commands.append,
    )

    assert result == "youtube minimize: ok (win_id=0x123)"
    assert commands == [["xdotool", "windowminimize", "0x123"]]
