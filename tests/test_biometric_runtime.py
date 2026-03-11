from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest import mock

from arouter import (
    biometric_lock_enabled,
    biometric_unlock_success_text,
    default_lock_screen_text,
    default_locked_denied_text,
    maybe_auto_lock,
    maybe_lock_from_signal,
    maybe_unlock_from_signal,
    reassert_lock_screen,
    record_successful_command_activity,
    run_biometric_owner_face_absent_check,
    run_biometric_owner_face_absent_runtime_check,
    run_biometric_owner_face_recent_check,
    run_biometric_owner_face_recent_runtime_check,
    run_biometric_password_candidate_load,
    run_biometric_signal_consume,
    run_biometric_status_client_get,
    run_biometric_status_client_resolution,
    run_biometric_status_fetch,
    run_biometric_status_runtime_fetch,
    run_biometric_status_url_fetch,
    set_system_locked,
    unlock_requires_face_auth_text,
    unlock_requires_live_voice_text,
    unlock_requires_password_text,
    unlock_requires_speaker_auth_text,
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


def test_biometric_lock_enabled_reads_flag_from_args() -> None:
    assert biometric_lock_enabled(SimpleNamespace(biometric_lock=True)) is True
    assert biometric_lock_enabled(SimpleNamespace(biometric_lock=False)) is False


def test_unlock_text_helpers_match_existing_contracts() -> None:
    assert unlock_requires_live_voice_text().startswith("ロック解除には実際の音声入力が必要です。")
    assert unlock_requires_speaker_auth_text() == (
        "声紋認証が利用できないため、ロックを解除できません。"
    )
    assert unlock_requires_face_auth_text() == (
        "顔認証を確認できませんでした。カメラの前で、もう一度お試しください。"
    )
    assert unlock_requires_password_text() == (
        "パスワード認証に失敗しました。もう一度お試しください。"
    )
    assert biometric_unlock_success_text() == (
        "バイオメトリクス認証に成功しました。おかえりなさい、ユイさま"
    )


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


def test_maybe_auto_lock_defaults_to_30_minutes_when_arg_missing() -> None:
    runtime = _make_runtime()
    runtime._last_successful_command_at = time.time() - 1700
    runtime._owner_face_absent_for_lock.return_value = True
    runtime.args = SimpleNamespace()

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


def test_run_biometric_status_runtime_fetch_uses_args_and_returns_updated_client() -> None:
    fetch_remote_status = mock.Mock(return_value=("next", {"ownerPresent": True}))

    client, status = run_biometric_status_runtime_fetch(
        current_client="current",
        args=SimpleNamespace(god_mode_status_url=" http://127.0.0.1:8765/biometric_status "),
        logger=None,
        client_available=True,
        fetch_remote_status=fetch_remote_status,
        fetch_status_from_url=mock.Mock(),
    )

    assert client == "next"
    assert status == {"ownerPresent": True}
    fetch_remote_status.assert_called_once_with(
        current_client="current",
        status_url="http://127.0.0.1:8765/biometric_status",
        logger=None,
        timeout_sec=1.5,
    )


def test_run_biometric_status_client_get_returns_current_client_when_cached() -> None:
    resolver = mock.Mock()

    client = run_biometric_status_client_get(
        current_client="cached",
        client_available=True,
        status_url="http://127.0.0.1:8765/biometric_status",
        logger=None,
        resolve_client=resolver,
    )

    assert client == "cached"
    resolver.assert_not_called()


def test_run_biometric_status_client_get_uses_resolver_when_available() -> None:
    resolver = mock.Mock(return_value="client")

    client = run_biometric_status_client_get(
        current_client=None,
        client_available=True,
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


def test_run_biometric_status_url_fetch_returns_dict_payload() -> None:
    request_builder = mock.Mock(return_value="request")
    response = mock.Mock()
    response.__enter__ = mock.Mock(return_value=response)
    response.__exit__ = mock.Mock(return_value=False)
    response.read.return_value = b'{"ownerPresent": true}'
    urlopen = mock.Mock(return_value=response)

    status = run_biometric_status_url_fetch(
        status_url=" http://127.0.0.1:8765/biometric_status ",
        debug=mock.Mock(),
        request_builder=request_builder,
        urlopen=urlopen,
        json_loads=lambda raw: {"ownerPresent": True} if raw else None,
    )

    assert status == {"ownerPresent": True}
    request_builder.assert_called_once_with(
        "http://127.0.0.1:8765/biometric_status",
        headers={"Accept": "application/json"},
    )
    urlopen.assert_called_once_with("request", timeout=1.5)


def test_run_biometric_status_url_fetch_logs_and_returns_none_on_error() -> None:
    debug = mock.Mock()
    urlopen = mock.Mock(side_effect=RuntimeError("boom"))

    status = run_biometric_status_url_fetch(
        status_url="http://127.0.0.1:8765/biometric_status",
        debug=debug,
        request_builder=mock.Mock(return_value="request"),
        urlopen=urlopen,
        json_loads=lambda raw: {"ownerPresent": True},
    )

    assert status is None
    debug.assert_called_once_with("god mode biometric status fetch failed: boom")


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


def test_run_biometric_owner_face_absent_runtime_check_uses_default_status_helper() -> None:
    fetch_status_from_url = mock.Mock(
        return_value={"ownerPresent": False, "ownerSeenAgoMs": 150_000}
    )

    next_client, ok = run_biometric_owner_face_absent_runtime_check(
        current_client=None,
        args=SimpleNamespace(
            biometric_face_absent_lock_sec=120,
            god_mode_status_url=" http://127.0.0.1:8765/biometric_status ",
        ),
        logger=None,
        client_available=False,
        resolve_client=None,
        fetch_remote_status=None,
        fetch_status_from_url=fetch_status_from_url,
        status_helper=None,
    )

    assert next_client is None
    assert ok is True
    fetch_status_from_url.assert_called_once_with("http://127.0.0.1:8765/biometric_status")


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


def test_run_biometric_owner_face_recent_runtime_check_uses_default_status_helper() -> None:
    fetch_status_from_url = mock.Mock(
        return_value={"ownerPresent": False, "ownerSeenAgoMs": 1_000}
    )

    next_client, ok = run_biometric_owner_face_recent_runtime_check(
        current_client=None,
        args=SimpleNamespace(
            biometric_unlock_face_fresh_ms=2_000,
            god_mode_status_url=" http://127.0.0.1:8765/biometric_status ",
        ),
        logger=None,
        client_available=False,
        resolve_client=None,
        fetch_remote_status=None,
        fetch_status_from_url=fetch_status_from_url,
        status_helper=None,
    )

    assert next_client is None
    assert ok is True
    fetch_status_from_url.assert_called_once_with("http://127.0.0.1:8765/biometric_status")


def test_run_biometric_password_candidate_load_returns_cached_copy() -> None:
    cached = ["secret"]

    candidates = run_biometric_password_candidate_load(
        cached_candidates=cached,
        args=SimpleNamespace(),
        debug=lambda _msg: None,
        log=lambda _msg: None,
        resolve_path=mock.Mock(),
        load_candidates=mock.Mock(),
        encrypted_default_path="/tmp/password.enc",
        private_key_default_path="/tmp/id_rsa",
    )

    assert candidates == ["secret"]
    assert candidates is not cached


def test_run_biometric_password_candidate_load_resolves_paths_and_loads() -> None:
    encrypted_path = "/tmp/password.enc"
    private_key_path = "/tmp/id_rsa"
    resolve_path = mock.Mock(side_effect=[encrypted_path, private_key_path])
    load_candidates = mock.Mock(return_value=["secret"])
    args = SimpleNamespace()

    candidates = run_biometric_password_candidate_load(
        cached_candidates=None,
        args=args,
        debug=lambda _msg: None,
        log=lambda _msg: None,
        resolve_path=resolve_path,
        load_candidates=load_candidates,
        encrypted_default_path="/tmp/password.enc",
        private_key_default_path="/tmp/id_rsa",
    )

    assert candidates == ["secret"]
    assert resolve_path.call_args_list == [
        mock.call(
            args=args,
            attr_name="biometric_password_file",
            default_path="/tmp/password.enc",
        ),
        mock.call(
            args=args,
            attr_name="biometric_password_private_key",
            default_path="/tmp/id_rsa",
        ),
    ]
    load_candidates.assert_called_once_with(
        encrypted_path=encrypted_path,
        private_key_path=private_key_path,
        debug=mock.ANY,
        log=mock.ANY,
    )


def test_run_biometric_signal_consume_resolves_path_and_delegates() -> None:
    resolve_path = mock.Mock(return_value="/tmp/unlock.signal")
    consume_signal = mock.Mock(return_value=(True, 5.0))
    args = SimpleNamespace()

    consumed, seen_mtime = run_biometric_signal_consume(
        args=args,
        attr_name="biometric_unlock_signal_file",
        default_path="/tmp/unlock.signal",
        seen_mtime=1.0,
        resolve_path=resolve_path,
        consume_signal=consume_signal,
    )

    assert consumed is True
    assert seen_mtime == 5.0
    resolve_path.assert_called_once_with(
        args=args,
        attr_name="biometric_unlock_signal_file",
        default_path="/tmp/unlock.signal",
    )
    consume_signal.assert_called_once_with(
        signal_path="/tmp/unlock.signal",
        seen_mtime=1.0,
    )


def test_record_successful_command_activity_updates_timestamp() -> None:
    runtime = SimpleNamespace(_last_successful_command_at=0.0)

    record_successful_command_activity(runtime, now=lambda: 123.0)

    assert runtime._last_successful_command_at == 123.0
