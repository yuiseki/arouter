from __future__ import annotations

import json
from typing import Any
from unittest import mock

import pytest

from arouter import (
    build_vacuumtube_context_base,
    ensure_vacuumtube_runtime_ready,
    ensure_vacuumtube_started_and_positioned,
    finalize_vacuumtube_context,
    is_recoverable_vacuumtube_error,
    merge_vacuumtube_cdp_state,
    merge_vacuumtube_window_snapshot,
    recover_vacuumtube_unresponsive_state,
    restart_vacuumtube_tmux_session,
    run_vacuumtube_action_with_recovery,
    run_vacuumtube_click_tile_center,
    run_vacuumtube_confirm_watch_playback,
    run_vacuumtube_confirm_watch_playback_host_runtime,
    run_vacuumtube_context_query,
    run_vacuumtube_context_runtime_flow,
    run_vacuumtube_context_runtime_query,
    run_vacuumtube_dom_click_tile,
    run_vacuumtube_ensure_home,
    run_vacuumtube_ensure_home_host_runtime,
    run_vacuumtube_enumerate_tiles,
    run_vacuumtube_fullscreen,
    run_vacuumtube_fullscreen_host_runtime,
    run_vacuumtube_go_home,
    run_vacuumtube_go_home_host_runtime,
    run_vacuumtube_go_home_runtime,
    run_vacuumtube_good_night_pause,
    run_vacuumtube_good_night_pause_cdp_runtime_flow,
    run_vacuumtube_good_night_pause_flow,
    run_vacuumtube_good_night_pause_host_runtime,
    run_vacuumtube_good_night_pause_runtime,
    run_vacuumtube_good_night_pause_runtime_flow,
    run_vacuumtube_hard_reload_home,
    run_vacuumtube_hide_overlay,
    run_vacuumtube_minimize,
    run_vacuumtube_minimize_host_runtime,
    run_vacuumtube_open_from_home,
    run_vacuumtube_open_from_home_host_runtime,
    run_vacuumtube_open_from_home_runtime,
    run_vacuumtube_play_bgm,
    run_vacuumtube_play_bgm_host_runtime,
    run_vacuumtube_play_bgm_runtime,
    run_vacuumtube_play_news,
    run_vacuumtube_play_news_host_runtime,
    run_vacuumtube_play_news_runtime,
    run_vacuumtube_quadrant,
    run_vacuumtube_quadrant_host_runtime,
    run_vacuumtube_resume_playback,
    run_vacuumtube_resume_playback_host_runtime,
    run_vacuumtube_resume_playback_runtime,
    run_vacuumtube_route_to_home,
    run_vacuumtube_select_account_if_needed,
    run_vacuumtube_snapshot_state,
    run_vacuumtube_snapshot_state_host_runtime,
    run_vacuumtube_state_host_runtime_query,
    run_vacuumtube_state_query,
    run_vacuumtube_stop_music,
    run_vacuumtube_stop_music_host_runtime,
    run_vacuumtube_stop_music_runtime,
    run_vacuumtube_try_resume_current_video,
    run_vacuumtube_wait_watch_route,
    run_vacuumtube_wait_watch_route_host_runtime,
    start_vacuumtube_tmux_session,
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


def test_run_vacuumtube_state_query_returns_dict_payload() -> None:
    out = run_vacuumtube_state_query(
        evaluate=lambda expr: {
            "hash": "#/watch?v=abc",
            "bodyText": "body",
            "expr_seen": "overlayVisible" in expr,
        }
    )

    assert out == {
        "hash": "#/watch?v=abc",
        "bodyText": "body",
        "expr_seen": True,
    }


def test_run_vacuumtube_state_query_returns_empty_dict_for_non_dict_payload() -> None:
    out = run_vacuumtube_state_query(evaluate=lambda _expr: ["not", "dict"])

    assert out == {}


def test_run_vacuumtube_state_host_runtime_query_reads_cdp_evaluate() -> None:
    cdp = mock.Mock()
    cdp.evaluate.return_value = {"hash": "#/watch?v=abc"}

    out = run_vacuumtube_state_host_runtime_query(cdp=cdp)

    assert out == {"hash": "#/watch?v=abc"}
    cdp.evaluate.assert_called_once()


def test_run_vacuumtube_snapshot_state_combines_state_and_tile_samples() -> None:
    out = run_vacuumtube_snapshot_state(
        query_state=lambda: {
            "hash": "#/watch?v=abc",
            "title": "VacuumTube",
            "accountSelectHint": False,
            "homeHint": False,
            "watchUiHint": True,
            "overlayVisible": True,
            "video": {"paused": False},
        },
        enumerate_tiles=lambda: [
            {"title": "Tile A"},
            {"text": "Tile B"},
            {"title": "Tile C"},
            {"title": "Tile D"},
        ],
    )

    assert out == {
        "hash": "#/watch?v=abc",
        "title": "VacuumTube",
        "accountSelectHint": False,
        "homeHint": False,
        "watchUiHint": True,
        "overlayVisible": True,
        "video": {"paused": False},
        "tilesCount": 4,
        "tilesSample": ["Tile A", "Tile B", "Tile C"],
    }


def test_run_vacuumtube_snapshot_state_tolerates_tile_enumeration_errors() -> None:
    out = run_vacuumtube_snapshot_state(
        query_state=lambda: {"hash": "#/"},
        enumerate_tiles=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert out == {
        "hash": "#/",
        "title": None,
        "accountSelectHint": None,
        "homeHint": None,
        "watchUiHint": None,
        "overlayVisible": None,
        "video": None,
        "tilesCount": 0,
        "tilesSample": [],
    }


def test_run_vacuumtube_snapshot_state_host_runtime_reads_runtime_methods() -> None:
    runtime = mock.Mock()
    runtime._enumerate_tiles.return_value = [{"title": "Tile A"}]
    cdp = mock.Mock()
    cdp.evaluate.return_value = {"hash": "#/watch?v=abc", "title": "VacuumTube"}

    out = run_vacuumtube_snapshot_state_host_runtime(runtime=runtime, cdp=cdp)

    assert out == {
        "hash": "#/watch?v=abc",
        "title": "VacuumTube",
        "accountSelectHint": None,
        "homeHint": None,
        "watchUiHint": None,
        "overlayVisible": None,
        "video": None,
        "tilesCount": 1,
        "tilesSample": ["Tile A"],
    }
    runtime._enumerate_tiles.assert_called_once_with(cdp)
    cdp.evaluate.assert_called_once()


def test_run_vacuumtube_context_query_combines_window_and_cdp_state() -> None:
    out = run_vacuumtube_context_query(
        ts=1.0,
        cdp_port=9992,
        find_window_row_by_cdp_port=lambda port: {
            "id": "0x123",
            "x": "10",
            "y": 20,
            "w": "300",
            "h": 400,
        }
        if port == 9992
        else None,
        find_window_id=lambda: "0x999",
        get_window_geometry=lambda wid: {"x": 0, "y": 0, "w": 1, "h": 1},
        current_window_is_fullscreenish=lambda wid: False,
        read_fullscreen_state=lambda wid: "",
        quadrant_mode_enabled=lambda: True,
        cdp_ready=lambda: True,
        query_cdp_state=lambda: {
            "hash": "#/watch?v=abc",
            "video": {"paused": False},
            "accountSelectHint": False,
            "homeHint": False,
            "watchUiHint": True,
        },
    )

    assert out == {
        "ts": 1.0,
        "available": True,
        "windowFound": True,
        "fullscreenish": False,
        "quadrantish": True,
        "watchRoute": True,
        "homeRoute": False,
        "videoPlaying": True,
        "videoPaused": False,
        "geom": {"x": 10, "y": 20, "w": 300, "h": 400},
        "hash": "#/watch?v=abc",
        "accountSelectHint": False,
        "homeHint": False,
        "watchUiHint": True,
    }


def test_run_vacuumtube_context_query_falls_back_to_window_lookup_and_xprop_state() -> None:
    out = run_vacuumtube_context_query(
        ts=2.0,
        cdp_port=None,
        find_window_row_by_cdp_port=lambda _port: None,
        find_window_id=lambda: "0xabc",
        get_window_geometry=lambda wid: {"x": 1, "y": 2, "w": 3, "h": 4},
        current_window_is_fullscreenish=lambda wid: False,
        read_fullscreen_state=lambda wid: "_NET_WM_STATE_FULLSCREEN",
        quadrant_mode_enabled=lambda: False,
        cdp_ready=lambda: False,
        query_cdp_state=lambda: {"hash": "#/watch?v=ignored"},
    )

    assert out == {
        "ts": 2.0,
        "available": True,
        "windowFound": True,
        "fullscreenish": True,
        "quadrantish": False,
        "watchRoute": False,
        "homeRoute": False,
        "videoPlaying": False,
        "videoPaused": None,
        "geom": {"x": 1, "y": 2, "w": 3, "h": 4},
    }


def test_run_vacuumtube_context_runtime_query_wires_fullscreen_and_cdp_helpers() -> None:
    events: list[object] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    out = run_vacuumtube_context_runtime_query(
        ts=3.0,
        cdp_port=9992,
        find_window_row_by_cdp_port=lambda port: {
            "id": "0x123",
            "x": "10",
            "y": 20,
            "w": "300",
            "h": 400,
        }
        if port == 9992
        else None,
        find_window_id=lambda: "0x999",
        get_window_geometry=lambda wid: {"x": 0, "y": 0, "w": 1, "h": 1},
        current_window_is_fullscreenish=lambda wid: False,
        run_xprop_query=lambda command: (
            events.append(("xprop", command)) or "_NET_WM_STATE_FULLSCREEN"
        ),
        quadrant_mode_enabled=lambda: True,
        cdp_ready=lambda: True,
        open_cdp=lambda: FakeContext(),
        read_state=lambda cdp: events.append(("state", cdp)) or {"hash": "#/watch?v=abc"},
    )

    assert out == {
        "ts": 3.0,
        "available": True,
        "windowFound": True,
        "fullscreenish": True,
        "quadrantish": True,
        "watchRoute": True,
        "homeRoute": False,
        "videoPlaying": False,
        "videoPaused": None,
        "geom": {"x": 10, "y": 20, "w": 300, "h": 400},
        "hash": "#/watch?v=abc",
        "accountSelectHint": False,
        "homeHint": False,
        "watchUiHint": False,
    }
    assert events == [
        ("xprop", ["xprop", "-id", "0x123", "_NET_WM_STATE"]),
        "enter",
        ("state", "cdp"),
        "exit",
    ]


def test_run_vacuumtube_context_runtime_flow_reads_runtime_methods() -> None:
    events: list[object] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    runtime = mock.Mock()
    runtime.cdp_port = 9992
    runtime.find_window_id.return_value = "0x999"
    runtime.get_window_geometry.return_value = {"x": 0, "y": 0, "w": 1, "h": 1}
    runtime._current_window_is_fullscreenish.return_value = False
    runtime._x11_env.return_value = {"DISPLAY": ":1"}
    runtime.cdp_ready.return_value = True
    runtime._cdp.return_value = FakeContext()
    runtime._state.return_value = {"hash": "#/watch?v=abc"}

    def _run_command(command: list[str], **kwargs: Any) -> mock.Mock:
        events.append(("cmd", command, kwargs))
        return mock.Mock(stdout="_NET_WM_STATE_FULLSCREEN")

    out = run_vacuumtube_context_runtime_flow(
        ts=3.0,
        runtime=runtime,
        find_window_row_by_cdp_port=lambda port: {
            "id": "0x123",
            "x": "10",
            "y": 20,
            "w": "300",
            "h": 400,
        }
        if port == 9992
        else None,
        quadrant_mode_enabled=lambda: True,
        run_command=_run_command,
    )

    assert events == [
        (
            "cmd",
            ["xprop", "-id", "0x123", "_NET_WM_STATE"],
            {"check": False, "env": {"DISPLAY": ":1"}},
        ),
        "enter",
        "exit",
    ]
    assert out == {
        "ts": 3.0,
        "available": True,
        "windowFound": True,
        "fullscreenish": True,
        "quadrantish": True,
        "watchRoute": True,
        "homeRoute": False,
        "videoPlaying": False,
        "videoPaused": None,
        "geom": {"x": 10, "y": 20, "w": 300, "h": 400},
        "hash": "#/watch?v=abc",
        "accountSelectHint": False,
        "homeHint": False,
        "watchUiHint": False,
    }


def test_run_vacuumtube_action_with_recovery_retries_once_for_recoverable_error() -> None:
    logs: list[str] = []
    action = mock.Mock(side_effect=[RuntimeError("Connection timed out"), "recovered"])
    recover = mock.Mock()

    out = run_vacuumtube_action_with_recovery(
        action=action,
        label="music_play",
        is_recoverable_error=lambda err: "timed out" in str(err),
        recover=recover,
        log=logs.append,
    )

    assert out == "recovered"
    assert action.call_count == 2
    recover.assert_called_once_with()
    assert logs == [
        (
            "music_play recoverable VacuumTube error: Connection timed out; "
            "restarting and retrying once"
        )
    ]


def test_run_vacuumtube_action_with_recovery_reraises_nonrecoverable_error() -> None:
    action = mock.Mock(side_effect=RuntimeError("boom"))
    recover = mock.Mock()

    with pytest.raises(RuntimeError, match="boom"):
        run_vacuumtube_action_with_recovery(
            action=action,
            label="music_play",
            is_recoverable_error=lambda _err: False,
            recover=recover,
            log=lambda _msg: None,
        )

    recover.assert_not_called()


def test_run_vacuumtube_hide_overlay_invokes_evaluate_with_overlay_selector() -> None:
    seen: list[str] = []

    run_vacuumtube_hide_overlay(evaluate=lambda expr: seen.append(expr))

    assert len(seen) == 1
    assert "vt-settings-overlay-root" in seen[0]


def test_run_vacuumtube_ensure_home_recovers_from_account_select_after_hard_reload() -> None:
    logs: list[str] = []
    now_values = iter([100.0, 100.2, 100.4, 100.6, 100.8, 101.7, 101.9, 102.1])
    snapshots = iter(
        [
            {
                "hash": "#/watch?v=abc",
                "tilesCount": 0,
                "homeHint": False,
                "watchUiHint": True,
                "accountSelectHint": False,
            },
            {
                "hash": "#/",
                "tilesCount": 0,
                "homeHint": False,
                "watchUiHint": True,
                "accountSelectHint": False,
            },
            {
                "hash": "#/",
                "tilesCount": 7,
                "homeHint": False,
                "watchUiHint": False,
                "accountSelectHint": True,
            },
            {
                "hash": "#/",
                "tilesCount": 7,
                "homeHint": False,
                "watchUiHint": False,
                "accountSelectHint": False,
            },
        ]
    )
    route_calls: list[str] = []
    reload_calls: list[str] = []
    select_calls: list[str] = []
    sleep_calls: list[float] = []

    out = run_vacuumtube_ensure_home(
        snapshot_state=lambda: next(snapshots),
        is_home_browse_state=lambda snap: (
            snap.get("hash") == "#/"
            and not snap.get("watchUiHint")
            and not snap.get("accountSelectHint")
            and int(snap.get("tilesCount") or 0) > 0
        ),
        route_to_home=lambda: route_calls.append("route"),
        hard_reload_home=lambda: reload_calls.append("reload"),
        select_account_if_needed=lambda: select_calls.append("select"),
        needs_hard_reload_home=lambda snap: (
            bool(snap.get("watchUiHint")) and not snap.get("homeHint")
        ),
        log=logs.append,
        now=lambda: next(now_values),
        sleep=lambda seconds: sleep_calls.append(seconds),
        timeout_sec=5.0,
    )

    assert out["hash"] == "#/"
    assert out["tilesCount"] == 7
    assert route_calls == ["route"]
    assert reload_calls == ["reload"]
    assert select_calls == ["select"]
    assert sleep_calls == [0.25]
    assert logs[0].startswith("state before ensure_home: ")
    assert any("forcing hard reload to home" in line for line in logs)
    assert any("trying default account focus" in line for line in logs)
    assert any(line.startswith("state after ensure_home: ") for line in logs)


def test_run_vacuumtube_ensure_home_host_runtime_reads_runtime_methods() -> None:
    runtime = mock.Mock()
    runtime._is_home_browse_state.return_value = True
    runtime._needs_hard_reload_home.return_value = False
    runtime._snapshot_state.return_value = {"hash": "#/"}
    runtime.log = mock.Mock()
    cdp = object()

    out = run_vacuumtube_ensure_home_host_runtime(
        runtime=runtime,
        cdp=cdp,
        timeout_sec=5.0,
    )

    assert out == {"hash": "#/"}
    runtime._snapshot_state.assert_called_once_with(cdp)
    runtime._is_home_browse_state.assert_called_once_with({"hash": "#/"})
    runtime.log.assert_called()


def test_run_vacuumtube_try_resume_current_video_returns_ok_flag() -> None:
    out = run_vacuumtube_try_resume_current_video(
        evaluate_async=lambda expr: {
            "ok": "window.yt" in expr,
            "paused": False,
        }
    )

    assert out is True


def test_run_vacuumtube_try_resume_current_video_swallows_errors() -> None:
    out = run_vacuumtube_try_resume_current_video(
        evaluate_async=lambda _expr: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    assert out is False


def test_run_vacuumtube_wait_watch_route_returns_true_when_hash_matches() -> None:
    states = iter(
        [
            {"hash": "#/"},
            {"hash": "#/watch?v=abc"},
        ]
    )
    sleeps: list[float] = []
    now_values = iter([100.0, 100.1, 100.2, 100.3])

    out = run_vacuumtube_wait_watch_route(
        get_state=lambda: next(states),
        now=lambda: next(now_values),
        sleep=lambda seconds: sleeps.append(seconds),
        timeout_sec=5.0,
    )

    assert out is True
    assert sleeps == [0.2]


def test_run_vacuumtube_wait_watch_route_tolerates_state_errors_until_timeout() -> None:
    sleeps: list[float] = []
    now_values = iter([100.0, 100.1, 100.3, 100.6])

    out = run_vacuumtube_wait_watch_route(
        get_state=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        now=lambda: next(now_values),
        sleep=lambda seconds: sleeps.append(seconds),
        timeout_sec=0.5,
    )

    assert out is False
    assert sleeps == [0.2, 0.2]


def test_run_vacuumtube_wait_watch_route_host_runtime_reads_runtime_methods() -> None:
    runtime = mock.Mock()
    runtime._state.return_value = {"hash": "#/watch?v=abc"}

    out = run_vacuumtube_wait_watch_route_host_runtime(
        runtime=runtime,
        cdp=object(),
        timeout_sec=5.0,
    )

    assert out is True
    runtime._state.assert_called_once()


def test_run_vacuumtube_route_to_home_invokes_hash_assignment() -> None:
    seen: list[str] = []

    run_vacuumtube_route_to_home(evaluate=seen.append)

    assert seen == ["location.hash = '#/'"]


def test_run_vacuumtube_hard_reload_home_invokes_full_home_url() -> None:
    seen: list[str] = []

    run_vacuumtube_hard_reload_home(evaluate=seen.append)

    assert seen == ["location.href = 'https://www.youtube.com/tv#/'"]


def test_run_vacuumtube_click_tile_center_passes_float_coordinates() -> None:
    seen: list[tuple[float, float]] = []

    run_vacuumtube_click_tile_center(
        tile={"cx": "123.4", "cy": 456},
        mouse_click=lambda x, y: seen.append((x, y)),
    )

    assert seen == [(123.4, 456.0)]


def test_run_vacuumtube_enumerate_tiles_returns_dict_rows() -> None:
    out = run_vacuumtube_enumerate_tiles(
        evaluate=lambda expr: [
            {"title": "Tile 1", "visible": True, "expr_seen": "ytlr-tile-renderer" in expr},
            "skip-me",
            {"title": "Tile 2", "visible": False},
        ]
    )

    assert out == [
        {"title": "Tile 1", "visible": True, "expr_seen": True},
        {"title": "Tile 2", "visible": False},
    ]


def test_run_vacuumtube_enumerate_tiles_returns_empty_list_for_non_list_payload() -> None:
    out = run_vacuumtube_enumerate_tiles(evaluate=lambda _expr: {"title": "Tile 1"})

    assert out == []


def test_run_vacuumtube_dom_click_tile_passes_title_and_text_to_expression() -> None:
    seen: list[str] = []

    out = run_vacuumtube_dom_click_tile(
        title="Best Tile",
        text="Best Tile Text",
        evaluate=lambda expr: seen.append(expr) or {"ok": True},
    )

    assert out == {"ok": True}
    assert len(seen) == 1
    assert '"Best Tile"' in seen[0]
    assert '"Best Tile Text"' in seen[0]


def test_run_vacuumtube_good_night_pause_returns_payload_dict() -> None:
    out = run_vacuumtube_good_night_pause(
        evaluate=lambda expr: {
            "ok": "window.yt" in expr,
            "afterPaused": True,
        }
    )

    assert out == {"ok": True, "afterPaused": True}


def test_run_vacuumtube_good_night_pause_wraps_non_dict_payload() -> None:
    out = run_vacuumtube_good_night_pause(evaluate=lambda _expr: "oops")

    assert out == {"ok": False, "result": "oops"}


def test_run_vacuumtube_good_night_pause_runtime_adds_state_hash() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    out = run_vacuumtube_good_night_pause_runtime(
        open_cdp=lambda: FakeContext(),
        snapshot_state=lambda cdp: {"hash": "#/watch?v=abc", "seen": cdp},
        run_pause=lambda cdp: {"ok": True, "afterPaused": True, "cdp": cdp},
    )

    assert out == (
        'good_night pause '
        '{"ok": true, "afterPaused": true, "cdp": "cdp", "stateHash": "#/watch?v=abc"}'
    )


def test_run_vacuumtube_good_night_pause_flow_returns_noop_when_window_missing() -> None:
    out = run_vacuumtube_good_night_pause_flow(
        find_window_id=lambda: None,
        pause_runtime=lambda: "unexpected",
    )

    assert out == "good_night pause no VacuumTube window (no-op)"


def test_run_vacuumtube_good_night_pause_flow_returns_runtime_result() -> None:
    out = run_vacuumtube_good_night_pause_flow(
        find_window_id=lambda: "0x123",
        pause_runtime=lambda: 'good_night pause {"ok": true}',
    )

    assert out == 'good_night pause {"ok": true}'


def test_run_vacuumtube_good_night_pause_flow_formats_runtime_error() -> None:
    out = run_vacuumtube_good_night_pause_flow(
        find_window_id=lambda: "0x123",
        pause_runtime=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert out == "good_night pause error: boom"


def test_run_vacuumtube_good_night_pause_runtime_flow_wraps_window_check_and_cdp_runtime() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    out = run_vacuumtube_good_night_pause_runtime_flow(
        find_window_id=lambda: "0x123",
        open_cdp=lambda: FakeContext(),
        snapshot_state=lambda cdp: events.append(f"snapshot:{cdp}") or {"hash": "#/watch?v=abc"},
        run_pause=lambda cdp: events.append(f"pause:{cdp}") or {"ok": True},
    )

    assert out == 'good_night pause {"ok": true, "stateHash": "#/watch?v=abc"}'
    assert events == [
        "enter",
        "snapshot:cdp",
        "pause:cdp",
        "exit",
    ]


def test_run_vacuumtube_good_night_pause_cdp_runtime_flow_uses_default_pause_query() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    class FakeCdp:
        def evaluate(self, expr: str) -> dict[str, object]:
            events.append(f"evaluate:{'video' in expr}")
            return {"ok": True, "afterPaused": True, "hash": "#/watch?v=abc"}

    out = run_vacuumtube_good_night_pause_cdp_runtime_flow(
        find_window_id=lambda: "0x123",
        open_cdp=lambda: FakeContext(),
        snapshot_state=lambda cdp: (
            events.append(f"snapshot:{cdp}") or {"hash": "#/watch?v=abc"}
        ),
        cdp_getter=lambda _cdp: FakeCdp(),
    )

    assert out == (
        'good_night pause '
        '{"ok": true, "afterPaused": true, "hash": "#/watch?v=abc", '
        '"stateHash": "#/watch?v=abc"}'
    )
    assert events == [
        "enter",
        "snapshot:cdp",
        "evaluate:True",
        "exit",
    ]


def test_run_vacuumtube_good_night_pause_host_runtime_uses_runtime_methods() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeCdp:
        def __init__(self, events: list[str]) -> None:
            self._events = events

        def evaluate(self, expr: str) -> dict[str, object]:
            self._events.append(f"evaluate:{'video' in expr}")
            return {"ok": True, "afterPaused": True, "hash": "#/watch?v=abc"}

    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def find_window_id(self) -> str | None:
            self.events.append("find_window")
            return "0x123"

        def _cdp(self) -> FakeContext:
            return FakeContext()

        def _snapshot_state(self, cdp: str) -> dict[str, object]:
            self.events.append(f"snapshot:{cdp}")
            return {"hash": "#/watch?v=abc"}

    runtime = FakeRuntime()

    out = run_vacuumtube_good_night_pause_host_runtime(
        runtime=runtime,
        cdp_getter=lambda _cdp: FakeCdp(runtime.events),
    )

    assert out == (
        'good_night pause '
        '{"ok": true, "afterPaused": true, "hash": "#/watch?v=abc", '
        '"stateHash": "#/watch?v=abc"}'
    )
    assert runtime.events == [
        "find_window",
        "snapshot:cdp",
        "evaluate:True",
    ]


def test_run_vacuumtube_select_account_if_needed_sends_enter_until_hint_clears() -> None:
    logs: list[str] = []
    events: list[str] = []
    sleep_calls: list[float] = []
    states = iter(
        [
            {"accountSelectHint": True},
            {"accountSelectHint": True},
            {"accountSelectHint": False},
        ]
    )
    now_values = iter([100.0, 100.1, 100.6, 100.9])

    out = run_vacuumtube_select_account_if_needed(
        snapshot_state=lambda: next(states),
        send_return_key=lambda: events.append("return"),
        log=logs.append,
        now=lambda: next(now_values),
        sleep=lambda seconds: sleep_calls.append(seconds),
        timeout_sec=2.0,
    )

    assert out is True
    assert events == ["return"]
    assert sleep_calls == [0.4]
    assert logs == [
        "VacuumTube account selection detected; sending Enter for default focus"
    ]


def test_run_vacuumtube_select_account_if_needed_logs_and_returns_false_on_error() -> None:
    logs: list[str] = []

    out = run_vacuumtube_select_account_if_needed(
        snapshot_state=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        send_return_key=lambda: None,
        log=logs.append,
        now=lambda: 100.0,
        sleep=lambda _seconds: None,
    )

    assert out is False
    assert logs == ["account selection check failed (continuing): boom"]


def test_run_vacuumtube_confirm_watch_playback_returns_confirmed_snapshot() -> None:
    logs: list[str] = []
    sleep_calls: list[float] = []
    states = iter(
        [
            {"hash": "#/watch?v=abc", "video": {"paused": True, "currentTime": 1}},
            {
                "hash": "#/watch?v=abc",
                "video": {"paused": False, "currentTime": 3},
                "confirmed": True,
            },
        ]
    )
    now_values = iter([100.0, 100.1, 100.5])

    out = run_vacuumtube_confirm_watch_playback(
        snapshot_state=lambda: next(states),
        is_watch_state=lambda snap: str(snap.get("hash") or "").startswith("#/watch"),
        playback_confirmed=lambda first, snap: bool(snap.get("confirmed")),
        try_resume_current_video=lambda: (_ for _ in ()).throw(AssertionError("should not resume")),
        log=logs.append,
        now=lambda: next(now_values),
        sleep=lambda seconds: sleep_calls.append(seconds),
        timeout_sec=3.0,
        allow_resume_attempts=False,
    )

    assert out["confirmed"] is True
    assert sleep_calls == [0.35]
    assert logs == [
        "watch playback confirmed: "
        + json.dumps(
            {"hash": "#/watch?v=abc", "video": {"paused": False, "currentTime": 3}},
            ensure_ascii=False,
        )
    ]


def test_run_vacuumtube_confirm_watch_playback_soft_confirms_unpaused_video() -> None:
    logs: list[str] = []
    states = iter(
        [
            {"hash": "#/watch?v=abc", "video": {"paused": True, "currentTime": 1}},
            {"hash": "#/watch?v=abc", "video": {"paused": False, "currentTime": 1}},
        ]
    )
    now_values = iter([100.0, 100.1, 100.5])

    out = run_vacuumtube_confirm_watch_playback(
        snapshot_state=lambda: next(states),
        is_watch_state=lambda snap: str(snap.get("hash") or "").startswith("#/watch"),
        playback_confirmed=lambda first, snap: False,
        try_resume_current_video=lambda: (_ for _ in ()).throw(AssertionError("should not resume")),
        log=logs.append,
        now=lambda: next(now_values),
        sleep=lambda _seconds: None,
        timeout_sec=3.0,
        allow_resume_attempts=False,
        allow_soft_confirm_when_unpaused=True,
    )

    assert out["video"]["paused"] is False
    assert logs == [
        "watch playback soft-confirmed: "
        + json.dumps(
            {"hash": "#/watch?v=abc", "video": {"paused": False, "currentTime": 1}},
            ensure_ascii=False,
        )
    ]


def test_run_vacuumtube_confirm_watch_playback_host_runtime_reads_runtime_methods() -> None:
    runtime = mock.Mock()
    runtime.log = mock.Mock()
    runtime._snapshot_state.return_value = {"hash": "#/watch?v=abc", "video": {"paused": False}}
    runtime._is_watch_state.return_value = True
    runtime._try_resume_current_video.return_value = True
    cdp = object()

    out = run_vacuumtube_confirm_watch_playback_host_runtime(
        runtime=runtime,
        cdp=cdp,
        playback_confirmed=lambda _first, _current: True,
        timeout_sec=4.0,
        allow_resume_attempts=False,
        allow_soft_confirm_when_unpaused=True,
    )

    assert out == {"hash": "#/watch?v=abc", "video": {"paused": False}}
    runtime._snapshot_state.assert_called_once_with(cdp)
    runtime._is_watch_state.assert_called_once_with(
        {"hash": "#/watch?v=abc", "video": {"paused": False}}
    )


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


def test_ensure_vacuumtube_runtime_ready_restarts_stale_tmux_session() -> None:
    events: list[str] = []
    ready_states = iter([False, True])

    def wait_ready(timeout: float) -> bool:
        events.append(f"wait_cdp_ready:{timeout}")
        return next(ready_states)

    ensure_vacuumtube_runtime_ready(
        cdp_ready=lambda: events.append("cdp_ready") or False,
        tmux_has=lambda: events.append("tmux_has") or True,
        wait_cdp_ready=wait_ready,
        restart_tmux_session=lambda: events.append("restart"),
        start_in_tmux=lambda: events.append("start"),
        log=events.append,
        tmux_session="vacuumtube-main",
        base_url="http://127.0.0.1:9992",
    )

    assert events == [
        "cdp_ready",
        "tmux_has",
        "wait_cdp_ready:2.5",
        "VacuumTube tmux session stale or crashed; restarting: vacuumtube-main",
        "restart",
        "wait_cdp_ready:35.0",
    ]


def test_ensure_vacuumtube_runtime_ready_starts_tmux_when_missing() -> None:
    events: list[str] = []

    def wait_ready(timeout: float) -> bool:
        events.append(f"wait_cdp_ready:{timeout}")
        return True

    ensure_vacuumtube_runtime_ready(
        cdp_ready=lambda: events.append("cdp_ready") or False,
        tmux_has=lambda: events.append("tmux_has") or False,
        wait_cdp_ready=wait_ready,
        restart_tmux_session=lambda: events.append("restart"),
        start_in_tmux=lambda: events.append("start"),
        log=events.append,
        tmux_session="vacuumtube-main",
        base_url="http://127.0.0.1:9992",
    )

    assert events == [
        "cdp_ready",
        "tmux_has",
        "start",
        "wait_cdp_ready:35.0",
    ]


def test_recover_vacuumtube_unresponsive_state_restarts_then_returns_positioned_state() -> None:
    events: list[str] = []

    def wait_ready(timeout: float) -> bool:
        events.append(f"wait_cdp_ready:{timeout}")
        return True

    def ensure_started() -> dict[str, str]:
        events.append("ensure_started")
        return {"window_id": "0x123"}

    result = recover_vacuumtube_unresponsive_state(
        restart_tmux_session=lambda: events.append("restart"),
        wait_cdp_ready=wait_ready,
        ensure_started_and_positioned=ensure_started,
        log=events.append,
        tmux_session="vacuumtube-main",
        base_url="http://127.0.0.1:9992",
    )

    assert result == {"window_id": "0x123"}
    assert events == [
        "VacuumTube recovery requested; restarting tmux session: vacuumtube-main",
        "restart",
        "wait_cdp_ready:35.0",
        "ensure_started",
    ]


def test_start_vacuumtube_tmux_session_starts_when_session_missing() -> None:
    events: list[object] = []

    start_vacuumtube_tmux_session(
        start_script="/opt/VacuumTube/start.sh",
        tmux_session="vacuumtube-main",
        path_exists=lambda path: events.append(("exists", path)) or True,
        tmux_has=lambda: events.append("tmux_has") or False,
        resolve_display=lambda: events.append("resolve_display") or ":0",
        build_start_command=lambda display: (
            events.append(("build", display)) or ["tmux", "new-session"]
        ),
        run_command=lambda command: events.append(("run", command)),
        log=events.append,
    )

    assert events == [
        ("exists", "/opt/VacuumTube/start.sh"),
        "tmux_has",
        "resolve_display",
        ("build", ":0"),
        ("run", ["tmux", "new-session"]),
        "VacuumTube tmux start requested: vacuumtube-main",
    ]


def test_start_vacuumtube_tmux_session_noops_when_session_exists() -> None:
    events: list[object] = []

    start_vacuumtube_tmux_session(
        start_script="/opt/VacuumTube/start.sh",
        tmux_session="vacuumtube-main",
        path_exists=lambda _path: True,
        tmux_has=lambda: True,
        resolve_display=lambda: (_ for _ in ()).throw(
            AssertionError("unexpected resolve_display")
        ),
        build_start_command=lambda _display: (_ for _ in ()).throw(
            AssertionError("unexpected build")
        ),
        run_command=lambda _command: (_ for _ in ()).throw(AssertionError("unexpected run")),
        log=events.append,
    )

    assert events == ["VacuumTube tmux session already exists: vacuumtube-main"]


def test_restart_vacuumtube_tmux_session_kills_then_restarts() -> None:
    events: list[object] = []

    restart_vacuumtube_tmux_session(
        tmux_has=lambda: True,
        build_kill_command=lambda: events.append("build_kill") or ["tmux", "kill-session"],
        run_command=lambda command: events.append(("run", command)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
        start_tmux_session=lambda: events.append("start"),
    )

    assert events == [
        "build_kill",
        ("run", ["tmux", "kill-session"]),
        ("sleep", 0.25),
        "start",
    ]


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


def test_run_vacuumtube_resume_playback_runtime_opens_cdp_and_reuses_resume_flow() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    result = run_vacuumtube_resume_playback_runtime(
        open_cdp=lambda: FakeContext(),
        find_window_id=lambda: "0x123",
        snapshot_state=lambda cdp: {"hash": "#/watch?v=abc", "cdp": cdp},
        is_watch_state=lambda _state: True,
        confirm_watch_playback=lambda cdp, **kwargs: events.append(
            f"confirm:{cdp}:{kwargs['timeout_sec']}:{kwargs.get('allow_resume_attempts', True)}"
        ),
        try_resume_current_video=lambda cdp: events.append(f"resume:{cdp}"),
        send_space_key=lambda: events.append("space"),
        ensure_top_right_position=lambda: events.append("ensure_top_right") or {"ok": True},
        log=events.append,
    )

    assert result == "watch route already playing (no-op)"
    assert events == [
        "enter",
        "confirm:cdp:1.2:False",
        "ensure_top_right",
        'RESUME already-playing window position: {"ok": true}',
        "exit",
    ]


def test_run_vacuumtube_resume_playback_host_runtime_uses_runtime_methods() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def _cdp(self) -> FakeContext:
            return FakeContext()

        def find_window_id(self) -> str | None:
            self.events.append("find_window")
            return "0x123"

        def _snapshot_state(self, cdp: str) -> dict[str, object]:
            self.events.append(f"snapshot:{cdp}")
            return {"hash": "#/watch?v=abc"}

        def _is_watch_state(self, state: dict[str, object]) -> bool:
            self.events.append(f"is_watch:{state.get('hash')}")
            return True

        def _wait_confirmed_watch_playback(self, cdp: str, **kwargs: object) -> dict[str, object]:
            self.events.append(
                f"confirm:{cdp}:{kwargs['timeout_sec']}:{kwargs.get('allow_resume_attempts', True)}"
            )
            return {"hash": "#/watch?v=abc"}

        def _try_resume_current_video(self, cdp: str) -> None:
            self.events.append(f"resume:{cdp}")

        def send_key(self, key: str) -> None:
            self.events.append(f"key:{key}")

        def ensure_top_right_position(self) -> dict[str, object]:
            self.events.append("ensure_top_right")
            return {"ok": True}

        def log(self, message: str) -> None:
            self.events.append(message)

    runtime = FakeRuntime()

    result = run_vacuumtube_resume_playback_host_runtime(runtime=runtime)

    assert result == "watch route already playing (no-op)"
    assert runtime.events == [
        "find_window",
        "snapshot:cdp",
        "is_watch:#/watch?v=abc",
        "confirm:cdp:1.2:False",
        "ensure_top_right",
        'RESUME already-playing window position: {"ok": true}',
    ]


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


def test_run_vacuumtube_go_home_runtime_opens_cdp_and_reuses_home_flow() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    result = run_vacuumtube_go_home_runtime(
        open_cdp=lambda: FakeContext(),
        presentation_before={"fullscreen": True, "window_id": "0x123"},
        hide_overlay_if_needed=lambda cdp: events.append(f"hide:{cdp}"),
        ensure_home=lambda cdp: (
            events.append(f"ensure_home:{cdp}") or {"hash": "#/", "tilesCount": 8}
        ),
        restore_window_presentation=lambda presentation, *, label: events.append(
            f"restore:{presentation['window_id']}:{label}"
        ),
        log=events.append,
    )

    assert result == 'youtube home verified {"hash": "#/", "tiles": 8}'
    assert events == [
        "enter",
        "hide:cdp",
        "ensure_home:cdp",
        "restore:0x123:YOUTUBE_HOME",
        "exit",
    ]


def test_run_vacuumtube_go_home_host_runtime_reads_runtime_methods() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        class _FakeContext:
            def __enter__(self) -> str:
                return "cdp"

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        def _cdp(self) -> _FakeContext:
            return self._FakeContext()

        def log(self, message: str) -> None:
            self.events.append(message)

        def _hide_overlay_if_needed(self, cdp: str) -> None:
            self.events.append(f"hide:{cdp}")

        def _ensure_home(self, cdp: str) -> dict[str, object]:
            self.events.append(f"ensure_home:{cdp}")
            return {"hash": "#/", "tilesCount": 8}

        def _restore_window_presentation(
            self,
            presentation: dict[str, object],
            *,
            label: str,
        ) -> None:
            self.events.append(f"restore:{presentation['window_id']}:{label}")

    runtime = FakeRuntime()

    result = run_vacuumtube_go_home_host_runtime(
        runtime=runtime,
        presentation_before={"fullscreen": True, "window_id": "0x123"},
    )

    assert result == 'youtube home verified {"hash": "#/", "tiles": 8}'
    assert runtime.events == [
        "hide:cdp",
        "ensure_home:cdp",
        "restore:0x123:YOUTUBE_HOME",
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


def test_run_vacuumtube_play_bgm_runtime_opens_cdp_and_reuses_bgm_flow() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    result = run_vacuumtube_play_bgm_runtime(
        open_cdp=lambda: FakeContext(),
        get_state=lambda cdp: {"accountSelectHint": False, "hash": "#/watch?v=abc", "cdp": cdp},
        send_return_key=lambda: events.append("return"),
        send_space_key=lambda: events.append("space"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        try_resume_current_video=lambda cdp: events.append(f"resume:{cdp}"),
        confirm_watch_playback=lambda cdp, **kwargs: events.append(
            f"confirm:{cdp}:{kwargs['timeout_sec']}:{kwargs['allow_soft_confirm_when_unpaused']}"
        ),
        open_from_home=lambda _cdp: (_ for _ in ()).throw(AssertionError("unexpected home open")),
        ensure_top_right_position=lambda: events.append("ensure_top_right") or {"ok": True},
        log=events.append,
    )

    assert result == "watch page detected; confirmed playback"
    assert events == [
        "enter",
        "resume:cdp",
        "confirm:cdp:4.0:True",
        "ensure_top_right",
        'BGM watch-resume window position: {"ok": true}',
        "exit",
    ]


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


def test_run_vacuumtube_play_bgm_runtime_passes_cdp_to_home_open() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    result = run_vacuumtube_play_bgm_runtime(
        open_cdp=lambda: FakeContext(),
        get_state=lambda cdp: (
            events.append(f"state:{cdp}") or {"accountSelectHint": False, "hash": "#/"}
        ),
        send_return_key=lambda: events.append("return"),
        send_space_key=lambda: events.append("space"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        try_resume_current_video=lambda cdp: events.append(f"resume:{cdp}"),
        confirm_watch_playback=lambda cdp, **kwargs: events.append(f"confirm:{cdp}:{kwargs}"),
        open_from_home=lambda cdp: (
            events.append(f"open:{cdp}") or "opened watch route #/watch?v=bgm"
        ),
        ensure_top_right_position=lambda: {"ok": True},
        log=events.append,
    )

    assert result == "opened watch route #/watch?v=bgm"
    assert events == [
        "enter",
        "state:cdp",
        "open:cdp",
        "exit",
    ]


def test_run_vacuumtube_play_bgm_host_runtime_uses_runtime_methods() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def log(self, message: str) -> None:
            self.events.append(message)

        def _cdp(self) -> FakeContext:
            return FakeContext()

        def _state(self, cdp: str) -> dict[str, object]:
            self.events.append(f"state:{cdp}")
            return {"accountSelectHint": False, "hash": "#/"}

        def send_key(self, key: str) -> None:
            self.events.append(f"key:{key}")

        def _try_resume_current_video(self, cdp: str) -> None:
            self.events.append(f"resume:{cdp}")

        def _hide_overlay_if_needed(self, cdp: str) -> None:
            self.events.append(f"hide:{cdp}")

        def _capture_window_presentation(self) -> dict[str, str]:
            self.events.append("capture")
            return {"window_id": "0x123"}

        def _ensure_home(self, cdp: str) -> dict[str, object]:
            self.events.append(f"home:{cdp}")
            return {"hash": "#/", "tilesCount": 1}

        def _enumerate_tiles(self, cdp: str) -> list[dict[str, object]]:
            self.events.append(f"tiles:{cdp}")
            return [{"title": "tile", "score": 1.0}]

        def _click_tile_center(self, cdp: str, tile: dict[str, object]) -> None:
            self.events.append(f"click:{cdp}:{tile['title']}")

        def _wait_watch_route(self, cdp: str, timeout: float) -> bool:
            self.events.append(f"wait:{cdp}:{timeout}")
            return True

        def _dom_click_tile(self, cdp: str, tile: dict[str, object]) -> bool:
            self.events.append(f"dom:{cdp}:{tile['title']}")
            return False

        def _wait_confirmed_watch_playback(self, cdp: str, **kwargs: object) -> dict[str, object]:
            self.events.append(
                f"confirm:{cdp}:{kwargs['timeout_sec']}:{kwargs.get('allow_soft_confirm_when_unpaused')}"
            )
            return {"hash": "#/watch?v=bgm"}

        def _score_bgm_tile(self, tile: dict[str, object]) -> float:
            return float(tile.get("score", 0.0))

        def _restore_window_presentation(
            self,
            presentation: dict[str, str],
            *,
            label: str,
        ) -> None:
            self.events.append(f"restore:{presentation['window_id']}:{label}")

        def ensure_top_right_position(self) -> dict[str, object]:
            self.events.append("position")
            return {"ok": True}

    runtime = FakeRuntime()

    result = run_vacuumtube_play_bgm_host_runtime(runtime=runtime, sleep=lambda _seconds: None)

    assert result == "opened watch route #/watch?v=bgm"
    assert runtime.events == [
        "state:cdp",
        "hide:cdp",
        "capture",
        "home:cdp",
        "BGM precondition home verified: hash=#/ tiles=1",
        "tiles:cdp",
        "BGM tile candidates: 1.0:tile",
        "BGM tile selected attempt=1: tile",
        "click:cdp:tile",
        "wait:cdp:2.5",
        "resume:cdp",
        "confirm:cdp:8.0:True",
        'BGM post-click state: {"hash": "#/watch?v=bgm", "title": null, "video": null}',
        "restore:0x123:BGM",
    ]


def test_run_vacuumtube_open_from_home_runtime_opens_cdp_and_reuses_flow() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    result = run_vacuumtube_open_from_home_runtime(
        open_cdp=lambda: FakeContext(),
        label="BGM",
        scorer=lambda tile: float(tile.get("score", 0.0)),
        filter_fn=None,
        allow_soft_playback_confirm=True,
        hide_overlay_if_needed=lambda cdp: events.append(f"hide:{cdp}"),
        capture_window_presentation=lambda: events.append("capture") or {"window_id": "0x123"},
        ensure_home=lambda cdp: events.append(f"home:{cdp}") or {"hash": "#/", "tilesCount": 1},
        log=events.append,
        enumerate_tiles=lambda cdp: (
            events.append(f"tiles:{cdp}") or [{"title": "tile", "score": 1.0}]
        ),
        click_tile_center=lambda cdp, tile: events.append(f"click:{cdp}:{tile['title']}"),
        wait_watch_route=lambda cdp, timeout: events.append(f"wait:{cdp}:{timeout}") or True,
        dom_click_tile=lambda cdp, tile: events.append(f"dom:{cdp}:{tile['title']}") or False,
        send_return_key=lambda: events.append("return"),
        try_resume_current_video=lambda cdp: events.append(f"resume:{cdp}"),
        wait_confirmed_watch_playback=lambda cdp, timeout, allow_soft: (
            events.append(f"confirm:{cdp}:{timeout}:{allow_soft}")
            or {"hash": "#/watch?v=abc", "title": "watch", "video": {"paused": False}}
        ),
        restore_window_presentation=lambda presentation, label: events.append(
            f"restore:{presentation['window_id']}:{label}"
        ),
    )

    assert result == "opened watch route #/watch?v=abc"
    assert events == [
        "enter",
        "hide:cdp",
        "capture",
        "home:cdp",
        "BGM precondition home verified: hash=#/ tiles=1",
        "tiles:cdp",
        "BGM tile candidates: 1.0:tile",
        "BGM tile selected attempt=1: tile",
        "click:cdp:tile",
        "wait:cdp:2.5",
        "resume:cdp",
        "confirm:cdp:8.0:True",
        (
            'BGM post-click state: {"hash": "#/watch?v=abc", '
            '"title": "watch", "video": {"paused": false}}'
        ),
        "restore:0x123:BGM",
        "exit",
    ]


def test_run_vacuumtube_open_from_home_host_runtime_reads_runtime_methods() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def log(self, message: str) -> None:
            self.events.append(message)

        def _hide_overlay_if_needed(self, cdp: str) -> None:
            self.events.append(f"hide:{cdp}")

        def _capture_window_presentation(self) -> dict[str, str]:
            self.events.append("capture")
            return {"window_id": "0x123"}

        def _ensure_home(self, cdp: str) -> dict[str, object]:
            self.events.append(f"home:{cdp}")
            return {"hash": "#/", "tilesCount": 1}

        def _enumerate_tiles(self, cdp: str) -> list[dict[str, object]]:
            self.events.append(f"tiles:{cdp}")
            return [{"title": "tile", "score": 1.0}]

        def _click_tile_center(self, cdp: str, tile: dict[str, object]) -> None:
            self.events.append(f"click:{cdp}:{tile['title']}")

        def _wait_watch_route(self, cdp: str, timeout: float) -> bool:
            self.events.append(f"wait:{cdp}:{timeout}")
            return True

        def _dom_click_tile(self, cdp: str, tile: dict[str, object]) -> bool:
            self.events.append(f"dom:{cdp}:{tile['title']}")
            return False

        def send_key(self, key: str) -> None:
            self.events.append(f"key:{key}")

        def _try_resume_current_video(self, cdp: str) -> None:
            self.events.append(f"resume:{cdp}")

        def _wait_confirmed_watch_playback(
            self,
            cdp: str,
            *,
            timeout_sec: float,
            allow_soft_confirm_when_unpaused: bool,
        ) -> dict[str, object]:
            self.events.append(
                f"confirm:{cdp}:{timeout_sec}:{allow_soft_confirm_when_unpaused}"
            )
            return {"hash": "#/watch?v=abc", "title": "watch", "video": {"paused": False}}

        def _restore_window_presentation(
            self,
            presentation: dict[str, str],
            *,
            label: str,
        ) -> None:
            self.events.append(f"restore:{presentation['window_id']}:{label}")

    runtime = FakeRuntime()

    result = run_vacuumtube_open_from_home_host_runtime(
        cdp="cdp",
        runtime=runtime,
        label="BGM",
        scorer=lambda tile: float(tile.get("score", 0.0)),
        filter_fn=None,
        allow_soft_playback_confirm=True,
    )

    assert result == "opened watch route #/watch?v=abc"
    assert runtime.events == [
        "hide:cdp",
        "capture",
        "home:cdp",
        "BGM precondition home verified: hash=#/ tiles=1",
        "tiles:cdp",
        "BGM tile candidates: 1.0:tile",
        "BGM tile selected attempt=1: tile",
        "click:cdp:tile",
        "wait:cdp:2.5",
        "resume:cdp",
        "confirm:cdp:8.0:True",
        (
            'BGM post-click state: {"hash": "#/watch?v=abc", '
            '"title": "watch", "video": {"paused": false}}'
        ),
        "restore:0x123:BGM",
    ]


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


def test_run_vacuumtube_fullscreen_host_runtime_uses_runtime_methods() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []
            self._geometries = iter(
                [
                    {"x": 100, "y": 100, "w": 1280, "h": 720},
                    {"x": 0, "y": 0, "w": 1920, "h": 1080},
                ]
            )

        def ensure_started_and_positioned(self) -> None:
            self.events.append("ensure_started")

        def wait_window(self) -> str:
            self.events.append("wait_window")
            return "0x123"

        def activate_window(self, win_id: str) -> None:
            self.events.append(f"activate:{win_id}")

        def get_window_geometry(self, _win_id: str) -> dict[str, int]:
            return next(self._geometries)

        def _set_fullscreen(self, win_id: str, *, enabled: bool) -> None:
            self.events.append(f"fullscreen:{win_id}:{enabled}")

        def _wait_fullscreen(self, win_id: str, *, enabled: bool, timeout_sec: float) -> bool:
            self.events.append(f"wait_fullscreen:{win_id}:{enabled}:{timeout_sec}")
            return True

    runtime = FakeRuntime()

    result = run_vacuumtube_fullscreen_host_runtime(runtime=runtime)

    assert json.loads(result.removeprefix("youtube fullscreen ")) == {
        "fullscreen": True,
        "before": {"x": 100, "y": 100, "w": 1280, "h": 720},
        "after": {"x": 0, "y": 0, "w": 1920, "h": 1080},
    }
    assert runtime.events == [
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


def test_run_vacuumtube_quadrant_host_runtime_uses_runtime_methods() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def ensure_started_and_positioned(self) -> None:
            self.events.append("ensure_started")

        def ensure_top_right_position(self) -> dict[str, object]:
            self.events.append("ensure_top_right")
            return {"ok": True, "window_id": "0x123"}

    runtime = FakeRuntime()

    result = run_vacuumtube_quadrant_host_runtime(runtime=runtime)

    assert result == 'youtube quadrant {"ok": true, "window_id": "0x123"}'
    assert runtime.events == ["ensure_started", "ensure_top_right"]


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


def test_run_vacuumtube_stop_music_runtime_opens_cdp_and_reuses_stop_flow() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    events: list[str] = []
    states = iter(
        [
            {"hash": "#/watch?v=abc", "video": {"paused": False}, "cdp": "cdp"},
            {"hash": "#/watch?v=abc", "video": {"paused": True}, "cdp": "cdp"},
        ]
    )

    result = run_vacuumtube_stop_music_runtime(
        open_cdp=lambda: FakeContext(),
        find_window_id=lambda: "0x123",
        snapshot_state=lambda cdp: next(states),
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


def test_run_vacuumtube_stop_music_host_runtime_uses_runtime_methods() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []
            self._states = iter(
                [
                    {"hash": "#/watch?v=abc", "video": {"paused": False}},
                    {"hash": "#/watch?v=abc", "video": {"paused": True}},
                ]
            )

        def _cdp(self) -> FakeContext:
            return FakeContext()

        def find_window_id(self) -> str | None:
            self.events.append("find_window")
            return "0x123"

        def _snapshot_state(self, cdp: str) -> dict[str, object]:
            self.events.append(f"snapshot:{cdp}")
            return next(self._states)

        def _is_watch_state(self, state: dict[str, object]) -> bool:
            self.events.append(f"is_watch:{state.get('hash')}")
            return str(state.get("hash", "")).startswith("#/watch")

        def send_key(self, key: str) -> None:
            self.events.append(f"key:{key}")

        def ensure_top_right_position(self) -> dict[str, object]:
            self.events.append("ensure_top_right")
            return {"ok": True, "window_id": "0x123"}

        def log(self, message: str) -> None:
            self.events.append(message)

    runtime = FakeRuntime()

    result = run_vacuumtube_stop_music_host_runtime(
        runtime=runtime,
        time_now=iter([100.0, 100.1]).__next__,
        sleep=lambda seconds: runtime.events.append(f"sleep:{seconds}"),
    )

    assert result == "sent Space toggle to VacuumTube (0x123); pause confirmed"
    assert runtime.events[:6] == [
        "find_window",
        "snapshot:cdp",
        "is_watch:#/watch?v=abc",
        "key:space",
        "snapshot:cdp",
        "is_watch:#/watch?v=abc",
    ]
    assert "ensure_top_right" in runtime.events


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


def test_run_vacuumtube_play_news_runtime_opens_cdp_and_reuses_news_flow() -> None:
    events: list[str] = []

    class FakeContext:
        def __enter__(self) -> str:
            events.append("enter")
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            events.append("exit")
            return None

    result = run_vacuumtube_play_news_runtime(
        open_cdp=lambda: FakeContext(),
        slot="morning",
        get_state=lambda cdp: events.append(f"state:{cdp}") or {"accountSelectHint": False},
        send_return_key=lambda: events.append("return"),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
        open_from_home=lambda cdp, label: (
            events.append(f"open:{cdp}:{label}") or "opened watch route #/watch?v=morning"
        ),
    )

    assert result == "opened watch route #/watch?v=morning"
    assert events == [
        "enter",
        "state:cdp",
        "open:cdp:NEWS-MORNING",
        "exit",
    ]


def test_run_vacuumtube_play_news_host_runtime_uses_runtime_methods() -> None:
    class FakeContext:
        def __enter__(self) -> str:
            return "cdp"

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def log(self, message: str) -> None:
            self.events.append(message)

        def _cdp(self) -> FakeContext:
            return FakeContext()

        def _state(self, cdp: str) -> dict[str, object]:
            self.events.append(f"state:{cdp}")
            return {"accountSelectHint": False, "hash": "#/"}

        def send_key(self, key: str) -> None:
            self.events.append(f"key:{key}")

        def _hide_overlay_if_needed(self, cdp: str) -> None:
            self.events.append(f"hide:{cdp}")

        def _capture_window_presentation(self) -> dict[str, str]:
            self.events.append("capture")
            return {"window_id": "0x123"}

        def _ensure_home(self, cdp: str) -> dict[str, object]:
            self.events.append(f"home:{cdp}")
            return {"hash": "#/", "tilesCount": 1}

        def _enumerate_tiles(self, cdp: str) -> list[dict[str, object]]:
            self.events.append(f"tiles:{cdp}")
            return [{"title": "morning news", "score": 1.0, "visible": True}]

        def _click_tile_center(self, cdp: str, tile: dict[str, object]) -> None:
            self.events.append(f"click:{cdp}:{tile['title']}")

        def _wait_watch_route(self, cdp: str, timeout: float) -> bool:
            self.events.append(f"wait:{cdp}:{timeout}")
            return True

        def _dom_click_tile(self, cdp: str, tile: dict[str, object]) -> bool:
            self.events.append(f"dom:{cdp}:{tile['title']}")
            return False

        def _try_resume_current_video(self, cdp: str) -> None:
            self.events.append(f"resume:{cdp}")

        def _wait_confirmed_watch_playback(self, cdp: str, **kwargs: object) -> dict[str, object]:
            self.events.append(
                f"confirm:{cdp}:{kwargs['timeout_sec']}:{kwargs.get('allow_soft_confirm_when_unpaused')}"
            )
            return {"hash": "#/watch?v=morning", "title": "watch", "video": {"paused": False}}

        def _restore_window_presentation(
            self,
            presentation: dict[str, str],
            *,
            label: str,
        ) -> None:
            self.events.append(f"restore:{presentation['window_id']}:{label}")

        def _score_news_tile(self, tile: dict[str, object], *, slot: str = "generic") -> float:
            return float(tile.get("score", 0.0))

    runtime = FakeRuntime()

    result = run_vacuumtube_play_news_host_runtime(
        runtime=runtime,
        slot="morning",
        sleep=lambda _seconds: None,
        filter_tile=lambda tile: bool(tile.get("visible")),
    )

    assert result == "opened watch route #/watch?v=morning"
    assert runtime.events == [
        "state:cdp",
        "hide:cdp",
        "capture",
        "home:cdp",
        "NEWS-MORNING precondition home verified: hash=#/ tiles=1",
        "tiles:cdp",
        "NEWS-MORNING filtered candidates: 1/1",
        "NEWS-MORNING tile candidates: 1.0:morning news",
        "NEWS-MORNING tile selected attempt=1: morning news",
        "click:cdp:morning news",
        "wait:cdp:2.5",
        "resume:cdp",
        "confirm:cdp:8.0:True",
        (
            'NEWS-MORNING post-click state: {"hash": "#/watch?v=morning", '
            '"title": "watch", "video": {"paused": false}}'
        ),
        "restore:0x123:NEWS-MORNING",
    ]


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


def test_run_vacuumtube_minimize_host_runtime_uses_runtime_methods() -> None:
    commands: list[list[str]] = []

    class FakeRuntime:
        def find_window_id(self) -> str | None:
            return "0x123"

    result = run_vacuumtube_minimize_host_runtime(
        runtime=FakeRuntime(),
        build_minimize_command=lambda win_id: ["xdotool", "windowminimize", win_id],
        run_command=commands.append,
    )

    assert result == "youtube minimize: ok (win_id=0x123)"
    assert commands == [["xdotool", "windowminimize", "0x123"]]


def test_run_vacuumtube_open_from_home_uses_return_fallback_and_restores_presentation() -> None:
    events: list[str] = []
    wait_results = iter([False, False, True])
    tile = {"title": "Best Tile", "text": "Best Tile", "hasJaLiveBadge": True}

    result = run_vacuumtube_open_from_home(
        label="NEWS",
        scorer=lambda candidate: 9.5 if candidate is tile else 0.0,
        filter_fn=lambda candidate: True,
        allow_soft_playback_confirm=True,
        hide_overlay_if_needed=lambda: events.append("hide_overlay"),
        capture_window_presentation=lambda: {"fullscreen": True},
        ensure_home=lambda: {"hash": "#/", "tilesCount": 3},
        log=events.append,
        enumerate_tiles=lambda: [tile],
        click_tile_center=lambda candidate: events.append(f"click:{candidate['title']}"),
        wait_watch_route=lambda timeout: events.append(f"wait:{timeout}") or next(wait_results),
        dom_click_tile=lambda candidate: events.append(f"dom:{candidate['title']}") or False,
        send_return_key=lambda: events.append("return"),
        try_resume_current_video=lambda: events.append("resume"),
        wait_confirmed_watch_playback=lambda timeout, allow_soft: (
            events.append(f"confirm:{timeout}:{allow_soft}")
            or {"hash": "#/watch?v=abc", "title": "Video", "video": {"paused": False}}
        ),
        restore_window_presentation=lambda presentation, label: events.append(
            f"restore:{label}:{presentation['fullscreen']}"
        ),
    )

    assert result == "opened watch route #/watch?v=abc"
    assert events == [
        "hide_overlay",
        "NEWS precondition home verified: hash=#/ tiles=3",
        "NEWS filtered candidates: 1/1",
        "NEWS tile candidates: 9.5:Best Tile [ライブ]",
        "NEWS tile selected attempt=1: Best Tile",
        "click:Best Tile",
        "wait:2.5",
        "click:Best Tile",
        "wait:2.5",
        "dom:Best Tile",
        "return",
        "wait:2.0",
        "resume",
        "confirm:8.0:True",
        (
            'NEWS post-click state: {"hash": "#/watch?v=abc", "title": "Video", '
            '"video": {"paused": false}}'
        ),
        "restore:NEWS:True",
    ]


def test_run_vacuumtube_open_from_home_raises_when_filter_removes_all_candidates() -> None:
    try:
        run_vacuumtube_open_from_home(
            label="BGM",
            scorer=lambda candidate: 1.0,
            filter_fn=lambda candidate: False,
            allow_soft_playback_confirm=False,
            hide_overlay_if_needed=lambda: None,
            capture_window_presentation=lambda: {"fullscreen": False},
            ensure_home=lambda: {"hash": "#/", "tilesCount": 1},
            log=lambda _message: None,
            enumerate_tiles=lambda: [{"title": "Nope"}],
            click_tile_center=lambda candidate: None,
            wait_watch_route=lambda timeout: False,
            dom_click_tile=lambda candidate: False,
            send_return_key=lambda: None,
            try_resume_current_video=lambda: None,
            wait_confirmed_watch_playback=lambda timeout, allow_soft: {"hash": "#/watch?v=abc"},
            restore_window_presentation=lambda presentation, label: None,
        )
    except RuntimeError as exc:
        assert str(exc) == "BGM candidates not found on home screen"
    else:
        raise AssertionError("expected RuntimeError")
