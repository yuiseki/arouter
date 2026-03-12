from __future__ import annotations

import importlib.util
import json
import os
import signal
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from arouter.entrypoint import run_voice_command_entrypoint_host_runtime


def resolve_workspaces_root() -> Path:
    env_root = os.environ.get("YUICLAW_WORKSPACES_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[4]


def resolve_voice_command_runtime_script_path(workspaces_root: Path | None = None) -> Path:
    root = workspaces_root or resolve_workspaces_root()
    return root / "repos/arouter/scripts/voice_command_runtime.py"


def load_voice_command_runtime_module(
    *,
    script_path: Path | None = None,
    module_name: str = "arouter_voice_command_runtime",
    module_from_spec: Callable[[Any], Any] = importlib.util.module_from_spec,
    spec_from_file_location: Callable[..., Any] = importlib.util.spec_from_file_location,
) -> Any:
    runtime_script_path = script_path or resolve_voice_command_runtime_script_path()
    spec = spec_from_file_location(module_name, runtime_script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load voice command runtime from {runtime_script_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_voice_command_entrypoint_main(
    argv: list[str] | None = None,
    *,
    load_module: Callable[[], Any] = load_voice_command_runtime_module,
    host_runtime: Callable[..., int] = run_voice_command_entrypoint_host_runtime,
) -> int:
    module = load_module()
    args = module.parse_args(argv)

    def _emit_json(payload: dict[str, Any]) -> None:
        print(json.dumps(payload, ensure_ascii=False), flush=True)

    def _install_signal_handlers(loop: Any) -> None:
        def _sig_handler(signum: int, _frame: Any) -> None:
            loop.stop_requested = True
            loop.log(f"signal {signum} received, stopping ...")

        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)

    def _request_biometric_lock_cli_flow() -> dict[str, Any]:
        return cast(
            dict[str, Any],
            module.arouter_run_request_biometric_lock_cli_flow(
                args=args,
                default_path=module.DEFAULT_BIOMETRIC_LOCK_SIGNAL_FILE,
                write_signal=module.write_biometric_signal_file,
            ),
        )

    def _encrypt_biometric_password_stdin_cli_flow() -> dict[str, Any]:
        return cast(
            dict[str, Any],
            module.arouter_run_encrypt_biometric_password_stdin_cli_flow(
                args=args,
                default_public_key_path=module.DEFAULT_BIOMETRIC_PASSWORD_PUBLIC_KEY,
                default_output_path=module.DEFAULT_BIOMETRIC_PASSWORD_FILE,
                read_passwords=module._read_password_secret_lines_from_stdin,
                encrypt_password=module.encrypt_biometric_password_file,
            ),
        )

    return host_runtime(
        args=args,
        build_loop=module.VoiceCommandLoop,
        emit_json=_emit_json,
        request_biometric_lock_cli_flow=_request_biometric_lock_cli_flow,
        encrypt_biometric_password_stdin_cli_flow=_encrypt_biometric_password_stdin_cli_flow,
        install_signal_handlers=_install_signal_handlers,
    )


def main(argv: list[str] | None = None) -> int:
    return run_voice_command_entrypoint_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
