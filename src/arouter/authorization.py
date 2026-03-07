from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import VoiceCommand

UNLOCK_INTENTS = {"good_morning", "system_biometric_auth", "system_password_unlock"}


class AuthorizationRuntime(Protocol):
    _system_locked: bool

    def _ensure_biometric_runtime_attrs(self) -> None: ...

    def _maybe_unlock_from_signal(self) -> bool: ...

    def _maybe_lock_from_signal(self) -> bool: ...

    def _maybe_auto_lock(self) -> None: ...

    def _biometric_lock_enabled(self) -> bool: ...

    def _log_auth_decision(
        self,
        *,
        cmd: VoiceCommand,
        source: str,
        outcome: str,
        detail: str,
    ) -> None: ...

    def _locked_denied_text(self) -> str: ...

    def _verify_unlock_password(self, cmd: VoiceCommand) -> bool: ...

    def _unlock_requires_password_text(self) -> str: ...

    def _set_system_locked(self, locked: bool, *, reason: str) -> None: ...

    def _unlock_requires_live_voice_text(self) -> str: ...

    def _speaker_auth_enabled(self) -> bool: ...

    def _unlock_requires_speaker_auth_text(self) -> str: ...

    def _verify_speaker_identity(
        self,
        wav_path: Path,
        *,
        cmd: VoiceCommand,
        log_label: str,
    ) -> tuple[bool, str | None]: ...

    def _owner_face_recent_for_unlock(self) -> bool: ...

    def _unlock_requires_face_auth_text(self) -> str: ...


def authorize_command(
    runtime: AuthorizationRuntime,
    cmd: VoiceCommand,
    *,
    wav_path: Path | None,
    source: str,
    log_label: str,
) -> tuple[bool, str | None]:
    runtime._ensure_biometric_runtime_attrs()
    runtime._maybe_unlock_from_signal()
    runtime._maybe_lock_from_signal()
    runtime._maybe_auto_lock()
    locked = bool(getattr(runtime, "_system_locked", False))

    if runtime._biometric_lock_enabled() and locked:
        if cmd.intent not in UNLOCK_INTENTS:
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="locked_non_unlock_intent",
            )
            return False, runtime._locked_denied_text()
        if cmd.intent == "system_password_unlock":
            if runtime._verify_unlock_password(cmd):
                runtime._log_auth_decision(
                    cmd=cmd,
                    source=source,
                    outcome="granted",
                    detail="password_unlock",
                )
                runtime._set_system_locked(False, reason=f"unlock:{cmd.intent}:{source}")
                return True, None
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="password_mismatch",
            )
            return False, runtime._unlock_requires_password_text()
        if wav_path is None:
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="unlock_requires_live_voice",
            )
            return False, runtime._unlock_requires_live_voice_text()
        if not runtime._speaker_auth_enabled():
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="speaker_auth_unavailable",
            )
            return False, runtime._unlock_requires_speaker_auth_text()
        ok, err = runtime._verify_speaker_identity(wav_path, cmd=cmd, log_label=log_label)
        if not ok:
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="speaker_auth_failed",
            )
            return False, err
        if not runtime._owner_face_recent_for_unlock():
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="owner_face_missing",
            )
            return False, runtime._unlock_requires_face_auth_text()
        runtime._log_auth_decision(
            cmd=cmd,
            source=source,
            outcome="granted",
            detail="biometric_unlock",
        )
        runtime._set_system_locked(False, reason=f"unlock:{cmd.intent}:{source}")
        return True, None

    if wav_path is not None:
        ok, err = runtime._verify_speaker_identity(wav_path, cmd=cmd, log_label=log_label)
        if not ok:
            runtime._log_auth_decision(
                cmd=cmd,
                source=source,
                outcome="denied",
                detail="speaker_auth_failed_unlocked",
            )
            return False, err

    return True, None
