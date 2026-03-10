from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from .desktop_runtime import (
    run_arrange_script_host_runtime,
    run_tmp_main_layout_host_runtime,
)
from .models import VoiceCommand
from .parser import normalize_transcript
from .system_modes import run_system_normal_mode, run_system_webcam_mode


class VacuumTubeRuntime(Protocol):
    def play_bgm(self) -> str: ...

    def stop_music(self) -> str: ...

    def resume_playback(self) -> str: ...

    def youtube_fullscreen(self) -> str: ...

    def youtube_quadrant(self) -> str: ...

    def youtube_minimize(self) -> str: ...

    def go_youtube_home(self) -> str: ...

    def play_news(self, *, slot: str) -> str: ...


class CommandRuntime(Protocol):
    vacuumtube: VacuumTubeRuntime
    _god_mode_last_layout: str | None
    _live_cam_last_layout: str | None

    def _run_vacuumtube_action(
        self,
        action: Callable[[], str],
        *,
        label: str,
    ) -> str: ...

    def _get_vacuumtube_context(
        self,
        *,
        max_age_sec: float = 3.0,
        refresh_if_stale: bool = True,
    ) -> Mapping[str, object]: ...

    def _set_system_locked(self, locked: bool, *, reason: str) -> bool: ...

    def system_status_report(self) -> str: ...

    def system_weather_today(self) -> str: ...

    def show_weather_pages_today(self) -> str: ...

    def system_live_camera_show(self) -> str: ...

    def system_live_camera_compact(self) -> str: ...

    def system_live_camera_hide(self) -> str: ...

    def system_normal_mode(self) -> str: ...

    def system_world_situation_mode(self) -> str: ...

    def system_weather_mode(self) -> str: ...

    def system_street_camera_mode(self) -> str: ...

    def system_webcam_mode(self) -> str: ...

    def god_mode_layout(self, mode: str) -> str: ...

    def system_load_check(self) -> str: ...

    def good_morning(self) -> str: ...

    def good_night(self) -> str: ...

    def log(self, msg: str) -> None: ...


def command_has_system_prefix(cmd: VoiceCommand) -> bool:
    normalized = str(cmd.normalized_text or "")
    if not normalized:
        normalized = normalize_transcript(cmd.raw_text or "")
    return ("システム" in normalized) or ("system" in normalized)


def execute_news_command(runtime: CommandRuntime, cmd: VoiceCommand, *, slot: str) -> str:
    result = runtime._run_vacuumtube_action(
        lambda: runtime.vacuumtube.play_news(slot=slot),
        label=f"news_{slot}",
    )
    if not command_has_system_prefix(cmd):
        return result
    try:
        fullscreen = runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_fullscreen,
            label=f"news_{slot}_fullscreen",
        )
    except Exception as exc:
        runtime.log(f"news fullscreen skipped after successful playback: {exc}")
        return result
    return f"{result}; {fullscreen}"


def run_system_status_report(
    *,
    close_weather_pages_tiled: Callable[[], str],
) -> str:
    try:
        close_result = close_weather_pages_tiled()
    except Exception as exc:
        close_result = f"weather pages close error: {exc}"
    return f"system running; normal mode; {close_result}"


def run_system_status_report_host_runtime(*, runtime: Any) -> str:
    return run_system_status_report(
        close_weather_pages_tiled=runtime.vacuumtube.close_weather_pages_tiled,
    )


def run_show_weather_pages_today_host_runtime(*, runtime: Any) -> str:
    return str(runtime.vacuumtube.open_weather_pages_tiled())


def run_good_morning(
    *,
    play_morning_news: Callable[[], str],
    fullscreen_news: Callable[[], str],
    lights_on: Callable[[], str],
) -> str:
    news_result = play_morning_news()
    fullscreen_result = fullscreen_news()
    try:
        lights_result = lights_on()
    except Exception as exc:
        lights_result = f"switchbot error: {exc}"
    return f"good_morning {news_result} fullscreen={fullscreen_result} lights={lights_result}"


