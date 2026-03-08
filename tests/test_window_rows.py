from __future__ import annotations

import pytest

from arouter import (
    chromium_window_ids_from_wmctrl_lines,
    detect_new_window_id,
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
