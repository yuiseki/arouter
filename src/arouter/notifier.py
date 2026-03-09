from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from typing import Any


def trim_notify_text(text: str, *, limit: int = 240) -> str:
    s = " ".join((text or "").split())
    if len(s) <= limit:
        return s
    if limit <= 1:
        return s[:limit]
    return s[: limit - 1] + "…"


def compose_overlay_notify_text(title: str, body: str) -> str:
    title_trimmed = trim_notify_text(title, limit=80) or "音声コマンド"
    body_trimmed = trim_notify_text(body, limit=240)
    if body_trimmed:
        return f"{title_trimmed}: {body_trimmed}"
    return title_trimmed


class DesktopNotifier:
    def __init__(
        self,
        *,
        enabled: bool,
        display: str | None,
        timeout_ms: int,
        app_name: str,
        overlay_client: Any | None,
        logger: Callable[[str], None],
        find_binary: Callable[[str], str | None] = shutil.which,
        run_command: Callable[..., Any] = subprocess.run,
        env_builder: Callable[[str | None], dict[str, str]] | None = None,
    ) -> None:
        self.log = logger
        self.enabled = enabled
        self.display = display
        self.timeout_ms = max(0, int(timeout_ms))
        self.app_name = app_name
        self.overlay = overlay_client
        self._find_binary = find_binary
        self._run_command = run_command
        self._env_builder = env_builder or self._default_env
        self._notify_send = find_binary("notify-send") if enabled else None
        if self.enabled and not self._notify_send and not (self.overlay and self.overlay.enabled):
            self.log("notify-send not found; desktop notifications disabled")
            self.enabled = False

    def _default_env(self, display: str | None) -> dict[str, str]:
        env = os.environ.copy()
        if display:
            env["DISPLAY"] = display
        return env

    def prepare(self) -> None:
        if not self.enabled:
            return
        if self.overlay and self.overlay.enabled:
            self.log(
                "desktop overlay notify enabled: "
                f"endpoint={self.overlay.endpoint} timeoutMs={self.timeout_ms}"
            )
        self.log(
            "desktop notify enabled: "
            f"display={self.display or '<inherit>'} timeoutMs={self.timeout_ms}"
        )

    def notify(self, title: str, body: str = "", *, urgency: str = "normal") -> None:
        if not self.enabled:
            return
        if self.overlay and self.overlay.enabled:
            try:
                self.overlay.notify(
                    text=compose_overlay_notify_text(title, body),
                    duration_ms=self.timeout_ms,
                )
                return
            except Exception as exc:
                self.log(f"overlay notify failed; fallback to notify-send: {exc}")
        if not self._notify_send:
            return
        cmd = [
            self._notify_send,
            "-a",
            self.app_name,
            "-u",
            urgency,
            "-t",
            str(self.timeout_ms),
            "-h",
            "string:x-canonical-private-synchronous:voice-command-loop",
            trim_notify_text(title, limit=80) or "音声コマンド",
        ]
        body_trimmed = trim_notify_text(body, limit=240)
        if body_trimmed:
            cmd.append(body_trimmed)
        try:
            self._run_command(
                cmd,
                check=True,
                text=True,
                capture_output=True,
                timeout=2.0,
                env=self._env_builder(self.display),
            )
        except Exception as exc:
            self.log(f"notify-send error: {exc}")
