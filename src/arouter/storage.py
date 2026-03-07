from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Protocol

from .models import VoiceCommand


class AuthorizationFailureRuntime(Protocol):
    voice: Any
    _system_locked: bool

    def _biometric_lock_enabled(self) -> bool: ...

    def _reassert_lock_screen(self, *, reason: str) -> None: ...


def _segment_minute_dir(*, datasets_root: Path, now: time.struct_time) -> Path:
    return (
        datasets_root
        / time.strftime("%Y", now)
        / time.strftime("%m", now)
        / time.strftime("%d", now)
        / time.strftime("%H", now)
        / time.strftime("%M", now)
    )


def store_authorized_wav(
    *,
    tmp_wav: Path,
    datasets_root: Path,
    now: time.struct_time,
    ts: str,
    seg_id: int,
) -> Path:
    target_dir = _segment_minute_dir(datasets_root=datasets_root, now=now)
    target_dir.mkdir(parents=True, exist_ok=True)
    final_wav = target_dir / f"listen-seg-{ts}-{seg_id:04d}.wav"
    shutil.move(str(tmp_wav), str(final_wav))
    return final_wav


def store_authfail_wav(
    *,
    tmp_wav: Path,
    datasets_root: Path,
    now: time.struct_time,
    ts: str,
    seg_id: int,
) -> Path:
    target_dir = _segment_minute_dir(datasets_root=datasets_root, now=now)
    target_dir.mkdir(parents=True, exist_ok=True)
    authfail_wav = target_dir / f"authfail-listen-seg-{ts}-{seg_id:04d}.wav"
    shutil.move(str(tmp_wav), str(authfail_wav))
    return authfail_wav


def handle_authorization_denied(
    runtime: AuthorizationFailureRuntime,
    *,
    tmp_wav: Path,
    datasets_root: Path,
    now: time.struct_time,
    ts: str,
    seg_id: int,
    cmd: VoiceCommand,
    auth_error: str | None,
) -> Path:
    authfail_wav = store_authfail_wav(
        tmp_wav=tmp_wav,
        datasets_root=datasets_root,
        now=now,
        ts=ts,
        seg_id=seg_id,
    )
    should_reassert_lock = runtime._biometric_lock_enabled() and bool(
        getattr(runtime, "_system_locked", False)
    )
    runtime.voice.speak(auth_error or "認証に失敗しました。", wait=should_reassert_lock)
    if should_reassert_lock:
        runtime._reassert_lock_screen(reason=f"auth_denied:{cmd.intent}")
    return authfail_wav
