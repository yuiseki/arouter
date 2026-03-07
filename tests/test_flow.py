from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from arouter import VoiceCommand, run_authorized_command_flow


def _make_runtime() -> SimpleNamespace:
    runtime = SimpleNamespace()
    runtime._last_ack_proc = None
    runtime._should_ack_before_action = mock.Mock(return_value=True)
    runtime._start_ack = mock.Mock()
    runtime._should_wait_ack_before_action = mock.Mock(return_value=True)
    runtime._wait_current_ack = mock.Mock()
    runtime._execute_command = mock.Mock(return_value="system running; normal mode")
    runtime._record_successful_command_activity = mock.Mock()
    runtime._post_action_voice_text = mock.Mock(return_value=None)
    runtime._wait_ack_if_requested = mock.Mock()
    runtime.log = mock.Mock()
    runtime.notifier = SimpleNamespace(notify=mock.Mock())
    runtime.voice = SimpleNamespace(speak=mock.Mock(return_value="ack-proc"))
    return runtime


def test_run_authorized_command_flow_orders_ack_then_action() -> None:
    runtime = _make_runtime()
    events: list[str] = []
    runtime._start_ack.side_effect = lambda _cmd: events.append("start_ack")
    runtime._wait_current_ack.side_effect = lambda **_kwargs: events.append("wait_current_ack")
    runtime._execute_command.side_effect = lambda _cmd: events.append("execute") or "ok"
    runtime._record_successful_command_activity.side_effect = lambda: events.append("record")
    runtime._wait_ack_if_requested.side_effect = lambda: events.append("wait_ack_if_requested")
    cmd = VoiceCommand(intent="system_status_report", normalized_text="", raw_text="")

    out = run_authorized_command_flow(
        runtime,
        seg_id=1,
        text="システム 状況報告",
        cmd=cmd,
        notify_progress=False,
    )

    assert out == "ok"
    assert events == [
        "start_ack",
        "wait_current_ack",
        "execute",
        "record",
        "wait_ack_if_requested",
    ]
    runtime.notifier.notify.assert_not_called()


def test_run_authorized_command_flow_skips_pre_ack_when_policy_disables_it() -> None:
    runtime = _make_runtime()
    runtime._should_ack_before_action.return_value = False
    cmd = VoiceCommand(intent="good_night", normalized_text="おやすみ", raw_text="おやすみ")

    run_authorized_command_flow(
        runtime,
        seg_id=2,
        text="システム おやすみ",
        cmd=cmd,
        notify_progress=False,
    )

    runtime._start_ack.assert_not_called()
    runtime._wait_current_ack.assert_not_called()
    runtime._execute_command.assert_called_once_with(cmd)


def test_run_authorized_command_flow_emits_progress_notifications_when_enabled() -> None:
    runtime = _make_runtime()
    cmd = VoiceCommand(
        intent="system_status_report",
        normalized_text="システム状況報告",
        raw_text="システム 状況報告",
    )

    run_authorized_command_flow(
        runtime,
        seg_id=3,
        text="システム 状況報告",
        cmd=cmd,
        notify_progress=True,
    )

    assert runtime.notifier.notify.call_count == 2
    assert runtime.notifier.notify.call_args_list[0].args[0] == "音声コマンド 認識"
    assert runtime.notifier.notify.call_args_list[1].args[0] == "音声コマンド 完了"


def test_run_authorized_command_flow_speaks_post_action_voice_text() -> None:
    runtime = _make_runtime()
    runtime._post_action_voice_text.return_value = "おやすみなさいませ。"
    cmd = VoiceCommand(intent="good_night", normalized_text="おやすみ", raw_text="おやすみ")

    run_authorized_command_flow(
        runtime,
        seg_id=4,
        text="システム おやすみ",
        cmd=cmd,
        notify_progress=False,
    )

    runtime.voice.speak.assert_called_once_with("おやすみなさいませ。", wait=False)
    assert runtime._last_ack_proc == "ack-proc"


def test_run_authorized_command_flow_logs_post_action_speak_failure() -> None:
    runtime = _make_runtime()
    runtime._post_action_voice_text.return_value = "おやすみなさいませ。"
    runtime._last_ack_proc = "stale"
    runtime.voice.speak.side_effect = RuntimeError("speaker down")
    cmd = VoiceCommand(intent="good_night", normalized_text="おやすみ", raw_text="おやすみ")

    run_authorized_command_flow(
        runtime,
        seg_id=5,
        text="システム おやすみ",
        cmd=cmd,
        notify_progress=False,
    )

    assert runtime._last_ack_proc is None
    runtime.log.assert_any_call("post-action speak error: speaker down")