def run_good_morning_host_runtime(
    *,
    runtime: Any,
) -> str:
    return run_good_morning(
        play_morning_news=lambda: runtime._run_vacuumtube_action(
            lambda: runtime.vacuumtube.play_news(slot="morning"),
            label="good_morning_news",
        ),
        fullscreen_news=lambda: runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_fullscreen,
            label="good_morning_fullscreen",
        ),
        lights_on=runtime._lights_on,
    )


def run_good_night(
    *,
    pause_for_night: Callable[[], str],
    lights_off: Callable[[], str],
) -> str:
    result = pause_for_night()
    try:
        lights_result = lights_off()
    except Exception as exc:
        lights_result = f"switchbot error: {exc}"
    return f"{result} lights={lights_result}"


def run_good_night_host_runtime(
    *,
    runtime: Any,
    lights_off: Callable[[], str],
) -> str:
    return run_good_night(
        pause_for_night=runtime.vacuumtube.good_night_pause,
        lights_off=lights_off,
    )


def run_system_live_camera_show_host_runtime(*, runtime: Any) -> str:
    runtime._live_cam_last_layout = "show"
    return str(runtime.live_cam_wall.show_full())


def run_system_live_camera_compact_host_runtime(*, runtime: Any) -> str:
    runtime._live_cam_last_layout = "compact"
    return str(runtime.live_cam_wall.show_compact())


def run_system_live_camera_hide_host_runtime(*, runtime: Any) -> str:
    runtime._live_cam_last_layout = "hide"
    return str(runtime.live_cam_wall.hide())


def run_system_street_camera_mode_host_runtime(
    *,
    runtime: Any,
) -> str:
    return str(runtime.system_live_camera_show())


def run_system_webcam_mode_host_runtime(*, runtime: Any) -> str:
    runtime._live_cam_last_layout = "hide"
    return run_system_webcam_mode(
        minimize_live_camera=runtime.live_cam_wall.minimize,
        god_mode_layout=runtime.god_mode_layout,
    )


def run_system_normal_mode_host_runtime(*, runtime: Any) -> str:
    return run_system_normal_mode(
        god_mode_layout=runtime.god_mode_layout,
        show_live_camera_compact=runtime.live_cam_wall.show_compact,
        minimize_other_windows=runtime._minimize_other_windows,
    )


def run_system_world_situation_mode_host_runtime(
    *,
    script_path: str,
) -> str:
    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY") or ":0"
    return run_arrange_script_host_runtime(
        script_path=script_path,
        label="world situation mode",
        env=env,
    )


def run_system_weather_mode_host_runtime(
    *,
    script_path: str,
) -> str:
    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY") or ":0"
    return run_arrange_script_host_runtime(
        script_path=script_path,
        label="weather mode",
        env=env,
    )


def run_god_mode_layout_host_runtime(
    *,
    runtime: Any,
    mode: str,
    script_path: str,
) -> str:
    result = run_tmp_main_layout_host_runtime(
        script_path=script_path,
        mode=mode,
    )
    runtime._god_mode_last_layout = mode
    return result


