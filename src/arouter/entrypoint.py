from __future__ import annotations

from collections.abc import Callable
from typing import Any


def run_voice_command_entrypoint_host_runtime(
    *,
    args: Any,
    build_loop: Callable[[Any], Any],
    emit_json: Callable[[dict[str, Any]], None],
    request_biometric_lock_cli_flow: Callable[[], dict[str, Any]],
    encrypt_biometric_password_stdin_cli_flow: Callable[[], dict[str, Any]],
    install_signal_handlers: Callable[[Any], None],
) -> int:
    if bool(getattr(args, "request_biometric_lock", False)):
        try:
            emit_json(request_biometric_lock_cli_flow())
            return 0
        except Exception as exc:
            emit_json({"ok": False, "error": str(exc)})
            return 1

    if bool(getattr(args, "encrypt_biometric_password_stdin", False)):
        try:
            emit_json(encrypt_biometric_password_stdin_cli_flow())
            return 0
        except Exception as exc:
            emit_json({"ok": False, "error": str(exc)})
            return 1

    loop = build_loop(args)
    simulate_mic_command = getattr(args, "simulate_mic_command", None)
    if simulate_mic_command:
        try:
            emit_json(loop.execute_simulated_mic_command(simulate_mic_command))
            return 0
        except Exception as exc:
            emit_json({"ok": False, "text": simulate_mic_command, "error": str(exc)})
            return 1

    run_command = getattr(args, "run_command", None)
    if run_command:
        try:
            emit_json(loop.execute_text_command(run_command))
            return 0
        except Exception as exc:
            emit_json({"ok": False, "text": run_command, "error": str(exc)})
            return 1

    install_signal_handlers(loop)
    return int(loop.run())
