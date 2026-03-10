from __future__ import annotations

from unittest import mock

from arouter import (
    resolve_vacuumtube_context_poll_interval,
    run_vacuumtube_context_poller_loop,
    run_vacuumtube_context_poller_loop_host_runtime,
    start_vacuumtube_context_poller,
    start_vacuumtube_context_poller_host_runtime,
    stop_vacuumtube_context_poller,
)


class DummyEvent:
    def __init__(self) -> None:
        self.set_calls = 0
        self.clear_calls = 0
        self.wait_calls: list[float] = []
        self._is_set = False

    def is_set(self) -> bool:
        return self._is_set

    def wait(self, timeout: float) -> bool:
        self.wait_calls.append(timeout)
        self._is_set = True
        return True

    def set(self) -> None:
        self.set_calls += 1
        self._is_set = True

    def clear(self) -> None:
        self.clear_calls += 1
        self._is_set = False


class DummyThread:
    def __init__(self, *, alive: bool = False) -> None:
        self._alive = alive
        self.started = 0
        self.joined: list[float | None] = []

    def is_alive(self) -> bool:
        return self._alive

    def start(self) -> None:
        self.started += 1
        self._alive = True

    def join(self, timeout: float | None = None) -> None:
        self.joined.append(timeout)
        self._alive = False


def test_resolve_vacuumtube_context_poll_interval_clamps_low_values() -> None:
    assert resolve_vacuumtube_context_poll_interval(0.1) == 0.5


def test_resolve_vacuumtube_context_poll_interval_falls_back_on_invalid_value() -> None:
    assert resolve_vacuumtube_context_poll_interval("invalid") == 2.5


def test_run_vacuumtube_context_poller_loop_refreshes_until_stop() -> None:
    event = DummyEvent()
    calls: list[str] = []

    run_vacuumtube_context_poller_loop(
        stop_requested=lambda: False,
        stop_event=event,
        interval_sec=1.5,
        refresh_context=lambda: calls.append("refresh"),
    )

    assert calls == ["refresh"]
    assert event.wait_calls == [1.5]


def test_run_vacuumtube_context_poller_loop_host_runtime_uses_runtime_refresh() -> None:
    event = DummyEvent()
    runtime = type(
        "Runtime",
        (),
        {
            "stop_requested": False,
            "_refresh_vacuumtube_context_cache": staticmethod(
                lambda *, reason: calls.append(reason)
            ),
        },
    )()
    calls: list[str] = []

    run_vacuumtube_context_poller_loop_host_runtime(
        runtime=runtime,
        stop_event=event,
        interval_sec=1.5,
    )

    assert calls == ["poll"]
    assert event.wait_calls == [1.5]


def test_start_vacuumtube_context_poller_returns_existing_alive_thread() -> None:
    event = DummyEvent()
    current = DummyThread(alive=True)

    result = start_vacuumtube_context_poller(
        enabled=True,
        current_thread=current,
        stop_event=event,
        thread_factory=lambda: DummyThread(),
    )

    assert result is current
    assert event.clear_calls == 0


def test_start_vacuumtube_context_poller_starts_new_thread() -> None:
    event = DummyEvent()

    result = start_vacuumtube_context_poller(
        enabled=True,
        current_thread=None,
        stop_event=event,
        thread_factory=lambda: DummyThread(),
    )

    assert result is not None
    assert result.started == 1
    assert event.clear_calls == 1


def test_start_vacuumtube_context_poller_host_runtime_builds_runtime_thread() -> None:
    event = DummyEvent()
    runtime = mock.Mock()
    fake_thread = DummyThread()

    with mock.patch(
        "arouter.vacuumtube_poller.threading.Thread",
        return_value=fake_thread,
    ) as thread_factory:
        result = start_vacuumtube_context_poller_host_runtime(
            runtime=runtime,
            current_thread=None,
            stop_event=event,
        )

    assert result is fake_thread
    assert fake_thread.started == 1
    assert event.clear_calls == 1
    thread_factory.assert_called_once_with(
        target=runtime._vacuumtube_context_poller,
        name="vacuumtube-context-poller",
        daemon=True,
    )


def test_stop_vacuumtube_context_poller_sets_event_and_joins() -> None:
    event = DummyEvent()
    thread = DummyThread(alive=True)

    stop_vacuumtube_context_poller(
        stop_event=event,
        current_thread=thread,
    )

    assert event.set_calls == 1
    assert thread.joined == [1.5]
