from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest import mock

from arouter import VoiceCommand
from arouter.execution import (
    command_has_system_prefix,
    execute_command,
    run_god_mode_layout_host_runtime,
    run_good_morning_host_runtime,
    run_good_night_host_runtime,
    run_show_weather_pages_today_host_runtime,
    run_system_live_camera_compact_host_runtime,
    run_system_live_camera_hide_host_runtime,
    run_system_live_camera_show_host_runtime,
    run_system_normal_mode_host_runtime,
    run_system_status_report_host_runtime,
    run_system_street_camera_mode_host_runtime,
    run_system_weather_mode_host_runtime,
    run_system_webcam_mode_host_runtime,
    run_system_world_situation_mode_host_runtime,
)


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
        good_night_pause=mock.Mock(return_value='good_night pause {"ok": true}'),
        open_weather_pages_tiled=mock.Mock(return_value="weather pages tiled []"),
        close_weather_pages_tiled=mock.Mock(return_value='weather pages closed {"closed":2}'),
    )
    runtime._play_music = mock.Mock(
        side_effect=lambda: runtime._run_vacuumtube_action(
            runtime.vacuumtube.play_bgm,
            label="music_play",
        )
    )
    runtime._stop_music = mock.Mock(
        side_effect=lambda *, label: runtime._run_vacuumtube_action(
            runtime.vacuumtube.stop_music,
            label=label,
        )
    )
    runtime._resume_playback = mock.Mock(
        side_effect=lambda: runtime._run_vacuumtube_action(
            runtime.vacuumtube.resume_playback,
            label="playback_resume",
        )
    )
    runtime._play_morning_news = mock.Mock(
        side_effect=lambda: runtime._play_news_slot(
            slot="morning",
            label="good_morning_news",
        )
    )
    runtime._play_news_slot = mock.Mock(
        side_effect=lambda *, slot, label=None: runtime._run_vacuumtube_action(
            lambda: runtime.vacuumtube.play_news(slot=slot),
            label=label or f"news_{slot}",
        )
    )
    runtime._fullscreen_vacuumtube = mock.Mock(
        side_effect=lambda *, label: runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_fullscreen,
            label=label,
        )
    )
    runtime._open_weather_pages_tiled = mock.Mock(
        side_effect=runtime.vacuumtube.open_weather_pages_tiled
    )
    runtime._close_weather_pages_tiled = mock.Mock(
        side_effect=runtime.vacuumtube.close_weather_pages_tiled
    )
    runtime._pause_for_night = mock.Mock(side_effect=runtime.vacuumtube.good_night_pause)
    runtime._fullscreen_morning_news = mock.Mock(
        side_effect=lambda: runtime._fullscreen_vacuumtube(
            label="good_morning_fullscreen"
        )
    )
    runtime._youtube_quadrant = mock.Mock(
        side_effect=lambda: runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_quadrant,
            label="youtube_quadrant",
        )
    )
    runtime._youtube_minimize = mock.Mock(
        side_effect=lambda: runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_minimize,
            label="youtube_minimize",
        )
    )
    runtime._go_youtube_home = mock.Mock(
        side_effect=lambda: runtime._run_vacuumtube_action(
            runtime.vacuumtube.go_youtube_home,
            label="youtube_home",
        )
    )
    runtime._show_live_camera_full = mock.Mock(return_value="show ok")
    runtime._show_live_camera_compact = mock.Mock(return_value="compact ok")
    runtime._hide_live_camera = mock.Mock(return_value="hide ok")
    runtime._minimize_live_camera = mock.Mock(return_value="street minimized")
    runtime._world_situation_mode_script_path = mock.Mock(return_value="/tmp/world.sh")
    runtime._weather_mode_script_path = mock.Mock(return_value="/tmp/weather.sh")
    runtime._god_mode_layout_script_path = mock.Mock(return_value="/tmp/tmp_main.sh")
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
    runtime._play_news_slot.assert_called_once_with(slot="generic", label="news_generic")
    runtime._fullscreen_vacuumtube.assert_called_once_with(label="news_generic_fullscreen")


def test_execute_command_dispatches_plain_news_live_without_fullscreen() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("news_live", "ニュースが見たい", "ニュースが見たい")

    out = execute_command(runtime, cmd)

    assert out == "opened watch route #/watch?v=abc"
    runtime._play_news_slot.assert_called_once_with(slot="generic", label="news_generic")
    runtime._fullscreen_vacuumtube.assert_not_called()


