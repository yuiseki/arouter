from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from .models import VoiceCommand
from .parser import normalize_transcript
from .resolution import resolve_segment_transcript


class CommandExecutionPayload(TypedDict):
    ok: bool
    text: str
    intent: str
    normalized: str
    ackText: str
    result: str


Authorizer = Callable[[VoiceCommand], tuple[bool, str | None]]
Executor = Callable[[VoiceCommand], str]
Contextualizer = Callable[[str, VoiceCommand | None], VoiceCommand | None]
ContextProvider = Callable[[], Mapping[str, object] | None]
Logger = Callable[[str], None]
SuccessRecorder = Callable[[], None]


def contextualize_command_with_vacuumtube_state_host_runtime(
    *,
    runtime: Any,
    text: str,
    cmd: VoiceCommand | None,
) -> VoiceCommand | None:
    logger = runtime.log if callable(getattr(runtime, "log", None)) else (lambda _msg: None)
    return contextualize_command_with_vacuumtube_state(
        text,
        cmd,
        get_context=lambda: runtime._get_vacuumtube_context(
            max_age_sec=3.0,
            refresh_if_stale=True,
        ),
        logger=logger,
    )


def contextualize_command_with_vacuumtube_state(
    text: str,
    cmd: VoiceCommand | None,
    *,
    get_context: ContextProvider,
    logger: Logger,
) -> VoiceCommand | None:
    raw = str(text or "")
    normalized = normalize_transcript(raw)
    if not normalized:
        return cmd

    has_youtube = any(token in normalized for token in ("youtube", "ユーチューブ", "ようつべ"))
    if not has_youtube:
        return cmd

    has_resize_words = any(
        token in normalized
        for token in (
            "全画面",
            "フルスクリーン",
            "大きく",
            "おおきく",
            "最大化",
            "小さく",
            "ちいさく",
            "4分割",
            "四分割",
        )
    )
    has_play_resume_words = any(token in normalized for token in ("再生", "再開"))
    has_explicit_media_subject = any(
        token in normalized
        for token in ("動画", "ビデオ", "ニュース", "音楽", "bgm", "ミュージック")
    )
    if not has_play_resume_words or has_resize_words or has_explicit_media_subject:
        return cmd

    context = get_context()
    if not isinstance(context, Mapping) or not context:
        return cmd

    watch_route = bool(context.get("watchRoute"))
    video_playing = bool(context.get("videoPlaying"))
    video_paused = context.get("videoPaused")
    fullscreenish = bool(context.get("fullscreenish"))

    def rewrite(intent: str, *, reason: str) -> VoiceCommand:
        rewritten = VoiceCommand(
            intent=intent,
            normalized_text=normalize_transcript(raw),
            raw_text=raw,
        )
        try:
            logger(
                "command contextualized: "
                + json.dumps(
                    {
                        "from": None if cmd is None else cmd.intent,
                        "to": intent,
                        "reason": reason,
                        "watchRoute": watch_route,
                        "videoPlaying": video_playing,
                        "videoPaused": video_paused,
                        "fullscreenish": fullscreenish,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass
        return rewritten

    if cmd is None:
        if watch_route and (video_paused is True):
            return rewrite("playback_resume", reason="youtube_ambiguous_play_phrase_while_paused")
        if watch_route and video_playing and not fullscreenish:
            return rewrite(
                "youtube_fullscreen",
                reason="youtube_ambiguous_play_phrase_while_playing_not_fullscreen",
            )
        return cmd

    if cmd.intent == "playback_resume":
        if watch_route and video_playing and not fullscreenish:
            return rewrite(
                "youtube_fullscreen",
                reason="youtube_resume_phrase_impossible_while_already_playing",
            )
        return cmd

    if cmd.intent == "youtube_fullscreen":
        if watch_route and (video_paused is True):
            return rewrite(
                "playback_resume",
                reason="youtube_fullscreen_phrase_improbable_while_paused_watch",
            )
        return cmd

    return cmd


def _allow_all(_cmd: VoiceCommand) -> tuple[bool, str | None]:
    return True, None


def _identity_contextualizer(_text: str, cmd: VoiceCommand | None) -> VoiceCommand | None:
    return cmd


def _noop_logger(_message: str) -> None:
    return None


def _noop_success_recorder() -> None:
    return None


class TextCommandRouter:
    def __init__(
        self,
        *,
        executor: Executor,
        authorizer: Authorizer = _allow_all,
        contextualizer: Contextualizer = _identity_contextualizer,
        logger: Logger = _noop_logger,
        success_recorder: SuccessRecorder = _noop_success_recorder,
    ) -> None:
        self._executor = executor
        self._authorizer = authorizer
        self._contextualizer = contextualizer
        self._logger = logger
        self._success_recorder = success_recorder

    def execute_text_command(self, text: str) -> CommandExecutionPayload:
        raw = " ".join(str(text or "").split())
        if not raw:
            raise RuntimeError("command text is empty")

        resolution = resolve_segment_transcript(
            raw,
            wav_path=None,
            dur_sec=0.0,
            source="cli",
            seg_label="cli command",
            contextualizer=self._contextualizer,
            suppressor=lambda _cmd, _dur_sec: None,
            authorizer=lambda cmd, _wav_path, _source, _seg_label: self._authorizer(cmd),
        )
        cmd = resolution.cmd
        if resolution.outcome == "reaction":
            raise RuntimeError(f"text resolved to reaction only: {resolution.reaction}")
        if resolution.outcome == "ignored":
            raise RuntimeError(f"no mapped command: {raw}")
        if resolution.outcome == "denied":
            raise RuntimeError(resolution.auth_error or "command authorization failed")
        if resolution.outcome != "ready" or cmd is None:
            raise RuntimeError(f"unexpected transcript resolution outcome: {resolution.outcome}")

        result = self._executor(cmd)
        self._success_recorder()
        payload: CommandExecutionPayload = {
            "ok": True,
            "text": raw,
            "intent": cmd.intent,
            "normalized": cmd.normalized_text,
            "ackText": cmd.ack_text,
            "result": result,
        }
        try:
            self._logger("cli command done: " + json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        return payload


def execute_text_command_host_runtime(
    *,
    runtime: Any,
    text: str,
) -> CommandExecutionPayload:
    router = TextCommandRouter(
        executor=runtime._execute_command,
        authorizer=lambda cmd: runtime._authorize_command(
            cmd,
            wav_path=None,
            source="cli",
            log_label="cli command",
        ),
        contextualizer=runtime._contextualize_command_with_vacuumtube_state,
        logger=runtime.log if callable(getattr(runtime, "log", None)) else _noop_logger,
        success_recorder=(
            runtime._record_successful_command_activity
            if callable(getattr(runtime, "_record_successful_command_activity", None))
            else _noop_success_recorder
        ),
    )
    return router.execute_text_command(text)
