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


def resolve_vacuumtube_context_poll_interval(
    value: object,
    *,
    default: float = 2.5,
    minimum: float = 0.5,
) -> float:
    try:
        resolved = float(str(value))
    except Exception:
        resolved = default
    return max(minimum, resolved)


def run_vacuumtube_context_poller_loop(
    *,
    stop_requested: Callable[[], bool],
    stop_event: EventLike,
    interval_sec: float,
    refresh_context: Callable[[], object],
) -> None:
    while not stop_requested() and not stop_event.is_set():
        try:
            refresh_context()
        except Exception:
            pass
        stop_event.wait(interval_sec)


def start_vacuumtube_context_poller(
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


def stop_vacuumtube_context_poller(
    *,
    stop_event: EventLike,
    current_thread: ThreadLike | None,
    join_timeout_sec: float = 1.5,
) -> None:
    stop_event.set()
    if current_thread and current_thread.is_alive():
        current_thread.join(timeout=join_timeout_sec)