def test_execute_command_dispatches_music_play_via_runtime_method() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("music_play", "音楽再生して", "音楽再生して")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime._play_music.assert_called_once_with()


def test_execute_command_dispatches_playback_resume_via_runtime_method() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("playback_resume", "続きから再生して", "続きから再生して")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime._resume_playback.assert_called_once_with()


def test_execute_command_dispatches_youtube_quadrant_via_runtime_method() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("youtube_quadrant", "YouTubeを右上にして", "YouTubeを右上にして")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime._youtube_quadrant.assert_called_once_with()


def test_execute_command_dispatches_youtube_minimize_via_runtime_method() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("youtube_minimize", "YouTubeを最小化して", "YouTubeを最小化して")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime._youtube_minimize.assert_called_once_with()


def test_execute_command_dispatches_youtube_home_via_runtime_method() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand("youtube_home", "YouTubeのホームに戻って", "YouTubeのホームに戻って")

    out = execute_command(runtime, cmd)

    assert out == "ok"
    runtime._go_youtube_home.assert_called_once_with()


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


def test_run_system_status_report_host_runtime_closes_weather_pages() -> None:
    runtime = SimpleNamespace(
        _close_weather_pages_tiled=mock.Mock(return_value='weather pages closed {"closed":2}')
    )

    out = run_system_status_report_host_runtime(runtime=runtime)

    assert out == 'system running; normal mode; weather pages closed {"closed":2}'
    runtime._close_weather_pages_tiled.assert_called_once_with()


def test_run_system_status_report_host_runtime_formats_close_error() -> None:
    runtime = SimpleNamespace(
        _close_weather_pages_tiled=mock.Mock(side_effect=RuntimeError("boom"))
    )

    out = run_system_status_report_host_runtime(runtime=runtime)

    assert out == "system running; normal mode; weather pages close error: boom"


def test_run_show_weather_pages_today_host_runtime_delegates_to_vacuumtube() -> None:
    runtime = SimpleNamespace(
        _open_weather_pages_tiled=mock.Mock(return_value="weather pages tiled []")
    )

    out = run_show_weather_pages_today_host_runtime(runtime=runtime)

    assert out == "weather pages tiled []"
    runtime._open_weather_pages_tiled.assert_called_once_with()


def test_run_good_morning_host_runtime_uses_news_fullscreen_and_lights() -> None:
    runtime = SimpleNamespace(
        _play_morning_news=mock.Mock(return_value="news ok"),
        _fullscreen_morning_news=mock.Mock(return_value="fullscreen ok"),
        _lights_on=mock.Mock(return_value="switchbot lights on: ok"),
    )

    out = run_good_morning_host_runtime(
        runtime=runtime,
    )

    assert out == "good_morning news ok fullscreen=fullscreen ok lights=switchbot lights on: ok"
    runtime._play_morning_news.assert_called_once_with()
    runtime._fullscreen_morning_news.assert_called_once_with()
    runtime._lights_on.assert_called_once_with()


def test_run_good_night_host_runtime_uses_pause_and_lights_off() -> None:
    runtime = SimpleNamespace(
        _pause_for_night=mock.Mock(return_value='good_night pause {"ok": true}'),
        _lights_off=mock.Mock(return_value="switchbot lights off: ok"),
    )

    out = run_good_night_host_runtime(
        runtime=runtime,
    )

    assert out == 'good_night pause {"ok": true} lights=switchbot lights off: ok'
    runtime._pause_for_night.assert_called_once_with()
    runtime._lights_off.assert_called_once_with()


def test_run_system_live_camera_show_host_runtime_tracks_layout_and_calls_show_full() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        _show_live_camera_full=mock.Mock(return_value="show ok"),
    )

    out = run_system_live_camera_show_host_runtime(runtime=runtime)

    assert out == "show ok"
    assert runtime._live_cam_last_layout == "show"
    runtime._show_live_camera_full.assert_called_once_with()


def test_run_system_live_camera_compact_host_runtime_tracks_layout_and_calls_show_compact() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        _show_live_camera_compact=mock.Mock(return_value="compact ok"),
    )

    out = run_system_live_camera_compact_host_runtime(runtime=runtime)

    assert out == "compact ok"
    assert runtime._live_cam_last_layout == "compact"
    runtime._show_live_camera_compact.assert_called_once_with()


