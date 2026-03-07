from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest import mock

from arouter import VoiceCommand
from arouter.execution import command_has_system_prefix, execute_command


def _make_runtime() -> SimpleNamespace:
    runtime = SimpleNamespace()
    runtime.log = mock.Mock()
    runtime._god_mode_last_layout = None
    runtime._live_cam_last_layout = None
    runtime._run_vacuumtube_action = mock.Mock(side_effect=lambda action, **_kwargs: action())
    runtime._get_vacuumtube_context = mock.Mock(return_value={})
    runtime._set_system_locked = mock.Mock(return_value=True)
    runtime.system_status_report = mock.Mock(return_value="ok")
    runtime.system_weather_today = mock.Mock(return_value="ok")
    runtime.show_weather_pages_today = mock.Mock(return_value="ok")
    runtime.system_live_camera_show = mock.Mock(return_value="ok")
    runtime.system_live_camera_compact = mock.Mock(return_value="ok")
    runtime.system_live_camera_hide = mock.Mock(return_value="ok")
    runtime.system_normal_mode = mock.Mock(return_value="ok")
    runtime.system_world_situation_mode = mock.Mock(return_value="ok")
    runtime.system_weather_mode = mock.Mock(return_value="ok")
    runtime.system_street_camera_mode = mock.Mock(return_value="ok")
    runtime.system_webcam_mode = mock.Mock(return_value="ok")
    runtime.god_mode_layout = mock.Mock(return_value="ok")
    runtime.system_load_check = mock.Mock(return_value="ok")
    runtime.good_morning = mock.Mock(return_value="ok")
    runtime.good_night = mock.Mock(return_value="ok")
    runtime.vacuumtube = SimpleNamespace(
        play_bgm=mock.Mock(return_value="ok"),
        stop_music=mock.Mock(return_value="ok"),
        resume_playback=mock.Mock(return_value="ok"),
        youtube_fullscreen=mock.Mock(return_value='youtube fullscreen {"fullscreen": true}'),
        youtube_quadrant=mock.Mock(return_value="ok"),
        youtube_minimize=mock.Mock(return_value="ok"),
        go_youtube_home=mock.Mock(return_value="ok"),
        play_news=mock.Mock(return_value="opened watch route #/watch?v=abc"),
    )
    return runtime


def test_execute_command_dispatches_system_status_report() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("system_status_report", "システム状況報告", "システム 状況報告")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_status_report.assert_called_once()


def test_execute_command_dispatches_system_lock_mode() -> None:
    runtime = _make_runtime()
    runtime._biometric_lock_state_lock = threading.Lock()
    cmd = VoiceCommand(
        "system_lock_mode",
        "システムロックモード",
        "システム ロックモード",
    )

    out = execute_command(runtime, cmd)

    assert out == "system locked by command"
    runtime._set_system_locked.assert_called_once_with(True, reason="command:system_lock_mode")


def test_execute_command_returns_noop_when_youtube_already_playing_for_resume() -> None:
    runtime = _make_runtime()
    runtime._get_vacuumtube_context = mock.Mock(
        return_value={
            "watchRoute": True,
            "videoPlaying": True,
        }
    )
    cmd = VoiceCommand("playback_resume", "youtubeを再開して", "YouTubeを再開して")

    out = execute_command(runtime, cmd)

    assert out == "youtube already playing (context no-op)"
    runtime._run_vacuumtube_action.assert_not_called()


