from __future__ import annotations

from unittest import mock

from arouter import (
    build_weather_pages_closed_response,
    build_weather_pages_tiled_response,
    build_weather_tile_result,
    close_weather_pages_flow,
    open_weather_pages_flow,
    prune_weather_window_history,
    run_weather_pages_closed,
    run_weather_pages_closed_host_runtime,
    run_weather_pages_tiled,
    run_weather_pages_tiled_host_runtime,
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


def test_open_weather_pages_flow_returns_history_and_response() -> None:
    launched: list[str] = []
    moved_calls: list[tuple[str, dict[str, int]]] = []

    def move_window(win_id: str, geom: dict[str, int]) -> dict[str, str]:
        moved_calls.append((win_id, geom))
        return {"window_id": win_id}

    out = open_weather_pages_flow(
        [
            {
                "label": "amesh",
                "url": "https://example.test/amesh",
                "geom": {"x": 0, "y": 0, "w": 640, "h": 360},
            }
        ],
        current_window_ids=lambda: {"0x0bad"},
        launch_window=launched.append,
        detect_new_window=lambda before_ids, timeout_sec: "0xBEEF",
        move_window=move_window,
        build_tile_result=lambda spec, moved: {"label": spec["label"], **moved},
        build_response=build_weather_pages_tiled_response,
    )

    assert launched == ["https://example.test/amesh"]
    assert moved_calls == [("0xBEEF", {"x": 0, "y": 0, "w": 640, "h": 360})]
    assert out == {
        "opened_ids": ["0xbeef"],
        "results": [{"label": "amesh", "window_id": "0xBEEF"}],
        "response": 'weather pages tiled [{"label": "amesh", "window_id": "0xBEEF"}]',
    }


def test_close_weather_pages_flow_closes_candidates_and_prunes_history() -> None:
    closed: list[str] = []
    after_close_calls: list[str] = []

    out = close_weather_pages_flow(
        ["0x1 0 host 東京アメッシュ - Chromium"],
        ["0x1", "0x2"],
        select_candidate_window_ids=lambda lines, last_ids: ["0x1"],
        close_window=closed.append,
        current_window_ids=lambda: {"0x2"},
        prune_history=prune_weather_window_history,
        build_response=build_weather_pages_closed_response,
        after_close=lambda: after_close_calls.append("slept"),
    )

    assert closed == ["0x1"]
    assert after_close_calls == ["slept"]
    assert out == {
        "candidate_ids": ["0x1"],
        "remaining_ids": {"0x2"},
        "history": ["0x2"],
        "response": 'weather pages closed {"closed": 1, "ids": ["0x1"]}',
    }


def test_run_weather_pages_tiled_uses_default_builders_and_returns_history() -> None:
    launched: list[str] = []
    moved_calls: list[tuple[str, dict[str, int]]] = []

    def move_window(win_id: str, geom: dict[str, int]) -> dict[str, object]:
        moved_calls.append((win_id, geom))
        return {"window_id": win_id, "target": dict(geom)}

    out = run_weather_pages_tiled(
        weather_desktop_tiles=[
            {
                "label": "amesh",
                "url": "https://example.test/amesh",
                "geom": {"x": 10, "y": 20, "w": 640, "h": 360},
            }
        ],
        current_window_ids=lambda: {"0x0bad"},
        launch_window=launched.append,
        detect_new_window=lambda before_ids, timeout_sec: "0xBEEF",
        move_window=move_window,
    )

    assert launched == ["https://example.test/amesh"]
    assert moved_calls == [("0xBEEF", {"x": 10, "y": 20, "w": 640, "h": 360})]
    assert out == {
        "history": ["0xbeef"],
        "response": (
            'weather pages tiled [{"window_id": "0xBEEF", "target": {"x": 10, '
            '"y": 20, "w": 640, "h": 360}, "label": "amesh", "url": '
            '"https://example.test/amesh"}]'
        ),
        "results": [
            {
                "window_id": "0xBEEF",
                "target": {"x": 10, "y": 20, "w": 640, "h": 360},
                "label": "amesh",
                "url": "https://example.test/amesh",
            }
        ],
    }


def test_run_weather_pages_closed_uses_default_helpers_and_returns_updated_history() -> None:
    closed: list[str] = []
    after_close_calls: list[str] = []

    out = run_weather_pages_closed(
        lines=["0x1 0 host 東京アメッシュ - Chromium"],
        last_weather_window_ids=["0x1", "0x2"],
        select_candidate_window_ids=lambda lines, last_ids: ["0x1"],
        close_window=closed.append,
        current_window_ids=lambda: {"0x2"},
        after_close=lambda: after_close_calls.append("slept"),
    )

    assert closed == ["0x1"]
    assert after_close_calls == ["slept"]
    assert out == {
        "history": ["0x2"],
        "response": 'weather pages closed {"closed": 1, "ids": ["0x1"]}',
        "candidate_ids": ["0x1"],
    }


def test_run_weather_pages_tiled_host_runtime_updates_history_from_runtime_methods() -> None:
    class FakeRuntime:
        _last_weather_window_ids: list[str] = []
        _weather_desktop_tiles = [
            {
                "label": "amesh",
                "url": "https://example.test/amesh",
                "geom": {"x": 10, "y": 20, "w": 640, "h": 360},
            }
        ]

        def _chromium_window_ids(self) -> set[str]:
            return {"0x0bad"}

        def _launch_chromium_new_window(self, _url: str) -> None:
            return None

        def _detect_new_chromium_window(self, _before: set[str], timeout_sec: float = 18.0) -> str:
            assert timeout_sec == 18.0
            return "0xBEEF"

        def _move_window_to_geometry(self, win_id: str, geom: dict[str, int]) -> dict[str, object]:
            return {"window_id": win_id, "target": dict(geom)}

    runtime = FakeRuntime()

    out = run_weather_pages_tiled_host_runtime(
        runtime=runtime,
    )

    assert out == (
        'weather pages tiled [{"window_id": "0xBEEF", "target": {"x": 10, "y": 20, '
        '"w": 640, "h": 360}, "label": "amesh", "url": "https://example.test/amesh"}]'
    )
    assert runtime._last_weather_window_ids == ["0xbeef"]


def test_run_weather_pages_closed_host_runtime_updates_history_from_runtime_methods() -> None:
    class FakeRuntime:
        _last_weather_window_ids = ["0x1", "0x2"]

        def _wmctrl_lines(self) -> list[str]:
            return ["0x1 0 host 東京アメッシュ - Chromium"]

        def _wmctrl_close_window(self, _win_id: str) -> None:
            return None

        def _chromium_window_ids(self) -> set[str]:
            return {"0x2"}

    runtime = FakeRuntime()

    out = run_weather_pages_closed_host_runtime(
        runtime=runtime,
        select_candidate_window_ids=lambda lines, history: ["0x1"],
        after_close=lambda: None,
    )

    assert out == 'weather pages closed {"closed": 1, "ids": ["0x1"]}'
    assert runtime._last_weather_window_ids == ["0x2"]


def test_run_weather_pages_closed_host_runtime_uses_default_selector_and_sleep() -> None:
    class FakeRuntime:
        _last_weather_window_ids = ["0x1", "0x2"]

        def _wmctrl_lines(self) -> list[str]:
            return ["0x1 0 host 東京アメッシュ - Chromium"]

        def _wmctrl_close_window(self, _win_id: str) -> None:
            return None

        def _chromium_window_ids(self) -> set[str]:
            return {"0x2"}

    runtime = FakeRuntime()
    sleep_calls: list[float] = []

    with mock.patch("arouter.weather_windows.time.sleep", side_effect=sleep_calls.append):
        out = run_weather_pages_closed_host_runtime(runtime=runtime)

    assert out == 'weather pages closed {"closed": 1, "ids": ["0x1"]}'
    assert runtime._last_weather_window_ids == ["0x2"]
    assert sleep_calls == [0.2]
