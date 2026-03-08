from __future__ import annotations

import re

from .models import VoiceCommand


def normalize_transcript(text: str) -> str:
    normalized = (text or "").strip()
    normalized = normalized.replace("\u3000", " ")
    normalized = normalized.replace("|", " ").replace("｜", " ")
    normalized = normalized.lower()
    normalized = re.sub(r"[\s\t\r\n]+", "", normalized)
    normalized = re.sub(r"[。．！？!?,，、・]+$", "", normalized)
    normalized = "".join(
        chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
        for char in normalized
    )
    return normalized


def extract_password_unlock_secret(normalized_text: str) -> str:
    candidate = normalize_transcript(normalized_text)
    for prefix in (
        "システムパスワード",
        "systempassword",
        "システムロック解除パスワード",
        "systemunlockpassword",
    ):
        if candidate.startswith(prefix):
            return candidate[len(prefix) :]
    return ""


def _apply_command_aliases(text: str) -> str:
    aliased = text
    aliased = aliased.replace("本部", "音楽")
    aliased = aliased.replace("vgm", "bgm")
    aliased = aliased.replace("水銭も", "bgmを")
    aliased = aliased.replace("水銭を", "bgmを")
    aliased = aliased.replace("水銭", "bgm")
    aliased = aliased.replace("天気おほう", "天気予報")
    aliased = aliased.replace("テンキをほう", "天気予報")
    aliased = aliased.replace("テンキ予報", "天気予報")
    aliased = aliased.replace("ロイブカメラ", "街頭カメラ")
    aliased = aliased.replace("ワイブカメラ", "街頭カメラ")
    aliased = aliased.replace("レイブカメラ", "街頭カメラ")
    aliased = aliased.replace("フェイブカメラ", "街頭カメラ")
    aliased = aliased.replace("ライブカカメラ", "街頭カメラ")
    aliased = aliased.replace("ライブカメラ", "街頭カメラ")
    aliased = aliased.replace("外当カメラ", "街頭カメラ")
    aliased = aliased.replace("だいぶカメラ", "街頭カメラ")
    aliased = aliased.replace("ダイブカメラ", "街頭カメラ")
    aliased = aliased.replace("ウェブカーメラ", "ウェブカメラ")
    aliased = aliased.replace("ウエブカメラ", "ウェブカメラ")
    aliased = aliased.replace("スステム", "システム")
    aliased = aliased.replace("リステム", "システム")
    aliased = aliased.replace("エステム", "システム")
    aliased = aliased.replace("チステム", "システム")
    aliased = aliased.replace("フィスペム", "システム")
    aliased = aliased.replace("フィクテム", "システム")
    aliased = aliased.replace("cstm", "システム")
    aliased = re.sub(r"^ステム", "システム", aliased)
    aliased = aliased.replace("セステム", "システム")
    aliased = aliased.replace("バイオメデリックス", "バイオメトリクス")
    aliased = aliased.replace("バイオメテリクス", "バイオメトリクス")
    aliased = aliased.replace("バイオメテリクシン", "バイオメトリクス")
    aliased = aliased.replace("バイオメティクセニーショー", "バイオメトリクス認証")
    aliased = aliased.replace("バイオメテルクセ", "バイオメトリクス")
    aliased = aliased.replace("バイオミテリクス", "バイオメトリクス")
    aliased = aliased.replace("バイオミテリックス", "バイオメトリクス")
    aliased = aliased.replace("バヤメテリクス", "バイオメトリクス")
    aliased = aliased.replace("バイラメテリクス", "バイオメトリクス")
    aliased = aliased.replace("バイアメテルクス", "バイオメトリクス")
    aliased = aliased.replace("バイアメテリクス", "バイオメトリクス")
    aliased = aliased.replace("認証開始", "認証")
    aliased = re.sub(r"バイオメトリクス認$", "バイオメトリクス認証", aliased)
    aliased = re.sub(r"バイオメトリクス$", "バイオメトリクス認証", aliased)
    aliased = aliased.replace("フカ", "負荷")
    aliased = aliased.replace("深を確認", "負荷を確認")
    aliased = aliased.replace("負荷チェック", "負荷を確認")
    aliased = re.sub(r"全画(?!面)", "全画面にして", aliased)
    aliased = re.sub(r"ホーム画面に戻$", "ホーム画面に戻って", aliased)
    aliased = re.sub(r"(youtube[をのはが]?)大$", r"\1大きくして", aliased)
    aliased = aliased.replace("災害化", "最大化")
    aliased = re.sub(r"(youtube[をのはが]?)最大$", r"\1最大化して", aliased)
    aliased = re.sub(r"(youtube[をのはが]?)小$", r"\1小さくして", aliased)
    return aliased