def execute_command(runtime: CommandRuntime, cmd: VoiceCommand) -> str:
    if cmd.intent == "playback_resume":
        context = runtime._get_vacuumtube_context(max_age_sec=5.0, refresh_if_stale=False)
        raw_normalized = normalize_transcript(cmd.raw_text or "")
        if (
            isinstance(context, Mapping)
            and bool(context.get("watchRoute"))
            and bool(context.get("videoPlaying"))
            and any(token in raw_normalized for token in ("youtube", "ユーチューブ", "ようつべ"))
        ):
            return "youtube already playing (context no-op)"

    if cmd.intent == "music_play":
        return runtime._run_vacuumtube_action(runtime.vacuumtube.play_bgm, label="music_play")
    if cmd.intent == "music_stop":
        return runtime._run_vacuumtube_action(runtime.vacuumtube.stop_music, label="music_stop")
    if cmd.intent == "playback_resume":
        return runtime._run_vacuumtube_action(
            runtime.vacuumtube.resume_playback,
            label="playback_resume",
        )
    if cmd.intent == "playback_stop":
        return runtime._run_vacuumtube_action(runtime.vacuumtube.stop_music, label="playback_stop")
    if cmd.intent == "news_live":
        return execute_news_command(runtime, cmd, slot="generic")
    if cmd.intent == "news_morning":
        return execute_news_command(runtime, cmd, slot="morning")
    if cmd.intent == "news_evening":
        return execute_news_command(runtime, cmd, slot="evening")
    if cmd.intent == "youtube_fullscreen":
        context = runtime._get_vacuumtube_context(max_age_sec=5.0, refresh_if_stale=False)
        if isinstance(context, Mapping) and bool(context.get("fullscreenish")):
            return "youtube fullscreen already active (context no-op)"
        return runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_fullscreen,
            label="youtube_fullscreen",
        )
    if cmd.intent == "youtube_quadrant":
        context = runtime._get_vacuumtube_context(max_age_sec=5.0, refresh_if_stale=False)
        if isinstance(context, Mapping) and bool(context.get("quadrantish")):
            return "youtube quadrant already active (context no-op)"
        return runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_quadrant,
            label="youtube_quadrant",
        )
    if cmd.intent == "youtube_minimize":
        return runtime._run_vacuumtube_action(
            runtime.vacuumtube.youtube_minimize,
            label="youtube_minimize",
        )
    if cmd.intent == "youtube_home":
        return runtime._run_vacuumtube_action(
            runtime.vacuumtube.go_youtube_home,
            label="youtube_home",
        )
    if cmd.intent == "system_status_report":
        return runtime.system_status_report()
    if cmd.intent == "system_weather_today":
        return runtime.system_weather_today()
    if cmd.intent == "weather_pages_today":
        return runtime.show_weather_pages_today()
    if cmd.intent == "system_live_camera_show":
        return runtime.system_live_camera_show()
    if cmd.intent == "system_live_camera_compact":
        return runtime.system_live_camera_compact()
    if cmd.intent == "system_live_camera_hide":
        return runtime.system_live_camera_hide()
    if cmd.intent == "system_normal_mode":
        return runtime.system_normal_mode()
    if cmd.intent == "system_world_situation_mode":
        return runtime.system_world_situation_mode()
    if cmd.intent == "system_weather_mode":
        return runtime.system_weather_mode()
    if cmd.intent == "system_lock_mode":
        runtime._set_system_locked(True, reason="command:system_lock_mode")
        return "system locked by command"
    if cmd.intent == "system_street_camera_mode":
        return runtime.system_street_camera_mode()
    if cmd.intent == "system_webcam_mode":
        return runtime.system_webcam_mode()
    if cmd.intent == "god_mode_show":
        return runtime.god_mode_layout("frontmost")
    if cmd.intent == "god_mode_fullscreen":
        god_already_full = getattr(runtime, "_god_mode_last_layout", None) in (
            "full-screen",
            "frontmost",
        )
        if god_already_full:
            return runtime.system_live_camera_show()
        return runtime.god_mode_layout("full-screen")
    if cmd.intent == "god_mode_compact":
        god_is_big = getattr(runtime, "_god_mode_last_layout", None) in (
            "full-screen",
            "frontmost",
        )
        live_is_full = getattr(runtime, "_live_cam_last_layout", None) == "show"
        if god_is_big and live_is_full:
            return runtime.system_live_camera_compact()
        return runtime.god_mode_layout("left-bottom")
    if cmd.intent == "god_mode_background":
        return runtime.god_mode_layout("backmost")
    if cmd.intent == "system_load_check":
        return runtime.system_load_check()
    if cmd.intent == "system_biometric_auth":
        normal_mode_result = runtime.system_normal_mode()
        return f"system unlocked by biometric authentication; {normal_mode_result}"
    if cmd.intent == "system_password_unlock":
        return "system unlocked by password fallback"
    if cmd.intent == "good_morning":
        return runtime.good_morning()
    if cmd.intent == "good_night":
        return runtime.good_night()
    raise RuntimeError(f"unsupported intent: {cmd.intent}")
