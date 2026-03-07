from __future__ import annotations

import subprocess
from typing import Any, Protocol

from .models import VoiceCommand


class ErrorReportingRuntime(Protocol):
    notifier: Any

    def log(self, msg: str) -> None: ...

    def _speak_action_error(self) -> None: ...


def report_segment_error(
    runtime: ErrorReportingRuntime,
    *,
    seg_id: int,
    exc: Exception,
    cmd: VoiceCommand | None,
) -> None:
    if isinstance(exc, subprocess.CalledProcessError):
        err = (exc.stderr or exc.stdout or "").strip()
        runtime.log(f"segment #{seg_id} error (subprocess exit={exc.returncode}): {err}")
        runtime.notifier.notify(
            "音声コマンド エラー",
            f"subprocess exit={exc.returncode} {err}",
            urgency="critical",
        )
    else:
        runtime.log(f"segment #{seg_id} error: {exc}")
        runtime.notifier.notify(
            "音声コマンド エラー",
            str(exc),
            urgency="critical",
        )
    if cmd is not None:
        runtime._speak_action_error()