def test_execute_command_dispatches_system_weather_today() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(
        "system_weather_today",
        "システム今日の天気",
        "システム 今日の天気",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_weather_today.assert_called_once()


def test_execute_command_dispatches_weather_pages_today() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("weather_pages_today", "今日の天気教えて", "今日の天気教えて")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.show_weather_pages_today.assert_called_once()


def test_execute_command_dispatches_system_prefixed_news_live_and_fullscreens() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(
        "news_live",
        "システムニュースが見たい",
        "システム ニュースが見たい",
    )

    out = execute_command(runtime, cmd)

    assert "opened watch route" in out
    assert "youtube fullscreen" in out
    runtime.vacuumtube.play_news.assert_called_once_with(slot="generic")
    runtime.vacuumtube.youtube_fullscreen.assert_called_once()


def test_execute_command_dispatches_plain_news_live_without_fullscreen() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("news_live", "ニュースが見たい", "ニュースが見たい")

    out = execute_command(runtime, cmd)

    assert out == "opened watch route #/watch?v=abc"
    runtime.vacuumtube.play_news.assert_called_once_with(slot="generic")
    runtime.vacuumtube.youtube_fullscreen.assert_not_called()


def test_execute_command_dispatches_system_live_camera_show() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(
        "system_live_camera_show",
        "システム街頭カメラ確認したい",
        "システム 街頭カメラ確認したい",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_live_camera_show.assert_called_once()


def test_execute_command_dispatches_system_world_situation_mode() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(
        "system_world_situation_mode",
        "システム世界情勢モード",
        "システム 世界情勢モード",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_world_situation_mode.assert_called_once()


def test_execute_command_dispatches_god_mode_show() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(
        "god_mode_show",
        "システムウェブカメラが見たい",
        "システム、ウェブカメラが見たい",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.god_mode_layout.assert_called_once_with("frontmost")


def test_execute_command_god_mode_fullscreen_tolerates_missing_layout_state() -> None:
    runtime = _make_runtime()
    del runtime._god_mode_last_layout
    cmd = VoiceCommand(
        "god_mode_fullscreen",
        "システムウェブカメラを最大化",
        "システム ウェブカメラを最大化",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.god_mode_layout.assert_called_once_with("full-screen")


def test_execute_command_god_mode_fullscreen_can_disambiguate_to_live_camera_show() -> None:
    runtime = _make_runtime()
    runtime._god_mode_last_layout = "frontmost"
    cmd = VoiceCommand(
        "god_mode_fullscreen",
        "システムウェブカメラを最大化",
        "システム ウェブカメラを最大化",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_live_camera_show.assert_called_once()
    runtime.god_mode_layout.assert_not_called()


def test_execute_command_god_mode_compact_can_disambiguate_to_live_camera_compact() -> None:
    runtime = _make_runtime()
    runtime._god_mode_last_layout = "frontmost"
    runtime._live_cam_last_layout = "show"
    cmd = VoiceCommand(
        "god_mode_compact",
        "システムウェブカメラを小さくして",
        "システム、ウェブカメラを小さくして",
    )

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_live_camera_compact.assert_called_once()
    runtime.god_mode_layout.assert_not_called()


def test_execute_command_dispatches_system_load_check() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("system_load_check", "システム負荷を確認", "システム 負荷を確認")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.system_load_check.assert_called_once()


def test_execute_command_dispatches_good_morning() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("good_morning", "システムおはよう", "システム おはよう")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.good_morning.assert_called_once()


def test_execute_command_dispatches_good_night() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("good_night", "システムおやすみ", "システム おやすみ")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime.good_night.assert_called_once()


def test_execute_command_dispatches_system_biometric_auth() -> None:
    runtime = _make_runtime()
    runtime.system_normal_mode = mock.Mock(return_value="normal mode ok")
    cmd = VoiceCommand(
        "system_biometric_auth",
        "システムバイオメトリクス認証",
        "システム バイオメトリクス認証",
    )

    out = execute_command(runtime, cmd)

    assert out == "system unlocked by biometric authentication; normal mode ok"
    runtime.system_normal_mode.assert_called_once()


def test_command_has_system_prefix_detects_explicit_prefix() -> None:
    cmd = VoiceCommand("news_live", "システムニュースが見たい", "システム ニュースが見たい")

    assert command_has_system_prefix(cmd) is True


def test_command_has_system_prefix_uses_raw_text_when_normalized_missing() -> None:
    cmd = VoiceCommand("news_live", "", "system news please")

    assert command_has_system_prefix(cmd) is True
