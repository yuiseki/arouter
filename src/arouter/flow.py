from __future__ import annotations

import time
from typing import Any, Protocol

from .models import VoiceCommand


class CommandFlowRuntime(Protocol):
    notifier: Any
    voice: Any
    _last_ack_proc: Any

    def _should_ack_before_action(self, cmd: VoiceCommand) -> bool: ...

    def _start_ack(self, cmd: VoiceCommand) -> None: ...

    def _should_wait_ack_before_action(self, cmd: VoiceCommand) -> bool: ...

    def _wait_current_ack(self, *, timeout_sec: float = 8.0) -> None: ...

    def _execute_command(self, cmd: VoiceCommand) -> str: ...

    def _record_successful_command_activity(self) -> None: ...

    def _post_action_voice_text(self, cmd: VoiceCommand, action_result: str) -> str | None: ...

    def _wait_ack_if_requested(self) -> None: ...

    def log(self, msg: str) -> None: ...


def run_authorized_command_flow(
    runtime: CommandFlowRuntime,
    *,
    seg_id: int,
    text: str,
    cmd: VoiceCommand,
    notify_progress: bool,
) -> str:
    if runtime._should_ack_before_action(cmd):
        runtime._start_ack(cmd)
        if runtime._should_wait_ack_before_action(cmd):
            runtime._wait_current_ack(timeout_sec=8.0)

    if notify_progress:
        runtime.notifier.notify(
            "音声コマンド 認識",
            f"{text} (intent={cmd.intent})",
            urgency="low",
        )

    started_at = time.time()
    result = runtime._execute_command(cmd)
    action_elapsed = time.time() - started_at

    runtime._record_successful_command_activity()
    post_action_voice = runtime._post_action_voice_text(cmd, result)
    if post_action_voice:
        try:
            runtime._last_ack_proc = runtime.voice.speak(post_action_voice, wait=False)
        except Exception as exc:
            runtime.log(f"post-action speak error: {exc}")
            runtime._last_ack_proc = None

    runtime._wait_ack_if_requested()
    runtime.log(f"action #{seg_id} done ({action_elapsed:.2f}s): {result}")

    if notify_progress:
        runtime.notifier.notify(
            "音声コマンド 完了",
            f"{cmd.ack_text} {result}",
            urgency="normal",
        )

    return result
