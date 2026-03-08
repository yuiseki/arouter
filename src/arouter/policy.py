from __future__ import annotations

from collections.abc import Callable

from .models import VoiceCommand

_WAIT_ACK_INTENTS = frozenset(
    {
        "youtube_fullscreen",
        "youtube_quadrant",
        "youtube_minimize",
        "weather_pages_today",
        "system_live_camera_show",
        "system_live_camera_compact",
        "system_live_camera_hide",
        "system_street_camera_mode",
        "system_webcam_mode",
        "system_normal_mode",
        "system_world_situation_mode",
        "system_weather_mode",
        "system_lock_mode",
        "system_load_check",
        "god_mode_show",
        "god_mode_fullscreen",
        "god_mode_compact",
        "god_mode_background",
    }
)

_NO_PRE_ACK_INTENTS = frozenset(
    {
        "good_night",
        "system_weather_today",
        "system_biometric_auth",
    }
)


def should_wait_ack_before_action(cmd: VoiceCommand) -> bool:
    return cmd.intent in _WAIT_ACK_INTENTS


def should_ack_before_action(cmd: VoiceCommand) -> bool:
    return cmd.intent not in _NO_PRE_ACK_INTENTS


def suppress_transcribed_command_reason(
    cmd: VoiceCommand,
    *,
    dur_sec: float,
    fullscreenish: bool,
) -> str | None:
    if cmd.intent != "youtube_fullscreen":
        return None
    if dur_sec < 1.2:
        return f"segment too short for youtube_fullscreen ({dur_sec:.2f}s)"
    if dur_sec >= 1.8:
        return None
    if fullscreenish:
        return "short repeated youtube_fullscreen while already fullscreen"
    return None


def good_night_voice_text(action_result: str) -> str:
    lowered = (action_result or "").lower()
    if "no vacuumtube window" in lowered:
        return "おやすみなさいませ。YouTubeは停止済みのようです。どうぞ良い夢を。"
    if '"ok": true' in lowered or '"ok":true' in lowered or "afterpaused" in lowered:
        return "おやすみなさいませ。YouTubeを停止いたしました。どうぞ良い夢を。"
    if "video-not-found" in lowered:
        return "おやすみなさいませ。YouTubeの停止対象は見つかりませんでしたが、どうぞ良い夢を。"
    return "おやすみなさいませ。YouTubeの停止を試みました。どうぞ良い夢を。"


def post_action_voice_text(
    cmd: VoiceCommand,
    action_result: str,
    *,
    biometric_unlock_success_text_provider: Callable[[], str] | None = None,
) -> str | None:
    if cmd.intent == "good_night":
        return good_night_voice_text(action_result)
    if cmd.intent == "system_biometric_auth":
        if biometric_unlock_success_text_provider is None:
            return None
        return biometric_unlock_success_text_provider()
    if cmd.intent == "system_weather_today":
        return action_result
    return None
