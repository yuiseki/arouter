from __future__ import annotations

from arouter import chromium_window_ids_from_wmctrl_lines, window_title_from_wmctrl_lines


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
