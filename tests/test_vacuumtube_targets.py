from __future__ import annotations

from arouter import select_vacuumtube_page_target, select_vacuumtube_websocket_url


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


def test_select_vacuumtube_websocket_url_returns_string_field() -> None:
    assert (
        select_vacuumtube_websocket_url(
            {"webSocketDebuggerUrl": "ws://127.0.0.1:9992/devtools/page/1"}
        )
        == "ws://127.0.0.1:9992/devtools/page/1"
    )


def test_select_vacuumtube_websocket_url_returns_none_for_missing_or_empty_field() -> None:
    assert select_vacuumtube_websocket_url({"webSocketDebuggerUrl": ""}) is None
    assert select_vacuumtube_websocket_url({"url": "https://example.com"}) is None
