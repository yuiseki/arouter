from __future__ import annotations

from pathlib import Path
from unittest import mock

from arouter import VoiceCommand, resolve_segment_transcript


def test_resolve_segment_transcript_returns_reaction_when_no_command_maps() -> None:
    out = resolve_segment_transcript(
        "はっはっ",
        wav_path=Path("/tmp/test.wav"),
        dur_sec=0.7,
        source="mic",
        seg_label="command #1",
        contextualizer=lambda text, cmd: cmd,
        suppressor=lambda cmd, dur_sec: None,
        authorizer=lambda cmd, wav_path, source, log_label: (True, None),
    )

    assert out.outcome == "reaction"
    assert out.reaction == "laugh"
    assert out.cmd is None


def test_resolve_segment_transcript_returns_ignored_when_no_command_maps() -> None:
    out = resolve_segment_transcript(
        "えーとですね",
        wav_path=Path("/tmp/test.wav"),
        dur_sec=0.7,
        source="mic",
        seg_label="command #2",
        contextualizer=lambda text, cmd: cmd,
        suppressor=lambda cmd, dur_sec: None,
        authorizer=lambda cmd, wav_path, source, log_label: (True, None),
    )

    assert out.outcome == "ignored"
    assert out.cmd is None


def test_resolve_segment_transcript_returns_suppressed_reason() -> None:
    suppressor = mock.Mock(return_value="cooldown")

    out = resolve_segment_transcript(
        "システム 状況報告",
        wav_path=Path("/tmp/test.wav"),
        dur_sec=0.7,
        source="mic",
        seg_label="command #3",
        contextualizer=lambda text, cmd: cmd,
        suppressor=suppressor,
        authorizer=lambda cmd, wav_path, source, log_label: (True, None),
    )

    assert out.outcome == "suppressed"
    assert out.cmd is not None
    assert out.cmd.intent == "system_status_report"
    assert out.suppressed_reason == "cooldown"
    suppressor.assert_called_once()


def test_resolve_segment_transcript_returns_denied_auth_error() -> None:
    authorizer = mock.Mock(return_value=(False, "声紋認証に失敗しました"))

    out = resolve_segment_transcript(
        "システム 状況報告",
        wav_path=Path("/tmp/test.wav"),
        dur_sec=0.7,
        source="mic",
        seg_label="command #4",
        contextualizer=lambda text, cmd: cmd,
        suppressor=lambda cmd, dur_sec: None,
        authorizer=authorizer,
    )

    assert out.outcome == "denied"
    assert out.cmd is not None
    assert out.auth_error == "声紋認証に失敗しました"
    authorizer.assert_called_once()


def test_resolve_segment_transcript_returns_ready_authorized_command() -> None:
    contextualizer = mock.Mock(
        side_effect=lambda _text, _cmd: VoiceCommand(
            intent="system_status_report",
            normalized_text="システム状況報告",
            raw_text="システム 状況報告",
        )
    )
    authorizer = mock.Mock(return_value=(True, None))

    out = resolve_segment_transcript(
        "システム 状況報告",
        wav_path=Path("/tmp/test.wav"),
        dur_sec=0.7,
        source="mic",
        seg_label="command #5",
        contextualizer=contextualizer,
        suppressor=lambda cmd, dur_sec: None,
        authorizer=authorizer,
    )

    assert out.outcome == "ready"
    assert out.cmd is not None
    assert out.cmd.intent == "system_status_report"
    assert out.auth_error is None
    contextualizer.assert_called_once()
    authorizer.assert_called_once()
