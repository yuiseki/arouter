from __future__ import annotations

import pytest

from arouter import (
    run_vacuumtube_cdp_client,
    run_vacuumtube_page_cdp_client,
    run_vacuumtube_page_cdp_runtime,
    run_vacuumtube_page_target_query,
    select_vacuumtube_page_target,
    select_vacuumtube_websocket_url,
)


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


def test_run_vacuumtube_page_target_query_returns_selected_target() -> None:
    target = run_vacuumtube_page_target_query(
        fetch_targets=lambda: [{"type": "page", "url": "https://www.youtube.com/tv#/"}],
        select_target=select_vacuumtube_page_target,
    )

    assert target == {"type": "page", "url": "https://www.youtube.com/tv#/"}


def test_run_vacuumtube_page_target_query_raises_without_target() -> None:
    with pytest.raises(RuntimeError, match="no VacuumTube/YouTube TV page target found in CDP"):
        run_vacuumtube_page_target_query(
            fetch_targets=lambda: [],
            select_target=select_vacuumtube_page_target,
        )


def test_run_vacuumtube_cdp_client_selects_websocket_and_enables_client() -> None:
    events: list[object] = []

    client = run_vacuumtube_cdp_client(
        target={"webSocketDebuggerUrl": "ws://127.0.0.1:9992/devtools/page/1"},
        select_websocket_url=select_vacuumtube_websocket_url,
        create_client=lambda ws_url: events.append(("create", ws_url)) or {"ws_url": ws_url},
        enable_client=lambda cdp: events.append(("enable", cdp["ws_url"])),
    )

    assert client == {"ws_url": "ws://127.0.0.1:9992/devtools/page/1"}
    assert events == [
        ("create", "ws://127.0.0.1:9992/devtools/page/1"),
        ("enable", "ws://127.0.0.1:9992/devtools/page/1"),
    ]


def test_run_vacuumtube_cdp_client_raises_without_websocket_url() -> None:
    with pytest.raises(RuntimeError, match="CDP target missing webSocketDebuggerUrl"):
        run_vacuumtube_cdp_client(
            target={"title": "no websocket"},
            select_websocket_url=select_vacuumtube_websocket_url,
            create_client=lambda _ws_url: object(),
            enable_client=lambda _client: None,
        )


def test_run_vacuumtube_page_cdp_client_queries_target_and_enables_client() -> None:
    events: list[object] = []

    client = run_vacuumtube_page_cdp_client(
        fetch_targets=lambda: [
            {
                "type": "page",
                "url": "https://www.youtube.com/tv#/",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9992/devtools/page/1",
            }
        ],
        select_target=select_vacuumtube_page_target,
        select_websocket_url=select_vacuumtube_websocket_url,
        create_client=lambda ws_url: events.append(("create", ws_url)) or {"ws_url": ws_url},
        enable_client=lambda client: events.append(("enable", client["ws_url"])),
    )

    assert client == {"ws_url": "ws://127.0.0.1:9992/devtools/page/1"}
    assert events == [
        ("create", "ws://127.0.0.1:9992/devtools/page/1"),
        ("enable", "ws://127.0.0.1:9992/devtools/page/1"),
    ]


def test_run_vacuumtube_page_cdp_runtime_creates_client_and_enables_basics() -> None:
    events: list[object] = []

    class FakeClient:
        def __init__(self, ws_url: str) -> None:
            events.append(("create", ws_url))
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            events.append(("enable", self.ws_url))

    client = run_vacuumtube_page_cdp_runtime(
        fetch_targets=lambda: [
            {
                "type": "page",
                "url": "https://www.youtube.com/tv#/",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9992/devtools/page/1",
            }
        ],
        select_target=select_vacuumtube_page_target,
        select_websocket_url=select_vacuumtube_websocket_url,
        create_client=FakeClient,
    )

    assert isinstance(client, FakeClient)
    assert events == [
        ("create", "ws://127.0.0.1:9992/devtools/page/1"),
        ("enable", "ws://127.0.0.1:9992/devtools/page/1"),
    ]
