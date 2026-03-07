from __future__ import annotations

import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from arouter import VoiceCommand, handle_authorization_denied, store_authorized_wav


def test_store_authorized_wav_moves_into_minute_partition() -> None:
    now = time.strptime("2026-03-07 22:41:00", "%Y-%m-%d %H:%M:%S")
    with tempfile.TemporaryDirectory(prefix="arouter-storage-test-") as tmp_dir:
        datasets_root = Path(tmp_dir)
        tmp_wav = datasets_root / "tmp.wav"
        tmp_wav.write_bytes(b"wav")

        final_wav = store_authorized_wav(
            tmp_wav=tmp_wav,
            datasets_root=datasets_root,
            now=now,
            ts="20260307-224100",
            seg_id=12,
        )

        assert final_wav.exists()
        assert final_wav.name == "listen-seg-20260307-224100-0012.wav"
        assert final_wav.parent == datasets_root / "2026" / "03" / "07" / "22" / "41"
        assert not tmp_wav.exists()


def test_handle_authorization_denied_moves_authfail_wav_and_speaks_error() -> None:
    now = time.strptime("2026-03-07 22:42:00", "%Y-%m-%d %H:%M:%S")
    with tempfile.TemporaryDirectory(prefix="arouter-authfail-test-") as tmp_dir:
        datasets_root = Path(tmp_dir)
        tmp_wav = datasets_root / "tmp.wav"
        tmp_wav.write_bytes(b"wav")
        runtime = SimpleNamespace(
            voice=SimpleNamespace(speak=mock.Mock(return_value=None)),
            _system_locked=False,
            _biometric_lock_enabled=mock.Mock(return_value=False),
            _reassert_lock_screen=mock.Mock(),
        )
        cmd = VoiceCommand(
            intent="system_status_report",
            normalized_text="システム状況報告",
            raw_text="システム 状況報告",
        )

        authfail_wav = handle_authorization_denied(
            runtime,
            tmp_wav=tmp_wav,
            datasets_root=datasets_root,
            now=now,
            ts="20260307-224200",
            seg_id=13,
            cmd=cmd,
            auth_error="声紋認証に失敗しました",
        )

        assert authfail_wav.exists()
        assert authfail_wav.name == "authfail-listen-seg-20260307-224200-0013.wav"
        runtime.voice.speak.assert_called_once_with("声紋認証に失敗しました", wait=False)
        runtime._reassert_lock_screen.assert_not_called()


def test_handle_authorization_denied_reasserts_lock_screen_when_locked() -> None:
    now = time.strptime("2026-03-07 22:43:00", "%Y-%m-%d %H:%M:%S")
    with tempfile.TemporaryDirectory(prefix="arouter-authfail-test-") as tmp_dir:
        datasets_root = Path(tmp_dir)
        tmp_wav = datasets_root / "tmp.wav"
        tmp_wav.write_bytes(b"wav")
        runtime = SimpleNamespace(
            voice=SimpleNamespace(speak=mock.Mock(return_value=None)),
            _system_locked=True,
            _biometric_lock_enabled=mock.Mock(return_value=True),
            _reassert_lock_screen=mock.Mock(),
        )
        cmd = VoiceCommand(
            intent="system_live_camera_show",
            normalized_text="システム街頭カメラを表示",
            raw_text="システム 街頭カメラを表示",
        )

        handle_authorization_denied(
            runtime,
            tmp_wav=tmp_wav,
            datasets_root=datasets_root,
            now=now,
            ts="20260307-224300",
            seg_id=14,
            cmd=cmd,
            auth_error=None,
        )

        runtime.voice.speak.assert_called_once_with("認証に失敗しました。", wait=True)
        runtime._reassert_lock_screen.assert_called_once_with(
            reason="auth_denied:system_live_camera_show"
        )
