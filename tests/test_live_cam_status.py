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
