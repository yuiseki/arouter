from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Protocol

from .flow import CommandFlowRuntime, run_authorized_command_flow
from .resolution import resolve_segment_transcript
from .storage import (
    AuthorizationFailureRuntime,
    handle_authorization_denied,
    store_authorized_wav,
)


class SegmentRuntime(AuthorizationFailureRuntime, CommandFlowRuntime, Protocol):
    _last_resolved_segment_command: Any

    def _contextualize_command_with_vacuumtube_state(self, text: str, cmd: Any) -> Any: ...

    def _should_suppress_transcribed_command(self, cmd: Any, *, dur_sec: float) -> str | None: ...

    def _authorize_command(
        self,
        cmd: Any,
        *,
        wav_path: Path | None,
        source: str,
        log_label: str,
    ) -> tuple[bool, str | None]: ...


def process_transcribed_segment(
    runtime: SegmentRuntime,
    *,
    seg_id: int,
    text: str,
    stt_elapsed: float,
    dur_sec: float,
    wav_path: Path,
    tmp_wav: Path,
    datasets_root: Path,
    now: time.struct_time,
    ts: str,
    notify_progress: bool,
) -> str:
    normalized_text = " ".join(str(text or "").split())
    runtime._last_resolved_segment_command = None
    if not normalized_text:
        runtime.log(f"transcript #{seg_id} empty ({stt_elapsed:.2f}s)")
        return "empty"

    runtime.log(f"transcript #{seg_id} ({stt_elapsed:.2f}s): {normalized_text}")
    resolution = resolve_segment_transcript(
        normalized_text,
        wav_path=wav_path,
        dur_sec=dur_sec,
        source="mic",
        seg_label=f"command #{seg_id}",
        contextualizer=runtime._contextualize_command_with_vacuumtube_state,
        suppressor=lambda resolved_cmd, resolved_dur_sec: (
            runtime._should_suppress_transcribed_command(
                resolved_cmd,
                dur_sec=resolved_dur_sec,
            )
        ),
        authorizer=lambda resolved_cmd, resolved_wav_path, source, log_label: (
            runtime._authorize_command(
                resolved_cmd,
                wav_path=resolved_wav_path,
                source=source,
                log_label=log_label,
            )
        ),
    )
    cmd = resolution.cmd
    if cmd is not None:
        runtime._last_resolved_segment_command = cmd
    if resolution.outcome == "reaction":
        runtime.log(
            f"transcript #{seg_id} reaction detected "
            f"({resolution.reaction}; no-op): {normalized_text}"
        )
        return "reaction"
    if resolution.outcome == "ignored":
        runtime.log(f"transcript #{seg_id} ignored (no mapped command)")
        return "ignored"
    if resolution.outcome == "suppressed":
        if cmd is not None:
            runtime.log(
                f"command #{seg_id} suppressed: intent={cmd.intent} "
                f"reason={resolution.suppressed_reason}"
            )
        return "suppressed"
    if resolution.outcome == "denied":
        if cmd is None:
            raise RuntimeError("denied transcript resolution returned no command")
        runtime.log(
            f"command #{seg_id} authorization denied: intent={cmd.intent} "
            f"reason={resolution.auth_error or 'authorization_failed'}"
        )
        handle_authorization_denied(
            runtime,
            tmp_wav=tmp_wav,
            datasets_root=datasets_root,
            now=now,
            ts=ts,
            seg_id=seg_id,
            cmd=cmd,
            auth_error=resolution.auth_error,
        )
        return "denied"
    if resolution.outcome != "ready" or cmd is None:
        raise RuntimeError(f"unexpected transcript resolution outcome: {resolution.outcome}")

    store_authorized_wav(
        tmp_wav=tmp_wav,
        datasets_root=datasets_root,
        now=now,
        ts=ts,
        seg_id=seg_id,
    )
    runtime.log(f"command #{seg_id}: intent={cmd.intent} normalized={cmd.normalized_text}")
    run_authorized_command_flow(
        runtime,
        seg_id=seg_id,
        text=normalized_text,
        cmd=cmd,
        notify_progress=notify_progress,
    )
    return "executed"
