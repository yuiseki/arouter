from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from arouter import DesktopNotifier, compose_overlay_notify_text, trim_notify_text


def test_trim_notify_text_truncates_long_message() -> None:
    trimmed = trim_notify_text("a" * 30, limit=10)

    assert trimmed == "a" * 9 + "…"


def test_compose_overlay_notify_text_joins_title_and_body() -> None:
    assert (
        compose_overlay_notify_text("音声コマンド 完了", "承知しました、音楽を再生します。")
        == "音声コマンド 完了: 承知しました、音楽を再生します。"
    )


def test_desktop_notifier_disables_when_no_overlay_and_notify_send_missing() -> None:
    logs: list[str] = []

    notifier = DesktopNotifier(
        enabled=True,
        display=":1",
        timeout_ms=3000,
        app_name="voice-command-loop",
        overlay_client=None,
        logger=logs.append,
        find_binary=lambda _name: None,
        env_builder=lambda _display: {},
    )

    assert notifier.enabled is False
    assert logs == ["notify-send not found; desktop notifications disabled"]


def test_desktop_notifier_prefers_overlay_notify() -> None:
    overlay = SimpleNamespace(enabled=True, endpoint="127.0.0.1:47832", notify=mock.Mock())

    notifier = DesktopNotifier(
        enabled=True,
        display=":1",
        timeout_ms=3000,
        app_name="voice-command-loop",
        overlay_client=overlay,
        logger=lambda _msg: None,
        find_binary=lambda _name: "/usr/bin/notify-send",
        env_builder=lambda _display: {},
    )

    notifier.notify("音声コマンド 認識", "システム 状況報告", urgency="low")

    overlay.notify.assert_called_once_with(
        text="音声コマンド 認識: システム 状況報告",
        duration_ms=3000,
    )


def test_desktop_notifier_falls_back_to_notify_send_when_overlay_fails() -> None:
    logs: list[str] = []
    overlay = SimpleNamespace(
        enabled=True,
        endpoint="127.0.0.1:47832",
        notify=mock.Mock(side_effect=RuntimeError("overlay down")),
    )
    run_command = mock.Mock()

    notifier = DesktopNotifier(
        enabled=True,
        display=":1",
        timeout_ms=3000,
        app_name="voice-command-loop",
        overlay_client=overlay,
        logger=logs.append,
        find_binary=lambda _name: "/usr/bin/notify-send",
        run_command=run_command,
        env_builder=lambda display: {"DISPLAY": display or ""},
    )

    notifier.notify("音声コマンド エラー", "boom", urgency="critical")

    assert logs == ["overlay notify failed; fallback to notify-send: overlay down"]
    run_command.assert_called_once_with(
        [
            "/usr/bin/notify-send",
            "-a",
            "voice-command-loop",
            "-u",
            "critical",
            "-t",
            "3000",
            "-h",
            "string:x-canonical-private-synchronous:voice-command-loop",
            "音声コマンド エラー",
            "boom",
        ],
        check=True,
        text=True,
        capture_output=True,
        timeout=2.0,
        env={"DISPLAY": ":1"},
    )
