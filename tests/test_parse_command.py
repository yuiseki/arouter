from __future__ import annotations

import json

import pytest

from arouter import (
    build_overlay_ipc_line,
    compose_overlay_notify_text,
    extract_password_unlock_secret,
    normalize_transcript,
    parse_command,
)


def test_build_overlay_ipc_line_encodes_jsonl() -> None:
    line = build_overlay_ipc_line(
        {
            "type": "speak",
            "text": "承知しました、音楽を再生します。",
            "wav_path": "/tmp/ack.wav",
            "wait": True,
        }
    )
    assert line.endswith(b"\n")
    payload = json.loads(line.decode("utf-8"))
    assert payload["type"] == "speak"
    assert payload["wav_path"] == "/tmp/ack.wav"
    assert payload["wait"] is True


@pytest.mark.parametrize(
    ("title", "body", "expected"),
    [
        (
            "音声コマンド 完了",
            "承知しました、音楽を再生します。",
            "音声コマンド 完了: 承知しました、音楽を再生します。",
        ),
        ("音声コマンド 認識", "", "音声コマンド 認識"),
    ],
)
def test_compose_overlay_notify_text(title: str, body: str, expected: str) -> None:
    assert compose_overlay_notify_text(title, body) == expected


def test_normalize_transcript_cleans_spacing_and_full_width_ascii() -> None:
    assert normalize_transcript(" ＹｏｕＴｕｂｅ を　全画面にして。 ") == "youtubeを全画面にして"


@pytest.mark.parametrize(
    ("text", "expected_intent"),
    [
        ("音楽を停止してください。", "music_stop"),
        ("ニュース｜動画｜再生を止めて", "playback_stop"),
        ("動画を再開して", "playback_resume"),
        ("動画を再生｜再開して", "playback_resume"),
        ("BGM再生して", "music_play"),
        ("VGMを再生して", "music_play"),
        ("水銭も流して", "music_play"),
        ("本部を止めてください", "music_stop"),
        ("ニュースライブを再生して", "news_live"),
        ("システム ニュースが見たい", "news_live"),
        ("夕方のニュースが見たい", "news_evening"),
        ("朝のニュースを見せて", "news_morning"),
        ("YouTubeのホーム画面に戻って｜移動して", "youtube_home"),
        ("ユーチューブのホームに移動して", "youtube_home"),
        ("YouTubeを全画面にして", "youtube_fullscreen"),
        ("システム 状況報告", "system_status_report"),
        ("システム 通常モード", "system_normal_mode"),
        ("システム 世界情勢モード", "system_world_situation_mode"),
        ("天気予報モード。", "system_weather_mode"),
        ("システム 今日の天気を教えて", "system_weather_today"),
        ("システム 天気予報を表示", "weather_pages_today"),
        ("システム 街頭カメラ確認したい", "system_live_camera_show"),
        ("システム ライブカメラ確認したい", "system_live_camera_show"),
        ("システム フェイブカメラを最大化して", "system_live_camera_show"),
        ("システム 街頭カメラ小さくして", "system_live_camera_compact"),
        ("システム 街頭カメラ非表示にして", "system_live_camera_hide"),
        ("システム 外当カメラモード", "system_street_camera_mode"),
        ("システム ウェブカメラモード", "system_webcam_mode"),
        ("システム 負荷を確認", "system_load_check"),
        ("システム、フカを確認", "system_load_check"),
        ("システム、おはよう", "good_morning"),
        ("システム おやすみ", "good_night"),
        ("システム バイオメトリクス認証", "system_biometric_auth"),
        ("システム バイアメテルクス認証", "system_biometric_auth"),
        ("システム バイアメテリクス認証", "system_biometric_auth"),
        ("システム バイオミテルクス認証", "system_biometric_auth"),
        ("システム バイオミテレクスニーショー", "system_biometric_auth"),
        ("?? システム バイオメテリクス認証", "system_biometric_auth"),
        ("システム ロックモード", "system_lock_mode"),
        ("システム、YouTubeを最小化して", "youtube_minimize"),
        ("システム、ウェブカメラが見たい", "god_mode_show"),
        ("システム ウェブカメラを最大化", "god_mode_fullscreen"),
        ("システム、ウェブカメラを小さくして", "god_mode_compact"),
        ("システム、ウェブカメラを背景にして", "god_mode_background"),
    ],
)
def test_parse_command_maps_supported_phrases(text: str, expected_intent: str) -> None:
    command = parse_command(text)
    assert command is not None
    assert command.intent == expected_intent


@pytest.mark.parametrize(
    "text",
    [
        "おやすみ",
        "寝る",
        "YouTubeを再生して",
        "ホーム画面に戻って",
        "天気を教えてください",
        "",
        "   ",
    ],
)
def test_parse_command_rejects_unmapped_text(text: str) -> None:
    assert parse_command(text) is None


def test_extract_password_unlock_secret_trims_prefix() -> None:
    assert extract_password_unlock_secret("システム パスワード パスワード") == "パスワード"