def test_run_system_live_camera_hide_host_runtime_tracks_layout_and_calls_hide() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        _hide_live_camera=mock.Mock(return_value="hide ok"),
    )

    out = run_system_live_camera_hide_host_runtime(runtime=runtime)

    assert out == "hide ok"
    assert runtime._live_cam_last_layout == "hide"
    runtime._hide_live_camera.assert_called_once_with()


def test_run_system_street_camera_mode_host_runtime_reuses_show_helper() -> None:
    runtime = SimpleNamespace(system_live_camera_show=mock.Mock(return_value="show ok"))

    out = run_system_street_camera_mode_host_runtime(runtime=runtime)

    assert out == "show ok"
    runtime.system_live_camera_show.assert_called_once_with()


def test_run_system_webcam_mode_host_runtime_tracks_layout_and_reuses_system_mode_helper() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        _minimize_live_camera=mock.Mock(return_value="street minimized"),
        god_mode_layout=mock.Mock(return_value="webcam ok"),
    )

    out = run_system_webcam_mode_host_runtime(runtime=runtime)

    assert out == "street minimized; webcam ok"
    assert runtime._live_cam_last_layout == "hide"
    runtime._minimize_live_camera.assert_called_once_with()
    runtime.god_mode_layout.assert_called_once_with("frontmost")


def test_run_system_normal_mode_host_runtime_reuses_system_mode_helper() -> None:
    runtime = SimpleNamespace(
        god_mode_layout=mock.Mock(side_effect=["ignored", "backmost ok"]),
        _show_live_camera_compact=mock.Mock(return_value="compact ok"),
        _minimize_other_windows=mock.Mock(return_value="minimized ok"),
    )

    out = run_system_normal_mode_host_runtime(runtime=runtime)

    assert out == "backmost ok; compact ok; minimized ok"
    assert runtime.god_mode_layout.call_args_list == [
        mock.call("full-screen"),
        mock.call("backmost"),
    ]
    runtime._show_live_camera_compact.assert_called_once_with()
    runtime._minimize_other_windows.assert_called_once_with()


def test_run_system_world_situation_mode_host_runtime_uses_arrange_script() -> None:
    runtime = SimpleNamespace(
        _world_situation_mode_script_path=mock.Mock(return_value="/tmp/world.sh")
    )

    with mock.patch(
        "arouter.execution.run_arrange_script_host_runtime",
        return_value="world ok",
    ) as helper:
        out = run_system_world_situation_mode_host_runtime(runtime=runtime)

    assert out == "world ok"
    runtime._world_situation_mode_script_path.assert_called_once_with()
    helper.assert_called_once_with(
        script_path="/tmp/world.sh",
        label="world situation mode",
        env=mock.ANY,
    )


def test_run_system_weather_mode_host_runtime_uses_arrange_script() -> None:
    runtime = SimpleNamespace(
        _weather_mode_script_path=mock.Mock(return_value="/tmp/weather.sh")
    )

    with mock.patch(
        "arouter.execution.run_arrange_script_host_runtime",
        return_value="weather mode arranged",
    ) as helper:
        out = run_system_weather_mode_host_runtime(runtime=runtime)

    assert out == "weather mode arranged"
    runtime._weather_mode_script_path.assert_called_once_with()
    helper.assert_called_once_with(
        script_path="/tmp/weather.sh",
        label="weather mode",
        env=mock.ANY,
    )


def test_run_god_mode_layout_host_runtime_tracks_layout_state() -> None:
    runtime = SimpleNamespace(
        _god_mode_last_layout=None,
        _god_mode_layout_script_path=mock.Mock(return_value="/tmp/tmp_main.sh"),
    )

    with mock.patch(
        "arouter.execution.run_tmp_main_layout_host_runtime",
        return_value="god mode ok",
    ) as helper:
        out = run_god_mode_layout_host_runtime(
            runtime=runtime,
            mode="frontmost",
        )

    assert out == "god mode ok"
    assert runtime._god_mode_last_layout == "frontmost"
    runtime._god_mode_layout_script_path.assert_called_once_with()
    helper.assert_called_once_with(
        script_path="/tmp/tmp_main.sh",
        mode="frontmost",
    )


def test_command_has_system_prefix_detects_explicit_prefix() -> None:
    cmd = VoiceCommand("news_live", "システムニュースが見たい", "システム ニュースが見たい")

    assert command_has_system_prefix(cmd) is True


def test_command_has_system_prefix_uses_raw_text_when_normalized_missing() -> None:
    cmd = VoiceCommand("news_live", "", "system news please")

    assert command_has_system_prefix(cmd) is True