def parse_command(text: str) -> VoiceCommand | None:
    raw = (text or "").strip()
    if not raw:
        return None

    normalized = normalize_transcript(raw)
    if not normalized:
        return None

    normalized_alias = _apply_command_aliases(normalized)

    has_music_subject = any(token in normalized_alias for token in ("音楽", "bgm", "ミュージック"))
    is_play = any(
        token in normalized_alias
        for token in ("再生", "流して", "流す", "かけて", "かける", "掛けて", "掛ける")
    )
    is_stop = any(
        token in normalized_alias for token in ("停止", "止め", "とめ", "止ま", "一時停止")
    )
    is_resume = any(token in normalized_alias for token in ("再開", "再生再開"))
    has_news_subject = any(token in normalized_alias for token in ("ニュース", "news"))
    has_video_subject = any(token in normalized_alias for token in ("動画", "ビデオ", "video"))
    has_youtube_subject = any(
        token in normalized_alias for token in ("youtube", "ユーチューブ", "ようつべ")
    )
    has_home_subject = any(token in normalized_alias for token in ("ホーム画面", "ホーム"))
    has_fullscreen_subject = any(
        token in normalized_alias
        for token in ("全画面", "フルスクリーン", "大きく", "おおきく", "最大化", "さいだいか")
    )
    has_small_subject = any(token in normalized_alias for token in ("小さく", "ちいさく"))
    has_quadrant_subject = any(token in normalized_alias for token in ("4分割", "四分割"))
    wants_move_home = any(
        token in normalized_alias
        for token in ("戻って", "戻る", "移動して", "移動", "行って", "行く")
    )
    wants_watch = any(
        token in normalized_alias
        for token in (
            "見たい",
            "みたい",
            "見せて",
            "みせて",
            "再生",
            "流して",
            "流す",
            "つけて",
            "つける",
        )
    )
    wants_resize_mode = any(
        token in normalized_alias
        for token in ("して", "にして", "にする", "戻して", "戻す", "モード")
    )
    news_live_hint = any(
        token in normalized_alias
        for token in ("ライブ", "live", "最新", "速報", "生放送")
    )
    news_morning_hint = any(
        token in normalized_alias for token in ("朝", "morning", "モーニング", "おはよう")
    )
    news_evening_hint = any(
        token in normalized_alias for token in ("夕方", "夜", "evening", "night", "イブニング")
    )
    has_weather_subject = any(token in normalized_alias for token in ("天気", "weather"))
    has_forecast_subject = ("天気予報" in normalized_alias) or ("予報" in normalized_alias)
    wants_weather_report = any(
        token in normalized_alias
        for token in ("教えて", "おしえて", "は", "確認", "報告", "チェック")
    )
    has_today_hint = any(token in normalized_alias for token in ("今日", "きょう", "本日"))
    has_live_camera_subject = any(
        token in normalized_alias
        for token in ("街頭カメラ", "ライブカメラ", "livecamera", "livecam")
    )
    has_webcam_subject = any(
        token in normalized_alias for token in ("ウェブカメラ", "webカメラ", "webcam", "ウェブカム")
    )
    has_load_subject = any(token in normalized_alias for token in ("負荷", "load"))
    wants_hide = any(
        token in normalized_alias
        for token in ("終了", "終わ", "閉じて", "閉じる", "非表示", "隠して", "かくして")
    )
    wants_background = any(token in normalized_alias for token in ("背景", "バックグラウンド"))
    wants_confirm = any(
        token in normalized_alias
        for token in ("確認", "見たい", "みたい", "見せて", "みせて", "表示", "確認したい")
    )
    playback_object_hint = any(
        token in normalized_alias
        for token in (
            "再生を",
            "再生の",
            "動画を",
            "動画の",
            "ニュースを",
            "ニュースの",
            "再生中",
        )
    )
    has_system_subject = ("システム" in normalized_alias) or ("system" in normalized_alias)
    wants_load_check = (
        wants_confirm or ("チェック" in normalized_alias) or ("買ってみ" in normalized_alias)
    )

    if has_load_subject and wants_load_check:
        return VoiceCommand("system_load_check", normalized_alias, raw)
    if "通常モード" in normalized_alias:
        return VoiceCommand("system_normal_mode", normalized_alias, raw)
    if "世界情勢モード" in normalized_alias:
        return VoiceCommand("system_world_situation_mode", normalized_alias, raw)
    if "天気予報モード" in normalized_alias:
        return VoiceCommand("system_weather_mode", normalized_alias, raw)
    if has_system_subject and (
        ("ロックモード" in normalized_alias) or ("lockmode" in normalized_alias)
    ):
        return VoiceCommand("system_lock_mode", normalized_alias, raw)
    if has_system_subject and ("街頭カメラモード" in normalized_alias):
        return VoiceCommand("system_street_camera_mode", normalized_alias, raw)
    if has_system_subject and ("ウェブカメラモード" in normalized_alias):
        return VoiceCommand("system_webcam_mode", normalized_alias, raw)

    status_tokens = (
        "状況報告",
        "状態報告",
        "現状報告",
        "状況教えて",
        "状態教えて",
        "現状教えて",
        "ステータス",
        "ステータスチェック",
        "ステータス確認",
        "チェック",
        "status",
    )
    status_literals = {
        "システム状況報告",
        "システム状態報告",
        "システム現状報告",
        "システム状況教えて",
        "システム状態教えて",
        "システム現状教えて",
        "システムステータス",
        "システムチェック",
        "システムステータスチェック",
        "システムステータス報告",
        "システムステータス確認",
        "状況報告",
        "状態教えて",
        "statusreport",
    }
    if (
        has_system_subject and any(token in normalized_alias for token in status_tokens)
    ) or normalized_alias in status_literals:
        return VoiceCommand("system_status_report", normalized_alias, raw)

    if has_system_subject and has_live_camera_subject:
        if wants_hide:
            return VoiceCommand("system_live_camera_hide", normalized_alias, raw)
        if has_small_subject or has_quadrant_subject:
            return VoiceCommand("system_live_camera_compact", normalized_alias, raw)
        if wants_confirm or wants_watch or has_fullscreen_subject:
            return VoiceCommand("system_live_camera_show", normalized_alias, raw)

    if has_system_subject and has_webcam_subject:
        if wants_background:
            return VoiceCommand("god_mode_background", normalized_alias, raw)
        if has_fullscreen_subject:
            return VoiceCommand("god_mode_fullscreen", normalized_alias, raw)
        if has_small_subject:
            return VoiceCommand("god_mode_compact", normalized_alias, raw)
        if wants_confirm or wants_watch:
            return VoiceCommand("god_mode_show", normalized_alias, raw)

    if has_system_subject and has_forecast_subject and (
        wants_confirm or wants_watch or ("開いて" in normalized_alias)
    ):
        return VoiceCommand("weather_pages_today", normalized_alias, raw)
    if has_system_subject and has_weather_subject and has_today_hint and wants_weather_report:
        return VoiceCommand("system_weather_today", normalized_alias, raw)
    if (not has_system_subject) and has_weather_subject and has_today_hint and wants_weather_report:
        return VoiceCommand("weather_pages_today", normalized_alias, raw)

    biometric_tokens = (
        "バイオメトリクス認証",
        "バイオメトリクス",
        "バイオメトリック",
        "バイアメテリクス",
        "生体認証",
        "biometricauth",
        "biometrics",
        "認証解除",
        "ロック解除",
    )
    if any(token in normalized_alias for token in biometric_tokens):
        return VoiceCommand("system_biometric_auth", normalized_alias, raw)

    if has_system_subject and any(
        token in normalized_alias for token in ("パスワード", "password")
    ):
        secret_text = extract_password_unlock_secret(normalized_alias)
        if secret_text:
            return VoiceCommand("system_password_unlock", normalized_alias, raw, secret_text)

    if has_system_subject and any(
        token in normalized_alias for token in ("おはよう", "おはよ", "お早う", "goodmorning")
    ):
        return VoiceCommand("good_morning", normalized_alias, raw)

    if has_system_subject and (
        normalized_alias in {
            "システムおやすみ",
            "システムおやすみなさい",
            "システムおやすみなさいませ",
            "システムお休み",
            "システムお休みなさい",
            "システム寝る",
            "システム寝ます",
            "systemgoodnight",
            "systemsleep",
        }
        or any(
            normalized_alias.endswith(suffix)
            for suffix in (
                "システムおやすみ",
                "システムおやすみなさい",
                "システム寝る",
                "システム寝ます",
                "systemgoodnight",
                "systemsleep",
            )
        )
    ):
        return VoiceCommand("good_night", normalized_alias, raw)

    if has_youtube_subject and has_fullscreen_subject and wants_resize_mode and not is_stop:
        return VoiceCommand("youtube_fullscreen", normalized_alias, raw)
    if (has_youtube_subject and has_small_subject and wants_resize_mode) or (
        has_quadrant_subject and wants_resize_mode
    ):
        return VoiceCommand("youtube_quadrant", normalized_alias, raw)
    if has_youtube_subject and any(
        token in normalized_alias for token in ("最小化", "非表示", "隠して", "バックグラウンド")
    ):
        return VoiceCommand("youtube_minimize", normalized_alias, raw)
    if has_youtube_subject and has_home_subject and wants_move_home:
        return VoiceCommand("youtube_home", normalized_alias, raw)

    if is_stop and (
        has_music_subject
        or has_news_subject
        or has_video_subject
        or playback_object_hint
        or "再生停止" in normalized_alias
    ):
        if has_music_subject:
            return VoiceCommand("music_stop", normalized_alias, raw)
        return VoiceCommand("playback_stop", normalized_alias, raw)

    if not is_stop and (is_resume or (has_video_subject and is_play and not has_news_subject)):
        return VoiceCommand("playback_resume", normalized_alias, raw)
    if has_music_subject and is_play and not is_stop:
        return VoiceCommand("music_play", normalized_alias, raw)
    if has_news_subject and (wants_watch or news_live_hint):
        if news_morning_hint and not news_evening_hint:
            return VoiceCommand("news_morning", normalized_alias, raw)
        if news_evening_hint:
            return VoiceCommand("news_evening", normalized_alias, raw)
        return VoiceCommand("news_live", normalized_alias, raw)

    if normalized_alias in {"再生して", "再生してください", "音楽再生", "bgm再生"}:
        return VoiceCommand("music_play", normalized_alias, raw)
    if normalized_alias in {
        "停止して",
        "停止してください",
        "止めて",
        "止めてください",
        "音楽停止",
        "bgm停止",
    }:
        return VoiceCommand("music_stop", normalized_alias, raw)
    if normalized_alias in {
        "動画再開",
        "動画を再開して",
        "動画を再生して",
        "再開して",
        "再開してください",
        "動画を再生再開して",
    }:
        return VoiceCommand("playback_resume", normalized_alias, raw)
    if normalized_alias in {
        "動画停止",
        "動画を止めて",
        "再生を止めて",
        "再生停止",
        "ニュース動画再生を止めて",
    }:
        return VoiceCommand("playback_stop", normalized_alias, raw)
    if normalized_alias in {
        "youtubeを全画面にして",
        "youtube全画面",
        "youtubeをフルスクリーンにして",
        "youtubeを大きくして",
        "youtubeを最大化して",
    }:
        return VoiceCommand("youtube_fullscreen", normalized_alias, raw)
    if normalized_alias in {
        "youtubeを小さくして",
        "youtube小さく",
        "4分割モード",
        "四分割モード",
        "4分割にして",
        "四分割にして",
    }:
        return VoiceCommand("youtube_quadrant", normalized_alias, raw)
    if normalized_alias in {
        "youtubeを最小化して",
        "youtubeを非表示にして",
        "youtubeを隠して",
        "youtubeをバックグラウンドにして",
        "youtubeをバックグラウンドに",
        "システムyoutubeを最小化して",
        "システムyoutubeを非表示にして",
        "システムyoutubeを隠して",
        "システムyoutubeをバックグラウンドにして",
    }:
        return VoiceCommand("youtube_minimize", normalized_alias, raw)
    if normalized_alias in {
        "youtubeホーム",
        "youtubeホーム画面",
        "youtubeのホーム画面に戻って",
        "youtubeのホームに移動して",
    }:
        return VoiceCommand("youtube_home", normalized_alias, raw)
    if normalized_alias in {
        "ニュースライブ",
        "ニュースライブ再生",
        "ライブニュース再生",
        "ニュース再生",
        "ニュースを再生して",
    }:
        return VoiceCommand("news_live", normalized_alias, raw)
    if normalized_alias in {
        "朝のニュース",
        "朝ニュース",
        "朝のニュース再生",
        "朝のニュースを見たい",
    }:
        return VoiceCommand("news_morning", normalized_alias, raw)
    if normalized_alias in {
        "夕方のニュース",
        "夕方ニュース",
        "夕方のニュース再生",
        "夕方のニュースを見たい",
    }:
        return VoiceCommand("news_evening", normalized_alias, raw)
    if normalized_alias in {
        "システム状況報告",
        "システム状態報告",
        "システム現状報告",
        "システム状況教えて",
        "システム状態教えて",
        "システム現状教えて",
        "システムステータス",
    }:
        return VoiceCommand("system_status_report", normalized_alias, raw)
    return None
