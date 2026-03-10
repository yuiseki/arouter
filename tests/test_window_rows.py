from __future__ import annotations

import pytest

from arouter import (
    chromium_window_ids_from_wmctrl_lines,
    detect_new_window_id,
    find_window_geometry_from_wmctrl_lines,
    find_window_id_by_pid_and_title,
    find_window_id_by_title,
    find_window_row_by_pid_and_title,
    looks_like_weather_chromium_title,
    run_detect_new_window_id_host_runtime,
    run_wait_for_window_id_host_runtime,
    select_weather_candidate_window_ids,
    wait_for_window_id,
    window_rows_for_pids_from_wmctrl_lines,
    window_title_from_wmctrl_lines,
)


def test_window_title_from_wmctrl_lines_keeps_full_title() -> None:
    title = window_title_from_wmctrl_lines(
        [
            "0x050000b5  0 yuisekin-z 東京アメッシュ - Chromium",
        ],
        "0x050000b5",
    )

    assert title == "東京アメッシュ - Chromium"


def test_window_title_from_wmctrl_lines_returns_empty_for_missing_window() -> None:
    title = window_title_from_wmctrl_lines(
        [
            "0x050000b5  0 yuisekin-z 東京アメッシュ - Chromium",
        ],
        "0x0badbeef",
    )

    assert title == ""


def test_chromium_window_ids_from_wmctrl_lines_filters_chromium_titles() -> None:
    ids = chromium_window_ids_from_wmctrl_lines(
        [
            "0x050000b5  0 yuisekin-z 東京アメッシュ - Chromium",
            "0x00a00004  0 yuisekin-z VacuumTube",
            "broken",
        ]
    )

    assert ids == {"0x050000b5"}


def test_looks_like_weather_chromium_title_requires_weather_keyword_and_chromium() -> None:
    assert looks_like_weather_chromium_title("東京アメッシュ - Chromium") is True
    assert looks_like_weather_chromium_title("東京アメッシュ - VacuumTube") is False


def test_select_weather_candidate_window_ids_prefers_known_ids_then_title_fallback() -> None:
    candidate_ids = select_weather_candidate_window_ids(
        [
            "0x050000b5  0 yuisekin-z 東京アメッシュ - Chromium",
            "0x00a00004  0 yuisekin-z VacuumTube",
            "0x00b00005  0 yuisekin-z Yahoo!天気・災害 - Chromium",
        ],
        last_weather_window_ids=["0x00b00005", "0x0badbeef", "0x00b00005"],
    )

    assert candidate_ids == ["0x00b00005", "0x050000b5"]


def test_select_weather_candidate_window_ids_falls_back_to_weather_titles_when_history_empty(
) -> None:
    candidate_ids = select_weather_candidate_window_ids(
        [
            "0x050000b5  0 yuisekin-z 東京アメッシュ - Chromium",
            "0x00a00004  0 yuisekin-z VacuumTube",
        ],
        last_weather_window_ids=[],
    )

    assert candidate_ids == ["0x050000b5"]


def test_detect_new_window_id_returns_new_id_when_it_appears() -> None:
    clock = {"now": 0.0}

    def current_ids() -> set[str]:
        if clock["now"] < 0.25:
            return {"0x001"}
        return {"0x001", "0x002"}

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    detected = detect_new_window_id(
        before_ids={"0x001"},
        current_ids=current_ids,
        active_window_id=lambda: None,
        title_for_window_id=lambda _win_id: "",
        title_hint="Chromium",
        timeout_sec=1.0,
        now=now,
        sleep=sleep,
    )

    assert detected == "0x002"


def test_detect_new_window_id_falls_back_to_active_window() -> None:
    clock = {"now": 0.0}

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    detected = detect_new_window_id(
        before_ids={"0x001"},
        current_ids=lambda: {"0x001"},
        active_window_id=lambda: "0xabc",
        title_for_window_id=lambda _win_id: "Chromium",
        title_hint="Chromium",
        timeout_sec=0.1,
        now=now,
        sleep=sleep,
    )

    assert detected == "0xabc"


def test_detect_new_window_id_raises_when_no_window_detected() -> None:
    clock = {"now": 0.0}

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    with pytest.raises(RuntimeError, match="could not detect newly opened Chromium window"):
        detect_new_window_id(
            before_ids={"0x001"},
            current_ids=lambda: {"0x001"},
            active_window_id=lambda: None,
            title_for_window_id=lambda _win_id: "",
            title_hint="Chromium",
            timeout_sec=0.1,
            now=now,
            sleep=sleep,
        )


