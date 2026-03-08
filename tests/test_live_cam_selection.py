from __future__ import annotations

from pathlib import Path

from arouter import (
    annotate_live_cam_payload_selection,
    build_live_cam_browse_command,
    build_live_cam_command_failure,
    build_live_cam_force_retry_failure,
    build_live_cam_force_video_command,
    build_live_cam_json_parse_failure,
    expand_live_cam_candidates,
    format_live_cam_selection_error,
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


def test_build_live_cam_force_video_command_returns_expected_args() -> None:
    command = build_live_cam_force_video_command(
        Path("/tmp/open_tv_channel_live_tile_fast.js"),
        {"port": 9996, "keyword": "浅草・雷門前の様子"},
        force_video_id="urE7veQRlrQ",
    )

    assert command == [
        "node",
        "/tmp/open_tv_channel_live_tile_fast.js",
        "--cdp-port",
        "9996",
        "--force-video-id",
        "urE7veQRlrQ",
        "--keyword",
        "浅草・雷門前の様子",
    ]


def test_build_live_cam_browse_command_returns_expected_args() -> None:
    command = build_live_cam_browse_command(
        Path("/tmp/open_tv_channel_live_tile_fast.js"),
        {
            "port": 9994,
            "browse_url": "https://example.test/shinjuku",
            "keyword": "新宿駅前のライブカメラ",
            "verify_regex": "新宿駅前|新宿|Shinjuku",
        },
    )

    assert command == [
        "node",
        "/tmp/open_tv_channel_live_tile_fast.js",
        "--cdp-port",
        "9994",
        "--browse-url",
        "https://example.test/shinjuku",
        "--keyword",
        "新宿駅前のライブカメラ",
        "--verify-regex",
        "新宿駅前|新宿|Shinjuku",
    ]


def test_build_live_cam_failure_helpers_return_expected_payloads() -> None:
    candidate = {"keyword": "浅草・雷門前の様子"}

    assert build_live_cam_json_parse_failure(
        candidate,
        returncode=1,
        error="Expecting value",
    ) == {
        "keyword": "浅草・雷門前の様子",
        "returncode": 1,
        "error": "json-parse: Expecting value",
    }
    assert build_live_cam_force_retry_failure(
        candidate,
        video_id="TBSVID12345",
    ) == {
        "keyword": "浅草・雷門前の様子",
        "reason": "web-watch-rejected-force-failed",
        "videoId": "TBSVID12345",
    }
    assert build_live_cam_command_failure(
        candidate,
        returncode=2,
        payload={"ok": False},
        stderr=" no-match ",
    ) == {
        "keyword": "浅草・雷門前の様子",
        "returncode": 2,
        "payload": {"ok": False},
        "stderr": "no-match",
    }


def test_format_live_cam_selection_error_serializes_failures() -> None:
    message = format_live_cam_selection_error(
        9994,
        [{"keyword": "新宿駅前のライブカメラ", "returncode": 1}],
    )

    assert message == (
        'live camera select failed on port 9994: '
        '[{"keyword": "新宿駅前のライブカメラ", "returncode": 1}]'
    )
