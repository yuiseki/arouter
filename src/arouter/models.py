from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VoiceCommand:
    intent: str
    normalized_text: str
    raw_text: str
    secret_text: str = ""

    @property
    def ack_text(self) -> str:
        if self.intent == "music_play":
            return "承知しました、音楽を再生します。"
        if self.intent == "music_stop":
            return "承知しました、音楽を停止します。"
        if self.intent == "playback_resume":
            return "承知しました、動画の再生を再開します。"
        if self.intent == "playback_stop":
            return "承知しました、動画の再生を停止します。"
        if self.intent == "news_live":
            return "承知しました、ニュースライブを再生します。"
        if self.intent == "news_morning":
            return "承知しました、朝のニュースを再生します。"
        if self.intent == "news_evening":
            normalized = self.normalized_text.lower()
            if any(token in normalized for token in ("夜", "night")):
                return "承知しました、夜のニュースを再生します。"
            return "承知しました、夕方のニュースを再生します。"
        if self.intent == "youtube_fullscreen":
            return "承知しました、YouTubeを全画面にします。"
        if self.intent == "youtube_quadrant":
            return "承知しました、YouTubeを小さくします。"
        if self.intent == "youtube_minimize":
            return "承知しました、YouTubeを最小化します。"
        if self.intent == "youtube_home":
            return "承知しました、YouTubeのホーム画面に戻ります。"
        if self.intent == "system_status_report":
            return "システムチェック完了 オールグリーン 通常モード"
        if self.intent == "system_weather_today":
            return "承知しました、今日の天気を確認します。"
        if self.intent == "weather_pages_today":
            return "承知しました、天気予報ページを表示します。"
        if self.intent == "system_live_camera_show":
            return "承知しました、街頭カメラを表示します。"
        if self.intent == "system_live_camera_compact":
            return "承知しました、街頭カメラを小さくします。"
        if self.intent == "system_live_camera_hide":
            return "承知しました、街頭カメラを閉じます。"
        if self.intent == "system_street_camera_mode":
            return "承知しました。街頭カメラモードへ移行します。"
        if self.intent == "system_webcam_mode":
            return "承知しました。ウェブカメラモードへ移行します。"
        if self.intent == "god_mode_show":
            return "承知しました、ウェブカメラを表示します。"
        if self.intent == "god_mode_fullscreen":
            return "承知しました、ウェブカメラを最大化します。"
        if self.intent == "god_mode_compact":
            return "承知しました、ウェブカメラを小さくします。"
        if self.intent == "god_mode_background":
            return "承知しました、ウェブカメラを背景にします。"
        if self.intent == "system_normal_mode":
            return "承知しました。通常モードに移行します。"
        if self.intent == "system_world_situation_mode":
            return "承知しました。世界情勢モードへ移行します。"
        if self.intent == "system_weather_mode":
            return "承知しました。天気予報モードへ移行します。"
        if self.intent == "system_lock_mode":
            return "承知しました。ロックモードへ移行します。"
        if self.intent == "system_load_check":
            return "承知しました、負荷を確認します。"
        if self.intent == "system_biometric_auth":
            return "承知しました。バイオメトリクス認証を確認します。"
        if self.intent == "system_password_unlock":
            return "承知しました。パスワードを確認します。"
        if self.intent == "good_morning":
            return "おはようございます、ユイさま。朝のニュースを再生しますね。"
        if self.intent == "good_night":
            return "おやすみなさいませ。どうぞ良い夢を。"
        return "承知しました。"
