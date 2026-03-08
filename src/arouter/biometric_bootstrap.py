from __future__ import annotations

from collections.abc import Callable
from typing import Any


def ensure_biometric_runtime_attrs(
    runtime: Any,
    *,
    now: Callable[[], float],
    lock_factory: Callable[[], Any],
    event_factory: Callable[[], Any],
    seed_lock_seen_mtime: Callable[[], float],
    seed_unlock_seen_mtime: Callable[[], float],
) -> None:
    if not hasattr(runtime, "_biometric_lock_state_lock"):
        runtime._biometric_lock_state_lock = lock_factory()
    if not hasattr(runtime, "_system_locked"):
        runtime._system_locked = False
    if not hasattr(runtime, "_lock_screen_visible"):
        runtime._lock_screen_visible = False
    if not hasattr(runtime, "_last_successful_command_at"):
        runtime._last_successful_command_at = now()
    if not hasattr(runtime, "_biometric_poll_stop_event"):
        runtime._biometric_poll_stop_event = event_factory()
    if not hasattr(runtime, "_biometric_poll_thread"):
        runtime._biometric_poll_thread = None
    if not hasattr(runtime, "_biometric_password_candidates_cache"):
        runtime._biometric_password_candidates_cache = None
    if not hasattr(runtime, "_biometric_status_client"):
        runtime._biometric_status_client = None
    if not hasattr(runtime, "_biometric_lock_signal_seen_mtime"):
        runtime._biometric_lock_signal_seen_mtime = seed_lock_seen_mtime()
    if not hasattr(runtime, "_biometric_unlock_signal_seen_mtime"):
        runtime._biometric_unlock_signal_seen_mtime = seed_unlock_seen_mtime()
