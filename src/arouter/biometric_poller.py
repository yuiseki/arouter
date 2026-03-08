from __future__ import annotations

from collections.abc import Callable


def resolve_biometric_poll_interval(
    value: object,
    *,
    default: float = 1.0,
    minimum: float = 0.2,
) -> float:
    try:
        resolved = float(str(value))
    except Exception:
        resolved = default
    return max(minimum, resolved)


def run_biometric_poll_iteration(
    *,
    maybe_unlock_from_signal: Callable[[], object],
    maybe_lock_from_signal: Callable[[], object],
    maybe_auto_lock: Callable[[], object],
    debug: Callable[[str], None],
) -> None:
    try:
        maybe_unlock_from_signal()
        maybe_lock_from_signal()
        maybe_auto_lock()
    except Exception as exc:
        debug(f"biometric poll warning: {exc}")
