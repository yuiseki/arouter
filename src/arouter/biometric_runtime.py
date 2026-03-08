from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol


class LockRuntime(Protocol):
    _system_locked: bool
    _lock_screen_visible: bool
    _last_successful_command_at: float
    args: Any
    lock_overlay: Any | None
    overlay: Any | None

    def _biometric_lock_enabled(self) -> bool: ...

    def _consume_biometric_unlock_signal(self) -> bool: ...

    def _consume_biometric_lock_signal(self) -> bool: ...

    def _owner_face_absent_for_lock(self) -> bool: ...

    def _record_successful_command_activity(self) -> None: ...

    def _lock_screen_text(self) -> str: ...

    def log(self, msg: str) -> None: ...


def default_lock_screen_text() -> str:
    return "SYSTEM LOCKED\nNeed biometric authentication"


def default_locked_denied_text() -> str:
    return (
        "現在ロック中です。"
        "システム、おはよう、システム、バイオメトリクス認証、"
        "またはシステム、パスワードで解除してください。"
    )


def set_system_locked(runtime: LockRuntime, locked: bool, *, reason: str) -> bool:
    previous = bool(runtime._system_locked)
    runtime._system_locked = bool(locked)
    changed = previous != bool(locked)
    lock_client = getattr(runtime, "lock_overlay", None) or getattr(runtime, "overlay", None)
    try:
        if runtime._system_locked:
            if changed or not bool(getattr(runtime, "_lock_screen_visible", False)):
                show = getattr(lock_client, "show_lock_screen", None)
                if callable(show):
                    show(text=runtime._lock_screen_text())
                runtime._lock_screen_visible = True
        else:
            if changed or bool(getattr(runtime, "_lock_screen_visible", False)):
                hide = getattr(lock_client, "hide_lock_screen", None)
                if callable(hide):
                    hide()
                runtime._lock_screen_visible = False
    except Exception as exc:
        runtime.log(f"biometric lock overlay update failed ({reason}): {exc}")
    if changed:
        runtime.log(f"system lock state changed: locked={runtime._system_locked} reason={reason}")
    return changed


def maybe_unlock_from_signal(
    runtime: LockRuntime,
    *,
    set_locked: Callable[..., bool],
) -> bool:
    if not runtime._biometric_lock_enabled() or not bool(getattr(runtime, "_system_locked", False)):
        return False
    if not runtime._consume_biometric_unlock_signal():
        return False
    runtime.log("biometric unlock signal consumed")
    changed = set_locked(runtime, False, reason="unlock:overlay_password")
    runtime._record_successful_command_activity()
    return changed


def maybe_lock_from_signal(
    runtime: LockRuntime,
    *,
    set_locked: Callable[..., bool],
) -> bool:
    if not runtime._biometric_lock_enabled() or bool(getattr(runtime, "_system_locked", False)):
        return False
    if not runtime._consume_biometric_lock_signal():
        return False
    runtime.log("biometric lock signal consumed")
    return set_locked(runtime, True, reason="manual_signal")


def maybe_auto_lock(
    runtime: LockRuntime,
    *,
    set_locked: Callable[..., bool],
) -> None:
    if not runtime._biometric_lock_enabled() or bool(getattr(runtime, "_system_locked", False)):
        return
    idle_sec = time.time() - float(getattr(runtime, "_last_successful_command_at", time.time()))
    idle_threshold = max(
        0,
        int(getattr(getattr(runtime, "args", None), "biometric_command_idle_lock_sec", 900)),
    )
    if idle_sec < idle_threshold:
        return
    if not runtime._owner_face_absent_for_lock():
        return
    set_locked(runtime, True, reason="idle_timeout")
