from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class EventLike(Protocol):
    def is_set(self) -> bool: ...

    def wait(self, timeout: float) -> bool | None: ...

    def set(self) -> None: ...

    def clear(self) -> None: ...


class ThreadLike(Protocol):
    def is_alive(self) -> bool: ...

    def start(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...


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


def run_biometric_poller_loop(
    *,
    stop_requested: Callable[[], bool],
    stop_event: EventLike,
    interval_sec: float,
    run_iteration: Callable[[], object],
) -> None:
    while not stop_requested() and not stop_event.is_set():
        run_iteration()
        stop_event.wait(interval_sec)


def start_biometric_poller(
    *,
    enabled: bool,
    current_thread: ThreadLike | None,
    stop_event: EventLike,
    thread_factory: Callable[[], ThreadLike],
) -> ThreadLike | None:
    if not enabled:
        return current_thread
    if current_thread and current_thread.is_alive():
        return current_thread
    stop_event.clear()
    thread = thread_factory()
    thread.start()
    return thread


def stop_biometric_poller(
    *,
    stop_event: EventLike,
    current_thread: ThreadLike | None,
    join_timeout_sec: float = 1.5,
) -> None:
    stop_event.set()
    if current_thread and current_thread.is_alive():
        current_thread.join(timeout=join_timeout_sec)
