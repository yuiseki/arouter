from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest import mock

from arouter import (
    default_lock_screen_text,
    default_locked_denied_text,
    maybe_auto_lock,
    maybe_lock_from_signal,
    maybe_unlock_from_signal,
    set_system_locked,
)


def _make_runtime() -> SimpleNamespace:
    runtime = SimpleNamespace()
    runtime._biometric_lock_state_lock = threading.Lock()
    runtime._system_locked = False
    runtime._lock_screen_visible = False
    runtime._last_successful_command_at = time.time()
    runtime.overlay = SimpleNamespace(
        show_lock_screen=mock.Mock(),
        hide_lock_screen=mock.Mock(),
    )
    runtime.lock_overlay = None
    runtime._biometric_lock_enabled = mock.Mock(return_value=True)
    runtime._consume_biometric_unlock_signal = mock.Mock(return_value=False)
    runtime._consume_biometric_lock_signal = mock.Mock(return_value=False)
    runtime._owner_face_absent_for_lock = mock.Mock(return_value=False)
    runtime._record_successful_command_activity = mock.Mock(
        side_effect=lambda: setattr(runtime, "_last_successful_command_at", 999.0)
    )
    runtime._lock_screen_text = mock.Mock(return_value=default_lock_screen_text())
    runtime.log = mock.Mock()
    return runtime


def test_default_lock_screen_text_matches_existing_contract() -> None:
    assert default_lock_screen_text() == "SYSTEM LOCKED\nNeed biometric authentication"


def test_default_locked_denied_text_matches_existing_contract() -> None:
    assert default_locked_denied_text().startswith("現在ロック中です。")


def test_set_system_locked_shows_overlay_when_locking() -> None:
    runtime = _make_runtime()

    changed = set_system_locked(runtime, True, reason="startup")

    assert changed is True
    assert runtime._system_locked is True
    runtime.overlay.show_lock_screen.assert_called_once_with(text=default_lock_screen_text())


def test_set_system_locked_hides_overlay_when_unlocking() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    runtime._lock_screen_visible = True

    changed = set_system_locked(runtime, False, reason="unlock")

    assert changed is True
    assert runtime._system_locked is False
    runtime.overlay.hide_lock_screen.assert_called_once_with()


def test_maybe_unlock_from_signal_clears_lock_and_records_activity() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True
    runtime._consume_biometric_unlock_signal.return_value = True

    changed = maybe_unlock_from_signal(runtime, set_locked=set_system_locked)

    assert changed is True
    assert runtime._system_locked is False
    runtime._record_successful_command_activity.assert_called_once_with()


def test_maybe_lock_from_signal_sets_lock_state() -> None:
    runtime = _make_runtime()
    runtime._consume_biometric_lock_signal.return_value = True

    changed = maybe_lock_from_signal(runtime, set_locked=set_system_locked)

    assert changed is True
    assert runtime._system_locked is True
    runtime.overlay.show_lock_screen.assert_called_once_with(text=default_lock_screen_text())


def test_maybe_auto_lock_requires_idle_and_face_absence() -> None:
    runtime = _make_runtime()
    runtime._last_successful_command_at = time.time() - 3600
    runtime._owner_face_absent_for_lock.return_value = True
    runtime.args = SimpleNamespace(biometric_command_idle_lock_sec=900)

    maybe_auto_lock(runtime, set_locked=set_system_locked)

    assert runtime._system_locked is True
    runtime.overlay.show_lock_screen.assert_called_once_with(text=default_lock_screen_text())


def test_maybe_auto_lock_is_noop_when_face_not_absent() -> None:
    runtime = _make_runtime()
    runtime._last_successful_command_at = time.time() - 3600
    runtime._owner_face_absent_for_lock.return_value = False
    runtime.args = SimpleNamespace(biometric_command_idle_lock_sec=900)

    maybe_auto_lock(runtime, set_locked=set_system_locked)

    assert runtime._system_locked is False
    runtime.overlay.show_lock_screen.assert_not_called()
