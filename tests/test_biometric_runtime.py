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
    reassert_lock_screen,
    run_biometric_owner_face_absent_check,
    run_biometric_owner_face_recent_check,
    run_biometric_status_client_resolution,
    run_biometric_status_fetch,
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


def test_reassert_lock_screen_shows_overlay_when_locked() -> None:
    runtime = _make_runtime()
    runtime._system_locked = True

    changed = reassert_lock_screen(runtime, reason="auth_denied:system_status_report")

    assert changed is True
    assert runtime._lock_screen_visible is True
    runtime.overlay.show_lock_screen.assert_called_once_with(text=default_lock_screen_text())
    runtime.log.assert_called_once_with(
        "system lock overlay reasserted: reason=auth_denied:system_status_report"
    )


def test_reassert_lock_screen_is_noop_when_unlocked() -> None:
    runtime = _make_runtime()

    changed = reassert_lock_screen(runtime, reason="auth_denied:system_status_report")

    assert changed is False
    runtime.overlay.show_lock_screen.assert_not_called()


def test_run_biometric_status_client_resolution_delegates_with_timeout() -> None:
    resolver = mock.Mock(return_value="client")

    client = run_biometric_status_client_resolution(
        current_client=None,
        status_url=" http://127.0.0.1:8765/biometric_status ",
        logger=None,
        resolve_client=resolver,
    )

    assert client == "client"
    resolver.assert_called_once_with(
        current_client=None,
        status_url="http://127.0.0.1:8765/biometric_status",
        logger=None,
        timeout_sec=1.5,
    )


def test_run_biometric_status_fetch_uses_remote_helper_when_available() -> None:
    fetch_remote_status = mock.Mock(return_value=("client", {"ownerPresent": True}))
    fetch_status_from_url = mock.Mock()

    client, status = run_biometric_status_fetch(
        current_client="current",
        status_url=" http://127.0.0.1:8765/biometric_status ",
        logger=None,
        fetch_remote_status=fetch_remote_status,
        fetch_status_from_url=fetch_status_from_url,
    )

    assert client == "client"
    assert status == {"ownerPresent": True}
    fetch_remote_status.assert_called_once_with(
        current_client="current",
        status_url="http://127.0.0.1:8765/biometric_status",
        logger=None,
        timeout_sec=1.5,
    )
    fetch_status_from_url.assert_not_called()


def test_run_biometric_status_fetch_falls_back_to_url_fetch() -> None:
    fetch_status_from_url = mock.Mock(return_value={"ownerPresent": False})

    client, status = run_biometric_status_fetch(
        current_client="current",
        status_url="http://127.0.0.1:8765/biometric_status",
        logger=None,
        fetch_remote_status=None,
        fetch_status_from_url=fetch_status_from_url,
    )

    assert client == "current"
    assert status == {"ownerPresent": False}
    fetch_status_from_url.assert_called_once_with("http://127.0.0.1:8765/biometric_status")


def test_run_biometric_owner_face_absent_check_prefers_client_helper() -> None:
    client = SimpleNamespace(owner_face_absent_for_lock=mock.Mock(return_value=True))
    resolve_client = mock.Mock(return_value=client)
    fetch_remote_status = mock.Mock()
    status_helper = mock.Mock(return_value=False)

    next_client, ok = run_biometric_owner_face_absent_check(
        current_client=None,
        status_url="http://127.0.0.1:8765/biometric_status",
        absent_lock_sec=120,
        logger=None,
        resolve_client=resolve_client,
        fetch_remote_status=fetch_remote_status,
        fetch_status_from_url=None,
        status_helper=status_helper,
    )

    assert next_client is client
    assert ok is True
    client.owner_face_absent_for_lock.assert_called_once_with(absent_lock_sec=120)
    fetch_remote_status.assert_not_called()
    status_helper.assert_not_called()


def test_run_biometric_owner_face_recent_check_falls_back_to_status_helper() -> None:
    resolve_client = mock.Mock(return_value=None)
    fetch_remote_status = mock.Mock(return_value=("client", {"ownerPresent": False}))
    status_helper = mock.Mock(return_value=True)

    next_client, ok = run_biometric_owner_face_recent_check(
        current_client=None,
        status_url="http://127.0.0.1:8765/biometric_status",
        fresh_ms=2000,
        logger=None,
        resolve_client=resolve_client,
        fetch_remote_status=fetch_remote_status,
        fetch_status_from_url=None,
        status_helper=status_helper,
    )

    assert next_client == "client"
    assert ok is True
    status_helper.assert_called_once_with({"ownerPresent": False}, fresh_ms=2000)
