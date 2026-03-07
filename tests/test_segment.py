from __future__ import annotations

import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from arouter import process_transcribed_segment


def _make_runtime() -> SimpleNamespace:
    runtime = SimpleNamespace()
    runtime.log = mock.Mock()
    runtime.voice = SimpleNamespace(speak=mock.Mock(return_value=None))
    runtime.notifier = SimpleNamespace(notify=mock.Mock())
    runtime._system_locked = False
    runtime._contextualize_command_with_vacuumtube_state = mock.Mock(
        side_effect=lambda text, cmd: cmd
    )
    runtime._should_suppress_transcribed_command = mock.Mock(return_value=None)
    runtime._authorize_command = mock.Mock(return_value=(True, None))
    runtime._biometric_lock_enabled = mock.Mock(return_value=False)
    runtime._reassert_lock_screen = mock.Mock()
    runtime._should_ack_before_action = mock.Mock(return_value=False)
    runtime._start_ack = mock.Mock()
    runtime._should_wait_ack_before_action = mock.Mock(return_value=False)
    runtime._wait_current_ack = mock.Mock()
    runtime._execute_command = mock.Mock(return_value="system running; normal mode")
    runtime._record_successful_command_activity = mock.Mock()
    runtime._post_action_voice_text = mock.Mock(return_value=None)
    runtime._wait_ack_if_requested = mock.Mock()
    runtime._last_ack_proc = None
    return runtime


def test_process_transcribed_segment_ignores_empty_transcript() -> None:
    runtime = _make_runtime()

    outcome = process_transcribed_segment(
        runtime,
        seg_id=1,
        text="   ",
        stt_elapsed=0.12,
        dur_sec=0.7,
        wav_path=Path("/tmp/test.wav"),
        tmp_wav=Path("/tmp/test.wav"),
        datasets_root=Path("/tmp"),
        now=time.strptime("2026-03-07 23:01:00", "%Y-%m-%d %H:%M:%S"),
        ts="20260307-230100",
        notify_progress=False,
    )

    assert outcome == "empty"
    runtime.log.assert_called_once_with("transcript #1 empty (0.12s)")
    runtime._execute_command.assert_not_called()


def test_process_transcribed_segment_handles_reaction_without_execution() -> None:
    runtime = _make_runtime()

    outcome = process_transcribed_segment(
        runtime,
        seg_id=2,
        text="はっはっ",
        stt_elapsed=0.2,
        dur_sec=0.7,
        wav_path=Path("/tmp/test.wav"),
        tmp_wav=Path("/tmp/test.wav"),
        datasets_root=Path("/tmp"),
        now=time.strptime("2026-03-07 23:02:00", "%Y-%m-%d %H:%M:%S"),
        ts="20260307-230200",
        notify_progress=False,
    )

    assert outcome == "reaction"
    runtime._execute_command.assert_not_called()
    runtime.log.assert_any_call("transcript #2 (0.20s): はっはっ")


def test_process_transcribed_segment_handles_auth_denied() -> None:
    runtime = _make_runtime()
    runtime._authorize_command.return_value = (False, "声紋認証に失敗しました")
    with TemporaryDirectory(prefix="arouter-segment-test-") as tmp_dir:
        tmp_wav = Path(tmp_dir) / "test.wav"
        tmp_wav.write_bytes(b"wav")

        outcome = process_transcribed_segment(
            runtime,
            seg_id=3,
            text="システム 状況報告",
            stt_elapsed=0.3,
            dur_sec=0.7,
            wav_path=tmp_wav,
            tmp_wav=tmp_wav,
            datasets_root=Path(tmp_dir),
            now=time.strptime("2026-03-07 23:03:00", "%Y-%m-%d %H:%M:%S"),
            ts="20260307-230300",
            notify_progress=False,
        )

    assert outcome == "denied"
    runtime.voice.speak.assert_called_once_with("声紋認証に失敗しました", wait=False)
    runtime._execute_command.assert_not_called()


def test_process_transcribed_segment_executes_authorized_command() -> None:
    runtime = _make_runtime()
    with TemporaryDirectory(prefix="arouter-segment-test-") as tmp_dir:
        tmp_wav = Path(tmp_dir) / "test.wav"
        tmp_wav.write_bytes(b"wav")

        outcome = process_transcribed_segment(
            runtime,
            seg_id=4,
            text="システム 状況報告",
            stt_elapsed=0.4,
            dur_sec=0.7,
            wav_path=tmp_wav,
            tmp_wav=tmp_wav,
            datasets_root=Path(tmp_dir),
            now=time.strptime("2026-03-07 23:04:00", "%Y-%m-%d %H:%M:%S"),
            ts="20260307-230400",
            notify_progress=False,
        )

    assert outcome == "executed"
    runtime._execute_command.assert_called_once()
    runtime._record_successful_command_activity.assert_called_once()
    runtime.log.assert_any_call("transcript #4 (0.40s): システム 状況報告")
