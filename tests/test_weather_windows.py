from __future__ import annotations

from arouter import (
    build_weather_pages_closed_response,
    build_weather_pages_tiled_response,
    build_weather_tile_result,
    prune_weather_window_history,
)


def test_build_weather_tile_result_adds_spec_metadata() -> None:
    result = build_weather_tile_result(
        spec={"label": "jwa_amesh", "url": "https://tokyo-ame.jwa.or.jp/"},
        moved={"window_id": "0x1", "target": {"x": 0}},
    )

    assert result == {
        "window_id": "0x1",
        "target": {"x": 0},
        "label": "jwa_amesh",
        "url": "https://tokyo-ame.jwa.or.jp/",
    }


def test_build_weather_pages_tiled_response_wraps_json() -> None:
    assert (
        build_weather_pages_tiled_response([{"label": "jwa_amesh"}])
        == 'weather pages tiled [{"label": "jwa_amesh"}]'
    )


def test_prune_weather_window_history_keeps_only_remaining_ids() -> None:
    assert prune_weather_window_history(["0x1", "0x2"], {"0x2", "0x3"}) == ["0x2"]


def test_build_weather_pages_closed_response_wraps_count_and_ids() -> None:
    assert (
        build_weather_pages_closed_response(["0x1", "0x2"])
        == 'weather pages closed {"closed": 2, "ids": ["0x1", "0x2"]}'
    )
