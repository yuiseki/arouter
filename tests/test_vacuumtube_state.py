from __future__ import annotations

from arouter import (
    vacuumtube_is_home_browse_state,
    vacuumtube_is_watch_state,
    vacuumtube_needs_hard_reload_home,
    vacuumtube_video_current_time,
    vacuumtube_video_playing,
)


def test_vacuumtube_is_watch_state_uses_hash_prefix() -> None:
    assert vacuumtube_is_watch_state({"hash": "#/watch?v=abc"})
    assert not vacuumtube_is_watch_state({"hash": "#/"})


def test_vacuumtube_video_playing_and_current_time_handle_missing_video() -> None:
    assert not vacuumtube_video_playing({})
    assert vacuumtube_video_current_time({}) == 0.0


def test_vacuumtube_is_home_browse_state_rejects_account_select_even_with_tiles() -> None:
    assert not vacuumtube_is_home_browse_state(
        {
            "hash": "#/",
            "tilesCount": 12,
            "homeHint": True,
            "accountSelectHint": True,
            "video": None,
        }
    )


def test_vacuumtube_is_home_browse_state_rejects_active_video_even_with_home_hash() -> None:
    assert not vacuumtube_is_home_browse_state(
        {
            "hash": "#/",
            "tilesCount": 12,
            "homeHint": False,
            "accountSelectHint": False,
            "video": {"paused": False, "currentTime": 34.2, "readyState": 4},
        }
    )


def test_vacuumtube_is_home_browse_state_accepts_home_hint_with_tiles() -> None:
    assert vacuumtube_is_home_browse_state(
        {
            "hash": "#/",
            "tilesCount": 3,
            "homeHint": True,
            "watchUiHint": False,
            "accountSelectHint": False,
            "video": None,
        }
    )


def test_vacuumtube_is_home_browse_state_allows_tile_fallback_without_home_hint() -> None:
    assert vacuumtube_is_home_browse_state(
        {
            "hash": "#/",
            "tilesCount": 6,
            "homeHint": False,
            "watchUiHint": False,
            "accountSelectHint": False,
            "video": None,
        }
    )


def test_vacuumtube_is_home_browse_state_rejects_watch_ui_hint_even_with_home_hash() -> None:
    assert not vacuumtube_is_home_browse_state(
        {
            "hash": "#/",
            "tilesCount": 8,
            "homeHint": False,
            "watchUiHint": True,
            "accountSelectHint": False,
            "video": {"paused": True, "currentTime": 12.0, "readyState": 4},
        }
    )


def test_vacuumtube_needs_hard_reload_home_when_home_hash_has_zero_tiles() -> None:
    assert vacuumtube_needs_hard_reload_home(
        {
            "hash": "#/",
            "tilesCount": 0,
            "watchUiHint": False,
        }
    )


def test_vacuumtube_needs_hard_reload_home_when_home_hash_still_has_watch_ui_hint() -> None:
    assert vacuumtube_needs_hard_reload_home(
        {
            "hash": "#/",
            "tilesCount": 8,
            "watchUiHint": True,
        }
    )


def test_vacuumtube_needs_hard_reload_home_false_for_verified_home_candidate() -> None:
    assert not vacuumtube_needs_hard_reload_home(
        {
            "hash": "#/",
            "tilesCount": 8,
            "watchUiHint": False,
        }
    )
