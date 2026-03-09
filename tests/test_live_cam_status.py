from __future__ import annotations

from arouter import (
    build_live_cam_page_brief,
    build_live_cam_runtime_url_entry,
    collect_live_cam_pages_by_port,
    collect_live_cam_runtime_state,
    collect_live_cam_runtime_urls,
    find_stuck_live_cam_specs,
    merge_live_cam_page_snapshot,
    page_matches_live_camera_spec,
    run_live_cam_page_brief_cdp_runtime,
    run_live_cam_page_brief_flow,
    run_live_cam_page_brief_host_runtime_flow,
    run_live_cam_page_brief_http_query,
    run_live_cam_page_brief_runtime_flow,
    run_live_cam_page_snapshot_query,
    run_live_cam_page_snapshot_via_websocket,
    run_live_cam_runtime_state_cdp_runtime,
    run_live_cam_runtime_state_host_runtime_query,
    run_live_cam_runtime_state_http_query,
    run_live_cam_stuck_specs_host_runtime_query,
    run_live_cam_stuck_specs_query,
    run_live_cam_target_inspection,
    run_live_cam_target_snapshot_cdp_runtime,
    run_live_cam_target_snapshot_runtime,
    select_live_cam_page_target,
    select_live_cam_page_url,
)


def test_select_live_cam_page_url_prefers_youtube_tv_page() -> None:
    assert (
        select_live_cam_page_url(
            [
                {"type": "page", "url": "https://example.test/other"},
                {"type": "page", "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
            ]
        )
        == "https://www.youtube.com/tv#/watch?v=abc123DEF45"
    )


def test_select_live_cam_page_target_falls_back_to_first_page() -> None:
    assert select_live_cam_page_target(
        [
            {"type": "service_worker", "url": "https://example.test/sw.js"},
            {"type": "page", "url": "https://example.test/other", "title": "Other"},
        ]
    ) == {"type": "page", "url": "https://example.test/other", "title": "Other"}


def test_build_live_cam_runtime_url_entry_returns_error_payload() -> None:
    assert build_live_cam_runtime_url_entry(
        port=9996,
        targets_or_error=OSError("connection refused"),
    ) == {"port": 9996, "error": "connection refused"}


def test_collect_live_cam_runtime_urls_converts_targets_and_errors() -> None:
    specs = [{"port": 9993}, {"port": 9994}]

    def fetch_targets(port: int) -> object:
        if port == 9993:
            return [{"type": "page", "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}]
        raise OSError("connection refused")

    assert collect_live_cam_runtime_urls(specs, fetch_targets=fetch_targets) == [
        {"port": 9993, "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
        {"port": 9994, "error": "connection refused"},
    ]


def test_collect_live_cam_pages_by_port_converts_page_briefs_and_errors() -> None:
    specs = [{"port": 9993}, {"port": 9994}]

    def fetch_page_brief(port: int) -> object:
        if port == 9993:
            return {"url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}
        raise OSError("connection refused")

    pages_by_port = collect_live_cam_pages_by_port(specs, fetch_page_brief=fetch_page_brief)

    assert pages_by_port[9993] == {"url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}
    assert isinstance(pages_by_port[9994], OSError)
    assert str(pages_by_port[9994]) == "connection refused"


def test_collect_live_cam_runtime_state_combines_windows_and_urls() -> None:
    specs = [{"port": 9993}, {"port": 9994}]
    rows = [{"id": "0x1", "pid": 101}]

    def fetch_targets(port: int) -> object:
        if port == 9993:
            return [{"type": "page", "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}]
        raise OSError("connection refused")

    assert collect_live_cam_runtime_state(
        specs,
        rows=rows,
        fetch_targets=fetch_targets,
    ) == {
        "windows": [{"id": "0x1", "pid": 101}],
        "urls": [
            {"port": 9993, "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
            {"port": 9994, "error": "connection refused"},
        ],
    }


def test_run_live_cam_runtime_state_cdp_runtime_validates_target_lists() -> None:
    specs = [{"port": 9993}, {"port": 9994}]
    rows = [{"id": "0x1", "pid": 101}]

    out = run_live_cam_runtime_state_cdp_runtime(
        specs,
        rows=rows,
        fetch_targets=lambda port: (
            [{"type": "page", "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}]
            if port == 9993
            else {"unexpected": True}
        ),
        validate_target_list=lambda payload, message: (
            payload if isinstance(payload, list) else (_ for _ in ()).throw(RuntimeError(message))
        ),
    )

    assert out == {
        "windows": [{"id": "0x1", "pid": 101}],
        "urls": [
            {"port": 9993, "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
            {"port": 9994, "error": "unexpected CDP target list on port 9994"},
        ],
    }


def test_run_live_cam_runtime_state_http_query_uses_http_target_query() -> None:
    calls: list[tuple[str, float]] = []
    specs = [{"port": 9993}, {"port": 9994}]

    def fetch_json(url: str, timeout: float) -> object:
        calls.append((url, float(timeout)))
        if url.endswith(":9993/json"):
            return [{"type": "page", "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}]
        raise OSError("connection refused")

    out = run_live_cam_runtime_state_http_query(
        specs,
        rows=[{"id": "0x1", "pid": 101}],
        fetch_json=fetch_json,
    )

    assert out == {
        "windows": [{"id": "0x1", "pid": 101}],
        "urls": [
            {"port": 9993, "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
            {"port": 9994, "error": "connection refused"},
        ],
    }
    assert calls == [
        ("http://127.0.0.1:9993/json", 2.0),
        ("http://127.0.0.1:9994/json", 2.0),
    ]


def test_run_live_cam_runtime_state_host_runtime_query_reads_runtime_methods() -> None:
    class FakeRuntime:
        instances = [{"port": 9993}, {"port": 9994}]

        def _window_rows_by_pids(self, pids: list[int]) -> list[dict[str, int | str]]:
            assert pids == [101, 102]
            return [{"id": "0x1", "pid": 101}]

    fetch_calls: list[tuple[str, float]] = []

    out = run_live_cam_runtime_state_host_runtime_query(
        runtime=FakeRuntime(),
        pids_by_port={9993: 101, 9994: 102},
        fetch_json=lambda url, timeout: (
            fetch_calls.append((url, float(timeout)))
            or (
                [{"type": "page", "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"}]
                if url.endswith(":9993/json")
                else (_ for _ in ()).throw(OSError("connection refused"))
            )
        ),
    )

    assert out == {
        "windows": [{"id": "0x1", "pid": 101}],
        "urls": [
            {"port": 9993, "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
            {"port": 9994, "error": "connection refused"},
        ],
    }
    assert fetch_calls == [
        ("http://127.0.0.1:9993/json", 2.0),
        ("http://127.0.0.1:9994/json", 2.0),
    ]


def test_build_live_cam_page_brief_extracts_title_and_url() -> None:
    assert build_live_cam_page_brief(
        {
            "type": "page",
            "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
            "title": "Shibuya",
        }
    ) == {
        "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "title": "Shibuya",
    }


def test_merge_live_cam_page_snapshot_overlays_string_fields() -> None:
    assert merge_live_cam_page_snapshot(
        {"url": "https://www.youtube.com/tv#/watch?v=abc123DEF45", "title": "Before"},
        snapshot={
            "title": "After",
            "hash": "#/watch?v=abc123DEF45",
            "bodyText": "渋谷スクランブル交差点のライブ映像",
            "watchText": "【LIVE】いまの渋谷",
        },
    ) == {
        "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "title": "After",
        "hash": "#/watch?v=abc123DEF45",
        "bodyText": "渋谷スクランブル交差点のライブ映像",
        "watchText": "【LIVE】いまの渋谷",
    }


def test_merge_live_cam_page_snapshot_keeps_brief_and_records_inspect_error() -> None:
    assert merge_live_cam_page_snapshot(
        {"url": "https://www.youtube.com/tv#/watch?v=abc123DEF45", "title": "Shibuya"},
        inspect_error=RuntimeError("cdp failed"),
    ) == {
        "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "title": "Shibuya",
        "inspectError": "cdp failed",
    }


def test_run_live_cam_page_snapshot_query_returns_dict_payload() -> None:
    out = run_live_cam_page_snapshot_query(
        evaluate=lambda expr: {
            "title": "Shibuya",
            "watchText": "watch:Shibuya",
            "expr_seen": "ytlr-watch-metadata" in expr,
        }
    )

    assert out == {
        "title": "Shibuya",
        "watchText": "watch:Shibuya",
        "expr_seen": True,
    }


def test_run_live_cam_page_snapshot_query_returns_empty_dict_for_non_dict_payload() -> None:
    out = run_live_cam_page_snapshot_query(evaluate=lambda _expr: ["not", "dict"])

    assert out == {}


def test_run_live_cam_page_snapshot_via_websocket_opens_client_and_queries_snapshot() -> None:
    events: list[str] = []

    out = run_live_cam_page_snapshot_via_websocket(
        ws_url="ws://127.0.0.1:9993/devtools/page/1",
        create_client=lambda ws_url: {"ws_url": ws_url},
        enable_client=lambda client: events.append(f"enable:{client['ws_url']}"),
        query_snapshot=lambda client: {"watchText": client["ws_url"]},
    )

    assert out == {"watchText": "ws://127.0.0.1:9993/devtools/page/1"}
    assert events == ["enable:ws://127.0.0.1:9993/devtools/page/1"]


def test_page_matches_live_camera_spec_accepts_matching_watch_page() -> None:
    spec = {"verify_regex": "渋谷|Shibuya"}
    page = {
        "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "watchText": "【LIVE】いまの渋谷 Shibuya Scramble Crossing",
        "bodyText": "渋谷スクランブル交差点のライブ映像",
    }

    assert page_matches_live_camera_spec(spec, page) is True


def test_page_matches_live_camera_spec_rejects_mismatched_watch_page() -> None:
    spec = {"verify_regex": "渋谷|Shibuya"}
    page = {
        "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "watchText": "最新ニュース 日テレNEWS LIVE",
        "bodyText": "速報とニュース解説をお届けします",
    }

    assert page_matches_live_camera_spec(spec, page) is False


def test_page_matches_live_camera_spec_accepts_fallback_pattern() -> None:
    spec = {
        "verify_regex": "新宿駅前|新宿|Shinjuku",
        "fallbacks": [
            {"verify_regex": "浅草|雷門|Asakusa"},
        ],
    }
    page = {
        "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "watchText": "【LIVE】浅草・雷門前の様子 Asakusa, Tokyo JAPAN 【ライブカメラ】",
        "bodyText": "浅草 雷門 前 の ライブカメラ",
    }

    assert page_matches_live_camera_spec(spec, page) is True


def test_page_matches_live_camera_spec_rejects_archived_minowa_video() -> None:
    spec = {"verify_regex": "大関横丁|東京都台東区"}
    page = {
        "url": "https://www.youtube.com/tv/@channel/streams#/watch?v=MZEvlESu6I0",
        "watchText": (
            "【閲覧注意】令和６年10月21日(月)午後11時39分頃 "
            "交通事故 衝突事故 | 三ノ輪駅前ライブカメラ"
        ),
        "bodyText": "2:20:01 交通事故 衝突事故 三ノ輪駅前ライブカメラ 4052回視聴 1 年前",
    }

    assert page_matches_live_camera_spec(spec, page) is False


def test_find_stuck_live_cam_specs_marks_http_error_and_mismatched_watch_pages() -> None:
    specs = [
        {"label": "shibuya", "port": 9993, "verify_regex": "渋谷|Shibuya"},
        {"label": "akihabara", "port": 9996, "verify_regex": "秋葉原|Akihabara"},
    ]

    pages_by_port = {
        9993: {
            "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
            "watchText": "最新ニュース 日テレNEWS LIVE",
            "bodyText": "速報とニュース解説をお届けします",
        },
        9996: OSError("connection refused"),
    }

    stuck = find_stuck_live_cam_specs(specs, pages_by_port=pages_by_port)

    assert stuck == specs


def test_find_stuck_live_cam_specs_skips_matching_watch_pages() -> None:
    specs = [
        {"label": "shibuya", "port": 9993, "verify_regex": "渋谷|Shibuya"},
        {"label": "akihabara", "port": 9996, "verify_regex": "秋葉原|Akihabara"},
    ]

    pages_by_port = {
        9993: {
            "url": "https://www.youtube.com/tv#/watch?v=abc123",
            "watchText": "【LIVE】いまの渋谷 Shibuya",
            "bodyText": "渋谷スクランブル交差点のライブ映像",
        },
        9996: {
            "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
            "watchText": "【LIVE】秋葉原 Akihabara",
            "bodyText": "秋葉原 ライブカメラ",
        },
    }

    stuck = find_stuck_live_cam_specs(specs, pages_by_port=pages_by_port)

    assert stuck == []


def test_run_live_cam_stuck_specs_query_collects_pages_and_returns_stuck_specs() -> None:
    specs = [
        {"label": "shibuya", "port": 9993, "verify_regex": "渋谷|Shibuya"},
        {"label": "akihabara", "port": 9996, "verify_regex": "秋葉原|Akihabara"},
    ]
    calls: list[int] = []

    out = run_live_cam_stuck_specs_query(
        specs,
        fetch_page_brief=lambda port: (
            calls.append(port)
            or (
                {
                    "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
                    "watchText": "最新ニュース 日テレNEWS LIVE",
                    "bodyText": "速報とニュース解説をお届けします",
                }
                if port == 9993
                else {
                    "url": "https://www.youtube.com/tv#/watch?v=abc123DEF46",
                    "watchText": "【LIVE】秋葉原 Akihabara",
                    "bodyText": "秋葉原 ライブカメラ",
                }
            )
        ),
    )

    assert calls == [9993, 9996]
    assert out == [specs[0]]


def test_run_live_cam_stuck_specs_host_runtime_query_reads_runtime_methods() -> None:
    class FakeRuntime:
        instances = [
            {"label": "shibuya", "port": 9993, "verify_regex": "渋谷|Shibuya"},
            {"label": "akihabara", "port": 9996, "verify_regex": "秋葉原|Akihabara"},
        ]

        def _page_brief_for_port(self, port: int) -> dict[str, str]:
            if port == 9993:
                return {
                    "url": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
                    "watchText": "最新ニュース 日テレNEWS LIVE",
                    "bodyText": "速報とニュース解説をお届けします",
                }
            return {
                "url": "https://www.youtube.com/tv#/watch?v=abc123DEF46",
                "watchText": "【LIVE】秋葉原 Akihabara",
                "bodyText": "秋葉原 ライブカメラ",
            }

    out = run_live_cam_stuck_specs_host_runtime_query(runtime=FakeRuntime())

    assert out == [FakeRuntime.instances[0]]


def test_run_live_cam_page_brief_flow_merges_snapshot_from_inspector() -> None:
    out = run_live_cam_page_brief_flow(
        port=9993,
        fetch_targets=lambda port: [
            {
                "type": "page",
                "url": f"https://www.youtube.com/tv#/watch?v=abc{port}",
                "title": "Shibuya",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1",
            }
        ],
        validate_target_list=lambda data, _message: data,
        select_target=select_live_cam_page_target,
        build_brief=build_live_cam_page_brief,
        inspect_target=lambda target: {"watchText": f"watch:{target['title']}"},
        merge_snapshot=merge_live_cam_page_snapshot,
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9993",
        "title": "Shibuya",
        "watchText": "watch:Shibuya",
    }


def test_run_live_cam_page_brief_flow_records_inspect_error() -> None:
    out = run_live_cam_page_brief_flow(
        port=9994,
        fetch_targets=lambda _port: [
            {
                "type": "page",
                "url": "https://www.youtube.com/tv#/watch?v=abc9994",
                "title": "Akihabara",
            }
        ],
        validate_target_list=None,
        select_target=select_live_cam_page_target,
        build_brief=build_live_cam_page_brief,
        inspect_target=lambda _target: (_ for _ in ()).throw(RuntimeError("cdp failed")),
        merge_snapshot=merge_live_cam_page_snapshot,
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9994",
        "title": "Akihabara",
        "inspectError": "cdp failed",
    }


def test_run_live_cam_page_brief_cdp_runtime_uses_cdp_snapshot_runtime() -> None:
    events: list[object] = []

    class FakeClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            events.append(("enable", self.ws_url))

    out = run_live_cam_page_brief_cdp_runtime(
        port=9993,
        fetch_targets=lambda port: [
            {
                "type": "page",
                "url": f"https://www.youtube.com/tv#/watch?v=abc{port}",
                "title": "Shibuya",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1",
            }
        ],
        validate_target_list=None,
        select_target=select_live_cam_page_target,
        build_brief=build_live_cam_page_brief,
        create_client=lambda ws_url: FakeClient(ws_url),
        query_snapshot=lambda client: {
            "watchText": f"watch:{client.ws_url}",
        },
        merge_snapshot=merge_live_cam_page_snapshot,
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9993",
        "title": "Shibuya",
        "watchText": "watch:ws://127.0.0.1:9993/devtools/page/1",
    }
    assert events == [("enable", "ws://127.0.0.1:9993/devtools/page/1")]


def test_run_live_cam_page_brief_cdp_runtime_defaults_snapshot_query_to_evaluate() -> None:
    events: list[object] = []

    class FakeClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            events.append(("enable", self.ws_url))

        def evaluate(self, expr: str) -> dict[str, str]:
            events.append(("evaluate", "ytlr-watch-metadata" in expr))
            return {"watchText": f"watch:{self.ws_url}"}

    out = run_live_cam_page_brief_cdp_runtime(
        port=9993,
        fetch_targets=lambda port: [
            {
                "type": "page",
                "url": f"https://www.youtube.com/tv#/watch?v=abc{port}",
                "title": "Shibuya",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1",
            }
        ],
        validate_target_list=None,
        select_target=select_live_cam_page_target,
        build_brief=build_live_cam_page_brief,
        create_client=lambda ws_url: FakeClient(ws_url),
        merge_snapshot=merge_live_cam_page_snapshot,
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9993",
        "title": "Shibuya",
        "watchText": "watch:ws://127.0.0.1:9993/devtools/page/1",
    }
    assert events == [
        ("enable", "ws://127.0.0.1:9993/devtools/page/1"),
        ("evaluate", True),
    ]


def test_run_live_cam_page_brief_http_query_uses_http_target_query_and_client_factory() -> None:
    events: list[object] = []

    class FakeClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            events.append(("enable", self.ws_url))

        def evaluate(self, expr: str) -> dict[str, str]:
            events.append(("evaluate", "ytlr-watch-metadata" in expr))
            return {"watchText": f"watch:{self.ws_url}"}

    fetch_calls: list[tuple[str, float]] = []

    out = run_live_cam_page_brief_http_query(
        port=9993,
        fetch_json=lambda url, timeout: (
            fetch_calls.append((url, float(timeout)))
            or [
                {
                    "type": "page",
                    "url": "https://www.youtube.com/tv#/watch?v=abc9993",
                    "title": "Shibuya",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1",
                }
            ]
        ),
        create_client=lambda ws_url: FakeClient(ws_url),
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9993",
        "title": "Shibuya",
        "watchText": "watch:ws://127.0.0.1:9993/devtools/page/1",
    }
    assert fetch_calls == [("http://127.0.0.1:9993/json", 2.0)]
    assert events == [
        ("enable", "ws://127.0.0.1:9993/devtools/page/1"),
        ("evaluate", True),
    ]


def test_run_live_cam_page_brief_host_runtime_flow_reads_runtime_methods() -> None:
    class FakeRuntime:
        pass

    fetch_calls: list[tuple[str, float]] = []
    client_calls: list[tuple[str, float]] = []

    class FakeClient:
        def __init__(self, ws_url: str, *, timeout_sec: float) -> None:
            client_calls.append((ws_url, float(timeout_sec)))
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            pass

        def evaluate(self, _expr: str) -> dict[str, str]:
            return {"watchText": f"watch:{self.ws_url}"}

    out = run_live_cam_page_brief_host_runtime_flow(
        runtime=FakeRuntime(),
        port=9993,
        fetch_json=lambda url, timeout: (
            fetch_calls.append((url, float(timeout)))
            or [
                {
                    "type": "page",
                    "url": "https://www.youtube.com/tv#/watch?v=abc9993",
                    "title": "Shibuya",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1",
                }
            ]
        ),
        client_factory=FakeClient,
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9993",
        "title": "Shibuya",
        "watchText": "watch:ws://127.0.0.1:9993/devtools/page/1",
    }
    assert fetch_calls == [("http://127.0.0.1:9993/json", 2.0)]
    assert client_calls == [("ws://127.0.0.1:9993/devtools/page/1", 4.0)]


def test_run_live_cam_page_brief_runtime_flow_builds_client_with_timeouts() -> None:
    events: list[object] = []

    class FakeClient:
        def __init__(self, ws_url: str, *, timeout_sec: float) -> None:
            events.append(("create", ws_url, timeout_sec))
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            events.append(("enable", self.ws_url))

        def evaluate(self, expr: str) -> dict[str, str]:
            events.append(("evaluate", "ytlr-watch-metadata" in expr))
            return {"watchText": f"watch:{self.ws_url}"}

    fetch_calls: list[tuple[str, float]] = []

    out = run_live_cam_page_brief_runtime_flow(
        port=9993,
        fetch_json=lambda url, timeout: (
            fetch_calls.append((url, float(timeout)))
            or [
                {
                    "type": "page",
                    "url": "https://www.youtube.com/tv#/watch?v=abc9993",
                    "title": "Shibuya",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1",
                }
            ]
        ),
        client_factory=FakeClient,
        http_timeout=1.5,
        client_timeout=4.5,
    )

    assert out == {
        "url": "https://www.youtube.com/tv#/watch?v=abc9993",
        "title": "Shibuya",
        "watchText": "watch:ws://127.0.0.1:9993/devtools/page/1",
    }
    assert fetch_calls == [("http://127.0.0.1:9993/json", 1.5)]
    assert events == [
        ("create", "ws://127.0.0.1:9993/devtools/page/1", 4.5),
        ("enable", "ws://127.0.0.1:9993/devtools/page/1"),
        ("evaluate", True),
    ]


def test_run_live_cam_target_inspection_uses_websocket_url() -> None:
    out = run_live_cam_target_inspection(
        target={"webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1"},
        inspect_websocket=lambda ws_url: {"watchText": ws_url},
    )

    assert out == {"watchText": "ws://127.0.0.1:9993/devtools/page/1"}


def test_run_live_cam_target_inspection_returns_none_without_websocket_url() -> None:
    out = run_live_cam_target_inspection(
        target={"title": "no websocket"},
        inspect_websocket=lambda _ws_url: {"watchText": "unused"},
    )

    assert out is None


def test_run_live_cam_target_snapshot_runtime_chains_websocket_snapshot() -> None:
    events: list[str] = []

    out = run_live_cam_target_snapshot_runtime(
        target={"webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1"},
        create_client=lambda ws_url: {"ws_url": ws_url},
        enable_client=lambda client: events.append(f"enable:{client['ws_url']}"),
        query_snapshot=lambda client: {"watchText": client["ws_url"]},
    )

    assert out == {"watchText": "ws://127.0.0.1:9993/devtools/page/1"}
    assert events == ["enable:ws://127.0.0.1:9993/devtools/page/1"]


def test_run_live_cam_target_snapshot_cdp_runtime_enables_basics() -> None:
    events: list[object] = []

    class FakeClient:
        def __init__(self, ws_url: str) -> None:
            events.append(("create", ws_url))
            self.ws_url = ws_url

        def enable_basics(self) -> None:
            events.append(("enable", self.ws_url))

    out = run_live_cam_target_snapshot_cdp_runtime(
        target={"webSocketDebuggerUrl": "ws://127.0.0.1:9993/devtools/page/1"},
        create_client=FakeClient,
        query_snapshot=lambda client: {"watchText": client.ws_url},
    )

    assert out == {"watchText": "ws://127.0.0.1:9993/devtools/page/1"}
    assert events == [
        ("create", "ws://127.0.0.1:9993/devtools/page/1"),
        ("enable", "ws://127.0.0.1:9993/devtools/page/1"),
    ]
