from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from arouter import VoiceCommand, authorize_command


def _make_runtime() -> SimpleNamespace:
    runtime = SimpleNamespace()
    runtime._system_locked = False
    runtime.args = SimpleNamespace(
        biometric_unlock_face_retry_ms=0,
        biometric_unlock_face_retry_poll_ms=0,
    )
    runtime._ensure_biometric_runtime_attrs = mock.Mock()
    runtime._maybe_unlock_from_signal = mock.Mock(return_value=False)
    runtime._maybe_lock_from_signal = mock.Mock(return_value=False)
    runtime._maybe_auto_lock = mock.Mock()
    runtime._biometric_lock_enabled = mock.Mock(return_value=True)
    runtime._log_auth_decision = mock.Mock()
    runtime._locked_denied_text = mock.Mock(return_value="ロック中です。解除してください。")
    runtime._verify_unlock_password = mock.Mock(return_value=False)
    runtime._unlock_requires_password_text = mock.Mock(
        return_value="パスワードが違います。もう一度お願いします。"
    )
    runtime._unlock_requires_live_voice_text = mock.Mock(
        return_value="解除には音声コマンドが必要です。"
    )
    runtime._speaker_auth_enabled = mock.Mock(return_value=False)
    runtime._unlock_requires_speaker_auth_text = mock.Mock(
        return_value="声紋認証を利用できません。"
    )
    runtime._verify_speaker_identity = mock.Mock(return_value=(True, None))
    runtime._owner_face_recent_for_unlock = mock.Mock(return_value=True)
    runtime._unlock_requires_face_auth_text = mock.Mock(return_value="顔認証を確認してください。")

    def set_system_locked(locked: bool, *, reason: str) -> None:
        runtime._system_locked = locked
        runtime._last_lock_reason = reason

    runtime._set_system_locked = mock.Mock(side_effect=set_system_locked)
    return runtime


def test_authorize_command_blocks_non_unlock_when_locked() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    cmd = VoiceCommand(
        intent="system_live_camera_show",
        normalized_text="システム街頭カメラ表示",
        raw_text="システム 街頭カメラを表示",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=Path("/tmp/test.wav"),
        source="cli",
        log_label="cli command",
    )

    assert not ok
    assert err == "ロック中です。解除してください。"
    runtime._locked_denied_text.assert_called_once()
    runtime._verify_speaker_identity.assert_not_called()


def test_authorize_command_rejects_unlock_without_live_voice_when_locked() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    cmd = VoiceCommand(
        intent="system_biometric_auth",
        normalized_text="システムバイオメトリクス認証",
        raw_text="システム バイオメトリクス認証",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=None,
        source="cli",
        log_label="cli command",
    )

    assert not ok
    assert err == "解除には音声コマンドが必要です。"
    runtime._unlock_requires_live_voice_text.assert_called_once()


def test_authorize_command_unlocks_when_speaker_and_face_are_valid() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    runtime._speaker_auth_enabled.return_value = True
    cmd = VoiceCommand(
        intent="system_biometric_auth",
        normalized_text="システムバイオメトリクス認証",
        raw_text="システム バイオメトリクス認証",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=Path("/tmp/biometric-test.wav"),
        source="mic",
        log_label="test unlock",
    )

    assert ok
    assert err is None
    assert runtime._system_locked is False
    runtime._set_system_locked.assert_called_once_with(
        False,
        reason="unlock:system_biometric_auth:mic",
    )


def test_authorize_command_rejects_unlock_when_owner_face_is_missing() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    runtime._speaker_auth_enabled.return_value = True
    runtime._owner_face_recent_for_unlock.return_value = False
    cmd = VoiceCommand(
        intent="good_morning",
        normalized_text="システムおはよう",
        raw_text="システム おはよう",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=Path("/tmp/biometric-test.wav"),
        source="mic",
        log_label="test unlock",
    )

    assert not ok
    assert err == "顔認証を確認してください。"
    assert runtime._system_locked is True
    runtime._unlock_requires_face_auth_text.assert_called_once()


def test_authorize_command_retries_face_check_before_unlock_denial() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    runtime._speaker_auth_enabled.return_value = True
    runtime.args.biometric_unlock_face_retry_ms = 500
    runtime.args.biometric_unlock_face_retry_poll_ms = 0
    runtime._owner_face_recent_for_unlock.side_effect = [False, False, True]
    cmd = VoiceCommand(
        intent="system_biometric_auth",
        normalized_text="システムバイオメトリクス認証",
        raw_text="システム バイオメトリクス認証",
    )

    with mock.patch("arouter.authorization.time.monotonic") as mocked_monotonic:
        mocked_monotonic.side_effect = [0.0, 0.0, 0.1, 0.2]
        ok, err = authorize_command(
            runtime,
            cmd,
            wav_path=Path("/tmp/biometric-test.wav"),
            source="mic",
            log_label="test unlock",
        )

    assert ok
    assert err is None
    assert runtime._owner_face_recent_for_unlock.call_count == 3
    runtime._set_system_locked.assert_called_once_with(
        False,
        reason="unlock:system_biometric_auth:mic",
    )


def test_authorize_command_unlocks_with_password_fallback() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    runtime._verify_unlock_password.return_value = True
    cmd = VoiceCommand(
        intent="system_password_unlock",
        normalized_text="システムパスワードパスワード",
        raw_text="システム パスワード パスワード",
        secret_text="パスワード",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=None,
        source="mic",
        log_label="test password unlock",
    )

    assert ok
    assert err is None
    assert runtime._system_locked is False
    runtime._set_system_locked.assert_called_once_with(
        False,
        reason="unlock:system_password_unlock:mic",
    )


def test_authorize_command_rejects_wrong_password() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    cmd = VoiceCommand(
        intent="system_password_unlock",
        normalized_text="システムパスワードちがう",
        raw_text="システム パスワード ちがう",
        secret_text="ちがう",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=None,
        source="mic",
        log_label="test password unlock",
    )

    assert not ok
    assert err == "パスワードが違います。もう一度お願いします。"
    assert runtime._system_locked is True
    runtime._unlock_requires_password_text.assert_called_once()


def test_authorize_command_rejects_when_speaker_auth_is_unavailable() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    cmd = VoiceCommand(
        intent="system_biometric_auth",
        normalized_text="システムバイオメトリクス認証",
        raw_text="システム バイオメトリクス認証",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=Path("/tmp/biometric-test.wav"),
        source="mic",
        log_label="test unlock",
    )

    assert not ok
    assert err == "声紋認証を利用できません。"
    runtime._unlock_requires_speaker_auth_text.assert_called_once()


def test_authorize_command_rejects_unlocked_speaker_auth_failure() -> None:
    runtime = _make_runtime()
    runtime._verify_speaker_identity.return_value = (False, "声紋認証に失敗しました")
    cmd = VoiceCommand(
        intent="system_status_report",
        normalized_text="システム状況報告",
        raw_text="システム 状況報告",
    )

    ok, err = authorize_command(
        runtime,
        cmd,
        wav_path=Path("/tmp/voice.wav"),
        source="mic",
        log_label="command #1",
    )

    assert not ok
    assert err == "声紋認証に失敗しました"
    runtime._log_auth_decision.assert_any_call(
        cmd=cmd,
        source="mic",
        outcome="denied",
        detail="speaker_auth_failed_unlocked",
    )
