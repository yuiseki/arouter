from __future__ import annotations

from unittest import mock

from arouter import (
    resolve_biometric_poll_interval,
    run_biometric_poll_iteration,
    run_biometric_poller_loop,
    start_biometric_poller,
    stop_biometric_poller,
)


class _FakeEvent:
    def __init__(self, *, is_set: bool = False) -> None:
        self._is_set = is_set
        self.wait_calls: list[float] = []
        self.set_calls = 0
        self.clear_calls = 0

    def is_set(self) -> bool:
        return self._is_set

    def wait(self, timeout: float) -> bool:
        self.wait_calls.append(timeout)
        return self._is_set

    def set(self) -> None:
        self.set_calls += 1
        self._is_set = True

    def clear(self) -> None:
        self.clear_calls += 1
        self._is_set = False


class _FakeThread:
    def __init__(self, *, alive: bool = False) -> None:
        self._alive = alive
        self.start_calls = 0
        self.join_calls: list[float | None] = []

    def is_alive(self) -> bool:
        return self._alive

    def start(self) -> None:
        self.start_calls += 1
        self._alive = True

    def join(self, timeout: float | None = None) -> None:
        self.join_calls.append(timeout)
        self._alive = False


def test_resolve_biometric_poll_interval_returns_value_when_valid() -> None:
    assert resolve_biometric_poll_interval(0.75) == 0.75


def test_resolve_biometric_poll_interval_clamps_to_minimum() -> None:
    assert resolve_biometric_poll_interval(0.05) == 0.2


def test_resolve_biometric_poll_interval_falls_back_to_default_on_invalid_input() -> None:
    assert resolve_biometric_poll_interval("invalid") == 1.0


def test_run_biometric_poll_iteration_calls_steps_in_order() -> None:
    events: list[str] = []

    run_biometric_poll_iteration(
        maybe_unlock_from_signal=lambda: events.append("unlock"),
        maybe_lock_from_signal=lambda: events.append("lock"),
        maybe_auto_lock=lambda: events.append("auto_lock"),
        debug=lambda _msg: None,
    )

    assert events == ["unlock", "lock", "auto_lock"]


def test_run_biometric_poll_iteration_logs_warning_and_stops_cycle_on_error() -> None:
    maybe_lock = mock.Mock()
    maybe_auto_lock = mock.Mock()
    logs: list[str] = []

    run_biometric_poll_iteration(
        maybe_unlock_from_signal=mock.Mock(side_effect=RuntimeError("boom")),
        maybe_lock_from_signal=maybe_lock,
        maybe_auto_lock=maybe_auto_lock,
        debug=logs.append,
    )

    maybe_lock.assert_not_called()
    maybe_auto_lock.assert_not_called()
    assert logs == ["biometric poll warning: boom"]


def test_run_biometric_poller_loop_runs_single_cycle_then_waits() -> None:
    stop_requested = mock.Mock(side_effect=[False, True])
    stop_event = _FakeEvent()
    run_iteration = mock.Mock()

    run_biometric_poller_loop(
        stop_requested=stop_requested,
        stop_event=stop_event,
        interval_sec=0.75,
        run_iteration=run_iteration,
    )

    run_iteration.assert_called_once_with()
    assert stop_event.wait_calls == [0.75]


def test_run_biometric_poller_loop_skips_when_stop_event_already_set() -> None:
    stop_event = _FakeEvent(is_set=True)
    run_iteration = mock.Mock()

    run_biometric_poller_loop(
        stop_requested=mock.Mock(return_value=False),
        stop_event=stop_event,
        interval_sec=0.75,
        run_iteration=run_iteration,
    )

    run_iteration.assert_not_called()
    assert stop_event.wait_calls == []


def test_start_biometric_poller_starts_new_thread_when_enabled() -> None:
    stop_event = _FakeEvent(is_set=True)
    thread = _FakeThread()
    thread_factory = mock.Mock(return_value=thread)

    started = start_biometric_poller(
        enabled=True,
        current_thread=None,
        stop_event=stop_event,
        thread_factory=thread_factory,
    )

    assert started is thread
    assert stop_event.clear_calls == 1
    thread_factory.assert_called_once_with()
    assert thread.start_calls == 1


def test_start_biometric_poller_keeps_existing_alive_thread() -> None:
    stop_event = _FakeEvent()
    thread = _FakeThread(alive=True)
    thread_factory = mock.Mock()

    started = start_biometric_poller(
        enabled=True,
        current_thread=thread,
        stop_event=stop_event,
        thread_factory=thread_factory,
    )

    assert started is thread
    assert stop_event.clear_calls == 0
    thread_factory.assert_not_called()
    assert thread.start_calls == 0


def test_start_biometric_poller_noops_when_disabled() -> None:
    stop_event = _FakeEvent()
    thread_factory = mock.Mock()

    started = start_biometric_poller(
        enabled=False,
        current_thread=None,
        stop_event=stop_event,
        thread_factory=thread_factory,
    )

    assert started is None
    assert stop_event.clear_calls == 0
    thread_factory.assert_not_called()


def test_stop_biometric_poller_sets_event_and_joins_alive_thread() -> None:
    stop_event = _FakeEvent()
    thread = _FakeThread(alive=True)

    stop_biometric_poller(
        stop_event=stop_event,
        current_thread=thread,
        join_timeout_sec=2.0,
    )

    assert stop_event.set_calls == 1
    assert thread.join_calls == [2.0]


def test_stop_biometric_poller_skips_join_for_dead_thread() -> None:
    stop_event = _FakeEvent()
    thread = _FakeThread(alive=False)

    stop_biometric_poller(stop_event=stop_event, current_thread=thread)

    assert stop_event.set_calls == 1
    assert thread.join_calls == []
