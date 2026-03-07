from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .models import VoiceCommand
from .parser import parse_command
from .reactions import detect_non_command_reaction


@dataclass(frozen=True, slots=True)
class SegmentTranscriptResolution:
    outcome: str
    cmd: VoiceCommand | None = None
    reaction: str | None = None
    suppressed_reason: str | None = None
    auth_error: str | None = None


def resolve_segment_transcript(
    text: str,
    *,
    wav_path: Path | None,
    dur_sec: float,
    source: str,
    seg_label: str,
    contextualizer: Callable[[str, VoiceCommand | None], VoiceCommand | None],
    suppressor: Callable[[VoiceCommand, float], str | None],
    authorizer: Callable[[VoiceCommand, Path | None, str, str], tuple[bool, str | None]],
) -> SegmentTranscriptResolution:
    normalized_text = " ".join(str(text or "").split())
    cmd = parse_command(normalized_text)
    cmd = contextualizer(normalized_text, cmd)
    if not cmd:
        reaction = detect_non_command_reaction(normalized_text)
        if reaction:
            return SegmentTranscriptResolution(outcome="reaction", reaction=reaction)
        return SegmentTranscriptResolution(outcome="ignored")

    suppressed_reason = suppressor(cmd, dur_sec)
    if suppressed_reason:
        return SegmentTranscriptResolution(
            outcome="suppressed",
            cmd=cmd,
            suppressed_reason=suppressed_reason,
        )

    ok, auth_error = authorizer(cmd, wav_path, source, seg_label)
    if not ok:
        return SegmentTranscriptResolution(
            outcome="denied",
            cmd=cmd,
            auth_error=auth_error,
        )

    return SegmentTranscriptResolution(outcome="ready", cmd=cmd)
