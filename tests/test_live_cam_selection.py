from __future__ import annotations

from arouter import (
    annotate_live_cam_payload_selection,
    expand_live_cam_candidates,
    normalize_live_cam_force_video_id,
    web_watch_retry_video_id,
)


def test_expand_live_cam_candidates_keeps_primary_then_merged_fallbacks() -> None:
    candidates = expand_live_cam_candidates(
        {
            "port": 9996,
            "browse_url": "https://example.test/minowa",
            "keyword": "三ノ輪駅前ライブカメラ",
            "verify_regex": "三ノ輪|Minowa",
            "fallbacks": [
                {
                    "browse_url": "https://example.test/asakusa",
                    "force_video_id": "urE7veQRlrQ",
                    "keyword": "浅草・雷門前の様子",
                    "verify_regex": "浅草|雷門|Asakusa",
                },
            ],
        }
    )

    assert candidates == [
        {
            "port": 9996,
            "browse_url": "https://example.test/minowa",
            "keyword": "三ノ輪駅前ライブカメラ",
            "verify_regex": "三ノ輪|Minowa",
            "fallbacks": [
                {
                    "browse_url": "https://example.test/asakusa",
                    "force_video_id": "urE7veQRlrQ",
                    "keyword": "浅草・雷門前の様子",
                    "verify_regex": "浅草|雷門|Asakusa",
                },
            ],
        },
        {
            "port": 9996,
            "browse_url": "https://example.test/asakusa",
            "keyword": "浅草・雷門前の様子",
            "verify_regex": "浅草|雷門|Asakusa",
            "force_video_id": "urE7veQRlrQ",
        },
    ]


def test_normalize_live_cam_force_video_id_accepts_only_valid_ids() -> None:
    assert normalize_live_cam_force_video_id({"force_video_id": "urE7veQRlrQ"}) == "urE7veQRlrQ"
    assert normalize_live_cam_force_video_id({"force_video_id": "BADFORCE1234"}) == ""
    assert normalize_live_cam_force_video_id({"force_video_id": "short"}) == ""


def test_web_watch_retry_video_id_returns_video_id_only_for_retriable_payload() -> None:
    assert (
        web_watch_retry_video_id(
            {"method": "web-streams-fallback-web-watch", "videoId": "TBSVID12345"}
        )
        == "TBSVID12345"
    )
    assert web_watch_retry_video_id({"method": "direct-id", "videoId": "TBSVID12345"}) == ""
    assert (
        web_watch_retry_video_id(
            {"method": "web-streams-fallback-web-watch", "videoId": "BADID1234567"}
        )
        == ""
    )


def test_annotate_live_cam_payload_selection_sets_default_metadata() -> None:
    payload = annotate_live_cam_payload_selection(
        {"ok": True},
        {"keyword": "浅草・雷門前の様子", "verify_regex": "浅草|雷門|Asakusa"},
    )

    assert payload["selectedKeyword"] == "浅草・雷門前の様子"
    assert payload["selectedVerifyRegex"] == "浅草|雷門|Asakusa"
