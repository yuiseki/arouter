from __future__ import annotations

from arouter import (
    find_stuck_live_cam_specs,
    page_matches_live_camera_spec,
)


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
