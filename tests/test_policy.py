from __future__ import annotations

import json
from unittest import mock

from arouter import (
    VoiceCommand,
    good_night_voice_text,
    post_action_voice_text,
    should_ack_before_action,
    should_wait_ack_before_action,
    suppress_transcribed_command_reason,
)


def test_should_wait_ack_before_action_for_presentation_commands() -> None:
    assert should_wait_ack_before_action(
        VoiceCommand(intent="youtube_fullscreen", normalized_text="", raw_text="")
    )
    assert should_wait_ack_before_action(
        VoiceCommand(intent="system_world_situation_mode", normalized_text="", raw_text="")
    )
    assert not should_wait_ack_before_action(
        VoiceCommand(intent="system_status_report", normalized_text="", raw_text="")
    )


def test_should_ack_before_action_excludes_good_night_and_biometric_auth() -> None:
    assert not should_ack_before_action(
        VoiceCommand(intent="good_night", normalized_text="おやすみ", raw_text="おやすみ")
    )
    assert not should_ack_before_action(
        VoiceCommand(
            intent="system_biometric_auth",
            normalized_text="バイオメトリクス認証",
            raw_text="バイオメトリクス認証",
        )
    )
    assert should_ack_before_action(
        VoiceCommand(intent="system_status_report", normalized_text="", raw_text="")
    )


def test_suppress_transcribed_command_reason_for_too_short_fullscreen() -> None:
    reason = suppress_transcribed_command_reason(
        VoiceCommand(intent="youtube_fullscreen", normalized_text="", raw_text=""),
        dur_sec=0.6,
        fullscreenish=False,
    )

    assert reason == "segment too short for youtube_fullscreen (0.60s)"


def test_suppress_transcribed_command_reason_for_short_repeat_when_already_fullscreen() -> None:
    reason = suppress_transcribed_command_reason(
        VoiceCommand(intent="youtube_fullscreen", normalized_text="", raw_text=""),
        dur_sec=1.4,
        fullscreenish=True,
    )

    assert reason == "short repeated youtube_fullscreen while already fullscreen"


def test_suppress_transcribed_command_reason_allows_longer_fullscreen_segment() -> None:
    reason = suppress_transcribed_command_reason(
        VoiceCommand(intent="youtube_fullscreen", normalized_text="", raw_text=""),
        dur_sec=1.9,
        fullscreenish=True,
    )

    assert reason is None


def test_good_night_voice_text_handles_success_result() -> None:
    text = good_night_voice_text(
        "good_night pause " + json.dumps({"ok": True, "afterPaused": True}, ensure_ascii=False)
    )

    assert "おやすみ" in text
    assert "停止いたしました" in text


def test_good_night_voice_text_handles_no_window_result() -> None:
    text = good_night_voice_text("good_night pause no VacuumTube window (no-op)")

    assert text == "おやすみなさいませ。YouTubeは停止済みのようです。どうぞ良い夢を。"


def test_good_night_voice_text_handles_video_not_found_result() -> None:
    text = good_night_voice_text("good_night pause " + json.dumps({"reason": "video-not-found"}))

    assert text == (
        "おやすみなさいませ。YouTubeの停止対象は見つかりませんでしたが、どうぞ良い夢を。"
    )


def test_post_action_voice_text_uses_biometric_text_provider() -> None:
    provider = mock.Mock(
        return_value="バイオメトリクス認証に成功しました。おかえりなさい、ユイさま"
    )

    text = post_action_voice_text(
        VoiceCommand(
            intent="system_biometric_auth",
            normalized_text="バイオメトリクス認証",
            raw_text="バイオメトリクス認証",
        ),
        "unused",
        biometric_unlock_success_text_provider=provider,
    )

    assert text == "バイオメトリクス認証に成功しました。おかえりなさい、ユイさま"
    provider.assert_called_once_with()


def test_post_action_voice_text_passes_through_weather_result() -> None:
    text = post_action_voice_text(
        VoiceCommand(
            intent="system_weather_today",
            normalized_text="今日の天気",
            raw_text="今日の天気",
        ),
        "晴れ時々くもりです",
    )

    assert text == "晴れ時々くもりです"


def test_post_action_voice_text_returns_none_for_other_intents_without_calling_provider() -> None:
    provider = mock.Mock(return_value="unused")

    text = post_action_voice_text(
        VoiceCommand(intent="music_play", normalized_text="音楽", raw_text="音楽"),
        "unused",
        biometric_unlock_success_text_provider=provider,
    )

    assert text is None
    provider.assert_not_called()
