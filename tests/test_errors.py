from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest import mock

from arouter import VoiceCommand, report_segment_error


def _make_runtime() -> SimpleNamespace:
    return SimpleNamespace(
        log=mock.Mock(),
        notifier=SimpleNamespace(notify=mock.Mock()),
        _speak_action_error=mock.Mock(),
    )


def test_report_segment_error_handles_called_process_error() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(intent="youtube_home", normalized_text="", raw_text="")
    exc = subprocess.CalledProcessError(
        returncode=7,
        cmd=["fake"],
        stderr="boom",
    )

    report_segment_error(runtime, seg_id=9, exc=exc, cmd=cmd)

    runtime.log.assert_called_once_with("segment #9 error (subprocess exit=7): boom")
    runtime.notifier.notify.assert_called_once_with(
        "音声コマンド エラー",
        "subprocess exit=7 boom",
        urgency="critical",
    )
    runtime._speak_action_error.assert_called_once_with()


def test_report_segment_error_handles_generic_exception() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(intent="youtube_home", normalized_text="", raw_text="")

    report_segment_error(runtime, seg_id=10, exc=RuntimeError("VacuumTube failed"), cmd=cmd)

    runtime.log.assert_called_once_with("segment #10 error: VacuumTube failed")
    runtime.notifier.notify.assert_called_once_with(
        "音声コマンド エラー",
        "VacuumTube failed",
        urgency="critical",
    )
    runtime._speak_action_error.assert_called_once_with()


def test_report_segment_error_skips_action_error_voice_when_command_unresolved() -> None:
    runtime = _make_runtime()

    report_segment_error(runtime, seg_id=11, exc=RuntimeError("ignored"), cmd=None)

    runtime.notifier.notify.assert_called_once_with(
        "音声コマンド エラー",
        "ignored",
        urgency="critical",
    )
    runtime._speak_action_error.assert_not_called()
