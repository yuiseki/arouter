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


def run_biometric_status_client_resolution(
    *,
    current_client: Any | None,
    status_url: str,
    logger: Callable[[str], None] | None,
    resolve_client: Callable[..., Any | None],
) -> Any | None:
    return resolve_client(
        current_client=current_client,
        status_url=str(status_url or "").strip(),
        logger=logger,
        timeout_sec=1.5,
    )


def run_biometric_status_fetch(
    *,
    current_client: Any | None,
    status_url: str,
    logger: Callable[[str], None] | None,
    fetch_remote_status: Callable[..., tuple[Any | None, dict[str, Any] | None]] | None,
    fetch_status_from_url: Callable[[str], dict[str, Any] | None] | None,
) -> tuple[Any | None, dict[str, Any] | None]:
    resolved_url = str(status_url or "").strip()
    if callable(fetch_remote_status):
        client, status = fetch_remote_status(
            current_client=current_client,
            status_url=resolved_url,
            logger=logger,
            timeout_sec=1.5,
        )
        return client, status if isinstance(status, dict) else None
    if not resolved_url or not callable(fetch_status_from_url):
        return current_client, None
    status = fetch_status_from_url(resolved_url)
    return current_client, status if isinstance(status, dict) else None


def run_biometric_owner_face_absent_check(
    *,
    current_client: Any | None,
    status_url: str,
    absent_lock_sec: int,
    logger: Callable[[str], None] | None,
    resolve_client: Callable[..., Any | None] | None,
    fetch_remote_status: Callable[..., tuple[Any | None, dict[str, Any] | None]] | None,
    fetch_status_from_url: Callable[[str], dict[str, Any] | None] | None,
    status_helper: Callable[..., bool],
) -> tuple[Any | None, bool]:
    threshold_sec = max(0, int(absent_lock_sec))
    client = current_client
    if callable(resolve_client):
        client = run_biometric_status_client_resolution(
            current_client=current_client,
            status_url=status_url,
            logger=logger,
            resolve_client=resolve_client,
        )
        helper = getattr(client, "owner_face_absent_for_lock", None)
        if callable(helper):
            try:
                return client, bool(helper(absent_lock_sec=threshold_sec))
            except Exception:
                return client, False
    client, status = run_biometric_status_fetch(
        current_client=client,
        status_url=status_url,
        logger=logger,
        fetch_remote_status=fetch_remote_status,
        fetch_status_from_url=fetch_status_from_url,
    )
    return client, bool(status_helper(status, absent_lock_sec=threshold_sec))


def run_biometric_owner_face_recent_check(
    *,
    current_client: Any | None,
    status_url: str,
    fresh_ms: int,
    logger: Callable[[str], None] | None,
    resolve_client: Callable[..., Any | None] | None,
    fetch_remote_status: Callable[..., tuple[Any | None, dict[str, Any] | None]] | None,
    fetch_status_from_url: Callable[[str], dict[str, Any] | None] | None,
    status_helper: Callable[..., bool],
) -> tuple[Any | None, bool]:
    threshold_ms = max(0, int(fresh_ms))
    client = current_client
    if callable(resolve_client):
        client = run_biometric_status_client_resolution(
            current_client=current_client,
            status_url=status_url,
            logger=logger,
            resolve_client=resolve_client,
        )
        helper = getattr(client, "owner_face_recent_for_unlock", None)
        if callable(helper):
            try:
                return client, bool(helper(fresh_ms=threshold_ms))
            except Exception:
                return client, False
    client, status = run_biometric_status_fetch(
        current_client=client,
        status_url=status_url,
        logger=logger,
        fetch_remote_status=fetch_remote_status,
        fetch_status_from_url=fetch_status_from_url,
    )
    return client, bool(status_helper(status, fresh_ms=threshold_ms))


def run_biometric_password_candidate_load(
    *,
    cached_candidates: list[str] | None,
    args: Any,
    debug: Callable[[str], None],
    log: Callable[[str], None],
    resolve_path: Callable[..., Any],
    load_candidates: Callable[..., list[str]],
    encrypted_default_path: str,
    private_key_default_path: str,
) -> list[str]:
    if isinstance(cached_candidates, list):
        return list(cached_candidates)
    encrypted_path = resolve_path(
        args=args,
        attr_name="biometric_password_file",
        default_path=encrypted_default_path,
    )
    private_key_path = resolve_path(
        args=args,
        attr_name="biometric_password_private_key",
        default_path=private_key_default_path,
    )
    return list(
        load_candidates(
            encrypted_path=encrypted_path,
            private_key_path=private_key_path,
            debug=debug,
            log=log,
        )
    )


def run_biometric_signal_consume(
    *,
    args: Any,
    attr_name: str,
    default_path: str,
    seen_mtime: float,
    resolve_path: Callable[..., Any],
    consume_signal: Callable[..., tuple[bool, float]],
) -> tuple[bool, float]:
    signal_path = resolve_path(
        args=args,
        attr_name=attr_name,
        default_path=default_path,
    )
    return consume_signal(
        signal_path=signal_path,
        seen_mtime=float(seen_mtime),
    )


def record_successful_command_activity(
    runtime: Any,
    *,
    now: Callable[[], float] = time.time,
) -> None:
    runtime._last_successful_command_at = now()


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


def reassert_lock_screen(runtime: LockRuntime, *, reason: str) -> bool:
    if not runtime._biometric_lock_enabled() or not bool(getattr(runtime, "_system_locked", False)):
        return False
    lock_client = getattr(runtime, "lock_overlay", None) or getattr(runtime, "overlay", None)
    try:
        show = getattr(lock_client, "show_lock_screen", None)
        if callable(show):
            show(text=runtime._lock_screen_text())
        runtime._lock_screen_visible = True
        runtime.log(f"system lock overlay reasserted: reason={reason}")
        return True
    except Exception as exc:
        runtime.log(f"biometric lock overlay reassert failed ({reason}): {exc}")
        return False


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
