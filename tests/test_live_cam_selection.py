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
    select_live_cam_payload,
    web_watch_retry_video_id,
)

FAST_OPEN_SCRIPT = Path("/tmp/open_tv_channel_live_tile_fast.js")


def _build_force_command(candidate: dict[str, object], force_video_id: str) -> list[str]:
    return build_live_cam_force_video_command(
        FAST_OPEN_SCRIPT,
        candidate,
        force_video_id=force_video_id,
    )


def _build_browse_command(candidate: dict[str, object]) -> list[str]:
    return build_live_cam_browse_command(
        FAST_OPEN_SCRIPT,
        candidate,
    )


def _build_parse_failure(
    candidate: dict[str, object],
    returncode: int,
    error: str,
) -> dict[str, object]:
    return build_live_cam_json_parse_failure(
        candidate,
        returncode=returncode,
        error=error,
    )


def _build_force_retry(
    candidate: dict[str, object],
    video_id: str,
) -> dict[str, object]:
    return build_live_cam_force_retry_failure(
        candidate,
        video_id=video_id,
    )


def _build_command_failure(
    candidate: dict[str, object],
    returncode: int,
    payload: dict[str, object] | None,
    stderr: str,
) -> dict[str, object]:
    return build_live_cam_command_failure(
        candidate,
        returncode=returncode,
        payload=payload,
        stderr=stderr,
    )


def _selection_kwargs(
    *,
    run_command,
    verify_force_candidate_page,
    log=None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "expand_candidates": expand_live_cam_candidates,
        "normalize_force_video_id": normalize_live_cam_force_video_id,
        "build_force_video_command": _build_force_command,
        "build_browse_command": _build_browse_command,
        "build_json_parse_failure": _build_parse_failure,
        "build_force_retry_failure": _build_force_retry,
        "build_command_failure": _build_command_failure,
        "web_watch_retry_video_id": web_watch_retry_video_id,
        "annotate_payload_selection": annotate_live_cam_payload_selection,
        "format_selection_error": format_live_cam_selection_error,
        "run_command": run_command,
        "verify_force_candidate_page": verify_force_candidate_page,
    }
    if log is not None:
        kwargs["log"] = log
    return kwargs


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
        FAST_OPEN_SCRIPT,
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
        FAST_OPEN_SCRIPT,
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


def test_select_live_cam_payload_falls_back_to_alternate_candidate() -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], timeout: float) -> tuple[int, str, str]:
        calls.append(command)
        if len(calls) == 1:
            return 1, '{"ok":false}', "no-match"
        return 0, '{"ok":true,"videoId":"abc123DEF45","method":"direct-id"}', ""

    payload = select_live_cam_payload(
        {
            "port": 9994,
            "browse_url": "https://example.test/browse",
            "keyword": "新宿駅前のライブカメラ",
            "verify_regex": "新宿駅前|新宿|Shinjuku",
            "fallbacks": [
                {
                    "keyword": "浅草・雷門前の様子",
                    "verify_regex": "浅草|雷門|Asakusa",
                    "browse_url": "https://example.test/asakusa",
                }
            ],
        },
        **_selection_kwargs(
            run_command=fake_run,
            verify_force_candidate_page=lambda _candidate: True,
        ),
    )

    assert payload["videoId"] == "abc123DEF45"
    assert len(calls) == 2
    assert "新宿駅前のライブカメラ" in calls[0]
    assert "浅草・雷門前の様子" in calls[1]


def test_select_live_cam_payload_retries_web_watch_as_force_video_id() -> None:
    calls: list[list[str]] = []
    logs: list[str] = []

    def fake_run(command: list[str], timeout: float) -> tuple[int, str, str]:
        calls.append(command)
        if "--force-video-id" in command:
            return 0, '{"ok":true,"videoId":"TBSVID12345","method":"force-video-id"}', ""
        return (
            0,
            '{"ok":true,"method":"web-streams-fallback-web-watch","videoId":"TBSVID12345","finalHref":"https://www.youtube.com/watch?v=TBSVID12345"}',
            "",
        )

    payload = select_live_cam_payload(
        {
            "label": "shinjuku",
            "port": 9994,
            "browse_url": "https://example.test/shinjuku",
            "keyword": "新宿駅前のライブカメラ",
            "verify_regex": "新宿駅前|新宿|Shinjuku",
        },
        **_selection_kwargs(
            run_command=fake_run,
            verify_force_candidate_page=lambda _candidate: True,
            log=logs.append,
        ),
    )

    assert payload["videoId"] == "TBSVID12345"
    assert payload["method"] == "force-video-id"
    assert len(calls) == 2
    assert any("--force-video-id" in command for command in calls)
    assert any("retrying as TV URL via --force-video-id TBSVID12345" in entry for entry in logs)


def test_select_live_cam_payload_retries_browse_when_force_video_id_verification_fails() -> None:
    calls: list[list[str]] = []
    verify_calls: list[dict[str, object]] = []

    def fake_run(command: list[str], timeout: float) -> tuple[int, str, str]:
        calls.append(command)
        if "--force-video-id" in command:
            return 0, '{"ok":true,"videoId":"urE7veQRlrQ","method":"force-video-id"}', ""
        return 0, '{"ok":true,"videoId":"abc123DEF45","method":"direct-id"}', ""

    payload = select_live_cam_payload(
        {
            "label": "asakusa",
            "port": 9996,
            "force_video_id": "urE7veQRlrQ",
            "browse_url": "https://example.test/asakusa",
            "keyword": "浅草・雷門前の様子",
            "verify_regex": "浅草|雷門|Asakusa",
        },
        **_selection_kwargs(
            run_command=fake_run,
            verify_force_candidate_page=lambda candidate: verify_calls.append(candidate)
            or False,
        ),
    )

    assert payload["videoId"] == "abc123DEF45"
    assert payload["method"] == "direct-id"
    assert len(calls) == 2
    assert len(verify_calls) == 1
