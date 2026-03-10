from __future__ import annotations

from unittest import mock

import pytest

from arouter import (
    TextCommandRouter,
    VoiceCommand,
    contextualize_command_with_vacuumtube_state,
    contextualize_command_with_vacuumtube_state_host_runtime,
    detect_non_command_reaction,
)


def test_execute_text_command_parses_and_dispatches_once() -> None:
    executor = mock.Mock(return_value="live camera wall ok")
    router = TextCommandRouter(executor=executor, logger=mock.Mock())

    payload = router.execute_text_command(" システム 街頭カメラを表示 ")

    assert payload["ok"] is True
    assert payload["intent"] == "system_live_camera_show"
    assert payload["normalized"] == "システム街頭カメラを表示"
    assert payload["result"] == "live camera wall ok"
    executor.assert_called_once()


def test_execute_text_command_raises_for_unmapped_text() -> None:
    executor = mock.Mock()
    router = TextCommandRouter(
        executor=executor,
        contextualizer=lambda _text, _cmd: None,
        logger=mock.Mock(),
    )

    with pytest.raises(RuntimeError, match="no mapped command"):
        router.execute_text_command("これは未対応です")

    executor.assert_not_called()


def test_execute_text_command_raises_for_reaction_only_text() -> None:
    executor = mock.Mock()
    router = TextCommandRouter(executor=executor, logger=mock.Mock())

    with pytest.raises(RuntimeError, match="reaction only: laugh"):
        router.execute_text_command("はっはっ")

    executor.assert_not_called()


def test_contextualize_command_inferrs_youtube_fullscreen_from_ambiguous_play_phrase() -> None:
    context_provider = mock.Mock(
        return_value={
            "watchRoute": True,
            "videoPlaying": True,
            "videoPaused": False,
            "fullscreenish": False,
            "quadrantish": True,
        }
    )

    out = contextualize_command_with_vacuumtube_state(
        "YouTubeを再生して",
        None,
        get_context=context_provider,
        logger=mock.Mock(),
    )

    assert out is not None
    assert out.intent == "youtube_fullscreen"
    context_provider.assert_called_once()


def test_contextualize_command_rewrites_youtube_resume_to_fullscreen_when_already_playing() -> None:
    context_provider = mock.Mock(
        return_value={
            "watchRoute": True,
            "videoPlaying": True,
            "videoPaused": False,
            "fullscreenish": False,
        }
    )
    cmd = VoiceCommand(
        intent="playback_resume",
        normalized_text="youtubeを再開して",
        raw_text="YouTubeを再開して",
    )

    out = contextualize_command_with_vacuumtube_state(
        "YouTubeを再開して",
        cmd,
        get_context=context_provider,
        logger=mock.Mock(),
    )

    assert out is not None
    assert out.intent == "youtube_fullscreen"


def test_contextualize_command_keeps_youtube_resume_when_paused() -> None:
    context_provider = mock.Mock(
        return_value={
            "watchRoute": True,
            "videoPlaying": False,
            "videoPaused": True,
            "fullscreenish": False,
        }
    )
    cmd = VoiceCommand(
        intent="playback_resume",
        normalized_text="youtubeを再開して",
        raw_text="YouTubeを再開して",
    )

    out = contextualize_command_with_vacuumtube_state(
        "YouTubeを再開して",
        cmd,
        get_context=context_provider,
        logger=mock.Mock(),
    )

    assert out is not None
    assert out.intent == "playback_resume"


def test_contextualize_command_host_runtime_uses_runtime_context() -> None:
    runtime = mock.Mock()
    runtime._get_vacuumtube_context.return_value = {
        "watchRoute": True,
        "videoPlaying": True,
        "videoPaused": False,
        "fullscreenish": False,
    }
    cmd = VoiceCommand(
        intent="playback_resume",
        normalized_text="youtubeを再開して",
        raw_text="YouTubeを再開して",
    )

    out = contextualize_command_with_vacuumtube_state_host_runtime(
        runtime=runtime,
        text="YouTubeを再開して",
        cmd=cmd,
    )

    assert out is not None
    assert out.intent == "youtube_fullscreen"
    runtime._get_vacuumtube_context.assert_called_once_with(
        max_age_sec=3.0,
        refresh_if_stale=True,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("はっはっ", "laugh"),
        ("ハッ、ハッ", "laugh"),
        ("はっ", None),
        ("(笑)", None),
    ],
)
def test_detect_non_command_reaction(text: str, expected: str | None) -> None:
    assert detect_non_command_reaction(text) == expected
