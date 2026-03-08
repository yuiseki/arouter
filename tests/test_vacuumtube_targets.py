from __future__ import annotations

from arouter import select_vacuumtube_page_target


def test_select_vacuumtube_page_target_prefers_youtube_tv_url() -> None:
    targets = [
        {"type": "page", "url": "https://example.com", "title": "Other"},
        {"type": "page", "url": "https://www.youtube.com/tv#/", "title": "YouTube TV"},
    ]

    assert select_vacuumtube_page_target(targets) == targets[1]


def test_select_vacuumtube_page_target_falls_back_to_vacuumtube_title() -> None:
    targets = [
        {"type": "page", "url": "https://example.com", "title": "Other"},
        {"type": "page", "url": "https://example.com/player", "title": "VacuumTube Kiosk"},
    ]

    assert select_vacuumtube_page_target(targets) == targets[1]


def test_select_vacuumtube_page_target_returns_first_page_when_only_generic_pages_exist() -> None:
    targets = [
        {"type": "other", "url": "https://ignored.example", "title": "Ignored"},
        {"type": "page", "url": "https://example.com/one", "title": "One"},
        {"type": "page", "url": "https://example.com/two", "title": "Two"},
    ]

    assert select_vacuumtube_page_target(targets) == targets[1]


def test_select_vacuumtube_page_target_returns_none_for_non_list_payload() -> None:
    assert select_vacuumtube_page_target({"type": "page"}) is None
