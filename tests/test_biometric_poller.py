from __future__ import annotations

from unittest import mock

from arouter import resolve_biometric_poll_interval, run_biometric_poll_iteration


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
