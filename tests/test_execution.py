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


def test_run_system_status_report_host_runtime_closes_weather_pages() -> None:
    runtime = SimpleNamespace(
        vacuumtube=SimpleNamespace(
            close_weather_pages_tiled=mock.Mock(return_value='weather pages closed {"closed":2}')
        )
    )

    out = run_system_status_report_host_runtime(runtime=runtime)

    assert out == 'system running; normal mode; weather pages closed {"closed":2}'
    runtime.vacuumtube.close_weather_pages_tiled.assert_called_once_with()


def test_run_system_status_report_host_runtime_formats_close_error() -> None:
    runtime = SimpleNamespace(
        vacuumtube=SimpleNamespace(
            close_weather_pages_tiled=mock.Mock(side_effect=RuntimeError("boom"))
        )
    )

    out = run_system_status_report_host_runtime(runtime=runtime)

    assert out == "system running; normal mode; weather pages close error: boom"


def test_run_show_weather_pages_today_host_runtime_delegates_to_vacuumtube() -> None:
    runtime = SimpleNamespace(
        vacuumtube=SimpleNamespace(
            open_weather_pages_tiled=mock.Mock(return_value="weather pages tiled []")
        )
    )

    out = run_show_weather_pages_today_host_runtime(runtime=runtime)

    assert out == "weather pages tiled []"
    runtime.vacuumtube.open_weather_pages_tiled.assert_called_once_with()


def test_run_good_morning_host_runtime_uses_news_fullscreen_and_lights() -> None:
    runtime = SimpleNamespace(
        _run_vacuumtube_action=mock.Mock(side_effect=lambda action, **_kwargs: action()),
        vacuumtube=SimpleNamespace(
            play_news=mock.Mock(return_value="news ok"),
            youtube_fullscreen=mock.Mock(return_value="fullscreen ok"),
        ),
    )

    out = run_good_morning_host_runtime(
        runtime=runtime,
        lights_on=lambda: "switchbot lights on: ok",
    )

    assert out == "good_morning news ok fullscreen=fullscreen ok lights=switchbot lights on: ok"
    assert runtime._run_vacuumtube_action.call_count == 2
    runtime.vacuumtube.play_news.assert_called_once_with(slot="morning")
    runtime.vacuumtube.youtube_fullscreen.assert_called_once_with()


def test_run_good_night_host_runtime_uses_pause_and_lights_off() -> None:
    runtime = SimpleNamespace(
        vacuumtube=SimpleNamespace(
            good_night_pause=mock.Mock(return_value='good_night pause {"ok": true}')
        )
    )

    out = run_good_night_host_runtime(
        runtime=runtime,
        lights_off=lambda: "switchbot lights off: ok",
    )

    assert out == 'good_night pause {"ok": true} lights=switchbot lights off: ok'
    runtime.vacuumtube.good_night_pause.assert_called_once_with()


def test_run_system_live_camera_show_host_runtime_tracks_layout_and_calls_show_full() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        live_cam_wall=SimpleNamespace(show_full=mock.Mock(return_value="show ok")),
    )

    out = run_system_live_camera_show_host_runtime(runtime=runtime)

    assert out == "show ok"
    assert runtime._live_cam_last_layout == "show"
    runtime.live_cam_wall.show_full.assert_called_once_with()


def test_run_system_live_camera_compact_host_runtime_tracks_layout_and_calls_show_compact() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        live_cam_wall=SimpleNamespace(show_compact=mock.Mock(return_value="compact ok")),
    )

    out = run_system_live_camera_compact_host_runtime(runtime=runtime)

    assert out == "compact ok"
    assert runtime._live_cam_last_layout == "compact"
    runtime.live_cam_wall.show_compact.assert_called_once_with()


def test_run_system_live_camera_hide_host_runtime_tracks_layout_and_calls_hide() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        live_cam_wall=SimpleNamespace(hide=mock.Mock(return_value="hide ok")),
    )

    out = run_system_live_camera_hide_host_runtime(runtime=runtime)

    assert out == "hide ok"
    assert runtime._live_cam_last_layout == "hide"
    runtime.live_cam_wall.hide.assert_called_once_with()


def test_run_system_street_camera_mode_host_runtime_reuses_show_helper() -> None:
    called: list[str] = []

    out = run_system_street_camera_mode_host_runtime(
        show_live_camera=lambda: called.append("show") or "show ok"
    )

    assert out == "show ok"
    assert called == ["show"]


def test_run_system_webcam_mode_host_runtime_tracks_layout_and_reuses_system_mode_helper() -> None:
    runtime = SimpleNamespace(
        _live_cam_last_layout=None,
        live_cam_wall=SimpleNamespace(minimize=mock.Mock(return_value="street minimized")),
        god_mode_layout=mock.Mock(return_value="webcam ok"),
    )

    out = run_system_webcam_mode_host_runtime(runtime=runtime)

    assert out == "street minimized; webcam ok"
    assert runtime._live_cam_last_layout == "hide"
    runtime.live_cam_wall.minimize.assert_called_once_with()
    runtime.god_mode_layout.assert_called_once_with("frontmost")


def test_run_system_normal_mode_host_runtime_reuses_system_mode_helper() -> None:
    runtime = SimpleNamespace(
        god_mode_layout=mock.Mock(side_effect=["ignored", "backmost ok"]),
        live_cam_wall=SimpleNamespace(show_compact=mock.Mock(return_value="compact ok")),
        _minimize_other_windows=mock.Mock(return_value="minimized ok"),
    )

    out = run_system_normal_mode_host_runtime(runtime=runtime)

    assert out == "backmost ok; compact ok; minimized ok"
    assert runtime.god_mode_layout.call_args_list == [
        mock.call("full-screen"),
        mock.call("backmost"),
    ]
    runtime.live_cam_wall.show_compact.assert_called_once_with()
    runtime._minimize_other_windows.assert_called_once_with()


def test_run_system_world_situation_mode_host_runtime_uses_arrange_script() -> None:
    run_command = mock.Mock(
        return_value=SimpleNamespace(returncode=0, stdout="world ok\n", stderr="")
    )

    out = run_system_world_situation_mode_host_runtime(
        script_path="/tmp/world.sh",
        path_exists=lambda _path: True,
        run_command=run_command,
    )

    assert out == "world ok"
    run_command.assert_called_once_with(["bash", "/tmp/world.sh"])


def test_run_system_weather_mode_host_runtime_uses_arrange_script() -> None:
    run_command = mock.Mock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))

    out = run_system_weather_mode_host_runtime(
        script_path="/tmp/weather.sh",
        path_exists=lambda _path: True,
        run_command=run_command,
    )

    assert out == "weather mode arranged"
    run_command.assert_called_once_with(["bash", "/tmp/weather.sh"])


def test_run_god_mode_layout_host_runtime_tracks_layout_state() -> None:
    runtime = SimpleNamespace(_god_mode_last_layout=None)

    out = run_god_mode_layout_host_runtime(
        runtime=runtime,
        mode="frontmost",
        run_layout=lambda: "god mode ok",
    )

    assert out == "god mode ok"
    assert runtime._god_mode_last_layout == "frontmost"


def test_command_has_system_prefix_detects_explicit_prefix() -> None:
    cmd = VoiceCommand("news_live", "システムニュースが見たい", "システム ニュースが見たい")

    assert command_has_system_prefix(cmd) is True


def test_command_has_system_prefix_uses_raw_text_when_normalized_missing() -> None:
    cmd = VoiceCommand("news_live", "", "system news please")

    assert command_has_system_prefix(cmd) is True
