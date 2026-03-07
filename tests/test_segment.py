from __future__ import annotations

import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from arouter import process_pcm_segment, process_transcribed_segment


def _make_runtime() -> SimpleNamespace:
    runtime = SimpleNamespace()
    runtime.debug = mock.Mock()
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


def test_process_pcm_segment_skips_too_short_segment() -> None:
    runtime = _make_runtime()
    transcriber = mock.Mock()

    outcome = process_pcm_segment(
        runtime,
        raw_pcm=b"\x00" * 10,
        reason="silence",
        seg_id=1,
        min_segment_bytes=11,
        bytes_per_sample=2,
        sample_rate=16000,
        tmp_dir=Path("/tmp"),
        wav_encoder=lambda raw_pcm: raw_pcm,
        transcriber=transcriber,
        notify_progress=False,
    )

    assert outcome == "too_short"
    runtime.debug.assert_called_once()
    transcriber.assert_not_called()


def test_process_pcm_segment_creates_temp_wav_and_runs_transcriber() -> None:
    runtime = _make_runtime()

    def transcriber(wav_path: Path) -> str:
        assert wav_path.exists()
        assert wav_path.read_bytes() == b"wav-bytes"
        return "システム 状況報告"

    with TemporaryDirectory(prefix="arouter-pcm-test-") as tmp_dir:
        outcome = process_pcm_segment(
            runtime,
            raw_pcm=b"\x00\x01" * 4000,
            reason="silence",
            seg_id=2,
            min_segment_bytes=2,
            bytes_per_sample=2,
            sample_rate=16000,
            tmp_dir=Path(tmp_dir),
            wav_encoder=lambda _raw_pcm: b"wav-bytes",
            transcriber=transcriber,
            notify_progress=False,
        )

        assert outcome == "executed"
        wavs = list(Path(tmp_dir).rglob("*.wav"))
        assert len(wavs) == 1
        assert wavs[0].name.startswith("listen-seg-")


def test_process_pcm_segment_cleans_temp_file_after_transcriber_failure() -> None:
    runtime = _make_runtime()

    with TemporaryDirectory(prefix="arouter-pcm-test-") as tmp_dir:
        temp_paths_before = set(Path("/tmp").glob("listen-seg-*.wav"))
        outcome = process_pcm_segment(
            runtime,
            raw_pcm=b"\x00\x01" * 4000,
            reason="silence",
            seg_id=3,
            min_segment_bytes=2,
            bytes_per_sample=2,
            sample_rate=16000,
            tmp_dir=Path(tmp_dir),
            wav_encoder=lambda _raw_pcm: b"wav-bytes",
            transcriber=mock.Mock(side_effect=RuntimeError("transcriber failed")),
            notify_progress=False,
        )
        temp_paths_after = set(Path("/tmp").glob("listen-seg-*.wav"))

        assert outcome == "error"
        assert temp_paths_after == temp_paths_before
        runtime.notifier.notify.assert_called_once()
        runtime._execute_command.assert_not_called()


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
