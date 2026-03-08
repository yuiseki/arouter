from __future__ import annotations

from types import SimpleNamespace

from arouter import ensure_biometric_runtime_attrs


def test_ensure_biometric_runtime_attrs_populates_missing_fields() -> None:
    runtime = SimpleNamespace()
    lock = object()
    event = object()

    ensure_biometric_runtime_attrs(
        runtime,
        now=lambda: 123.0,
        lock_factory=lambda: lock,
        event_factory=lambda: event,
        seed_lock_seen_mtime=lambda: 10.0,
        seed_unlock_seen_mtime=lambda: 20.0,
    )

    assert runtime._biometric_lock_state_lock is lock
    assert runtime._system_locked is False
    assert runtime._lock_screen_visible is False
    assert runtime._last_successful_command_at == 123.0
    assert runtime._biometric_poll_stop_event is event
    assert runtime._biometric_poll_thread is None
    assert runtime._biometric_password_candidates_cache is None
    assert runtime._biometric_status_client is None
    assert runtime._biometric_lock_signal_seen_mtime == 10.0
    assert runtime._biometric_unlock_signal_seen_mtime == 20.0


def test_ensure_biometric_runtime_attrs_preserves_existing_fields() -> None:
    runtime = SimpleNamespace(
        _biometric_lock_state_lock="existing-lock",
        _system_locked=True,
        _lock_screen_visible=True,
        _last_successful_command_at=456.0,
        _biometric_poll_stop_event="existing-event",
        _biometric_poll_thread="existing-thread",
        _biometric_password_candidates_cache=["secret"],
        _biometric_status_client="existing-client",
        _biometric_lock_signal_seen_mtime=30.0,
        _biometric_unlock_signal_seen_mtime=40.0,
    )

    ensure_biometric_runtime_attrs(
        runtime,
        now=lambda: 999.0,
        lock_factory=lambda: object(),
        event_factory=lambda: object(),
        seed_lock_seen_mtime=lambda: 11.0,
        seed_unlock_seen_mtime=lambda: 22.0,
    )

    assert runtime._biometric_lock_state_lock == "existing-lock"
    assert runtime._system_locked is True
    assert runtime._lock_screen_visible is True
    assert runtime._last_successful_command_at == 456.0
    assert runtime._biometric_poll_stop_event == "existing-event"
    assert runtime._biometric_poll_thread == "existing-thread"
    assert runtime._biometric_password_candidates_cache == ["secret"]
    assert runtime._biometric_status_client == "existing-client"
    assert runtime._biometric_lock_signal_seen_mtime == 30.0
    assert runtime._biometric_unlock_signal_seen_mtime == 40.0