def test_find_window_id_by_pid_and_title_matches_pid_and_title_hint() -> None:
    win_id = find_window_id_by_pid_and_title(
        [
            "0x001 0 123 host Other",
            "0x002 0 456 host VacuumTube",
        ],
        pid=456,
        title_hint="VacuumTube",
    )

    assert win_id == "0x002"


def test_find_window_id_by_title_returns_first_matching_window() -> None:
    win_id = find_window_id_by_title(
        [
            "0x001 0 host VacuumTube",
            "0x002 0 host Chromium",
        ],
        title_hint="VacuumTube",
    )

    assert win_id == "0x001"


def test_find_window_geometry_from_wmctrl_lines_reads_target_geometry() -> None:
    geom = find_window_geometry_from_wmctrl_lines(
        [
            "0x001 0 10 20 30 40 host VacuumTube",
        ],
        "0x001",
    )

    assert geom == {"x": 10, "y": 20, "w": 30, "h": 40}


def test_window_rows_for_pids_from_wmctrl_lines_filters_target_pids() -> None:
    rows = window_rows_for_pids_from_wmctrl_lines(
        [
            "0x001 0 101 10 20 30 40 host VacuumTube Main",
            "0x002 0 202 11 21 31 41 host VacuumTube Side",
            "broken row",
        ],
        pids=[202],
    )

    assert rows == [
        {
            "id": "0x002",
            "pid": 202,
            "x": 11,
            "y": 21,
            "w": 31,
            "h": 41,
            "title": "VacuumTube Side",
        }
    ]


def test_find_window_row_by_pid_and_title_returns_matching_row() -> None:
    row = find_window_row_by_pid_and_title(
        [
            "0x001 0 101 10 20 30 40 host VacuumTube Main",
            "0x002 0 202 11 21 31 41 host VacuumTube Side",
        ],
        pid=202,
        title_hint="VacuumTube",
    )

    assert row == {
        "id": "0x002",
        "pid": 202,
        "x": 11,
        "y": 21,
        "w": 31,
        "h": 41,
        "title": "VacuumTube Side",
    }


def test_wait_for_window_id_polls_until_window_appears() -> None:
    clock = {"now": 0.0}

    def current_window_id() -> str | None:
        if clock["now"] < 0.4:
            return None
        return "0x123"

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    win_id = wait_for_window_id(
        current_window_id=current_window_id,
        timeout_sec=1.0,
        now=now,
        sleep=sleep,
    )

    assert win_id == "0x123"


def test_wait_for_window_id_raises_on_timeout() -> None:
    clock = {"now": 0.0}

    def now() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    with pytest.raises(RuntimeError, match="VacuumTube window not found"):
        wait_for_window_id(
            current_window_id=lambda: None,
            timeout_sec=0.1,
            now=now,
            sleep=sleep,
        )


def test_run_detect_new_window_id_host_runtime_reads_runtime_methods() -> None:
    events: list[object] = []

    class FakeRuntime:
        def _chromium_window_ids(self) -> set[str]:
            events.append("current_ids")
            return {"0x001", "0x002"}

        def _active_window_id_from_xdotool(self) -> str | None:
            events.append("active")
            return "0x002"

        def _window_title_from_wmctrl(self, win_id: str) -> str:
            events.append(("title", win_id))
            return "Chromium"

        def _time_now(self) -> float:
            return 100.0

        def _sleep(self, seconds: float) -> None:
            events.append(("sleep", seconds))

    out = run_detect_new_window_id_host_runtime(
        runtime=FakeRuntime(),
        before_ids={"0x001"},
        timeout_sec=3.0,
    )

    assert out == "0x002"
    assert events == ["current_ids"]


def test_run_wait_for_window_id_host_runtime_reads_runtime_methods() -> None:
    events: list[object] = []

    class FakeRuntime:
        def find_window_id(self) -> str | None:
            events.append("find_window")
            return "0x123"

        def _time_now(self) -> float:
            return 100.0

        def _sleep(self, seconds: float) -> None:
            events.append(("sleep", seconds))

    out = run_wait_for_window_id_host_runtime(
        runtime=FakeRuntime(),
        timeout_sec=3.0,
    )

    assert out == "0x123"
    assert events == ["find_window"]
