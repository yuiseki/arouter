from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .biometric_paths import resolve_biometric_arg_path


def request_biometric_lock_payload(
    *,
    signal_path: Path,
    write_signal: Callable[..., Path],
) -> dict[str, object]:
    written_path = write_signal(signal_path=signal_path, action="lock")
    return {
        "ok": True,
        "lockSignalFile": str(written_path),
    }


def encrypt_biometric_password_payload(
    *,
    public_key_path: Path,
    output_path: Path,
    password_lines: list[str],
    encrypt_password: Callable[..., Path],
) -> dict[str, object]:
    written_path = encrypt_password(
        public_key_path=public_key_path,
        output_path=output_path,
        password_lines=password_lines,
    )
    return {
        "ok": True,
        "passwordFile": str(written_path),
    }


def run_request_biometric_lock(
    *,
    args: Any,
    resolve_path: Callable[..., Path],
    request_payload: Callable[..., dict[str, object]],
    write_signal: Callable[..., Path],
) -> dict[str, object]:
    signal_path = resolve_path(args=args)
    return request_payload(
        signal_path=signal_path,
        write_signal=write_signal,
    )


def run_encrypt_biometric_password_stdin(
    *,
    args: Any,
    read_passwords: Callable[[], list[str]],
    resolve_public_key_path: Callable[..., Path],
    resolve_output_path: Callable[..., Path],
    encrypt_payload: Callable[..., dict[str, object]],
    encrypt_password: Callable[..., Path],
) -> dict[str, object]:
    password_lines = read_passwords()
    public_key_path = resolve_public_key_path(args=args)
    output_path = resolve_output_path(args=args)
    return encrypt_payload(
        public_key_path=public_key_path,
        output_path=output_path,
        password_lines=password_lines,
        encrypt_password=encrypt_password,
    )


def run_request_biometric_lock_cli_flow(
    *,
    args: Any,
    default_path: str,
    write_signal: Callable[..., Path],
) -> dict[str, object]:
    return run_request_biometric_lock(
        args=args,
        resolve_path=lambda *, args: resolve_biometric_arg_path(
            args=args,
            attr_name="biometric_lock_signal_file",
            default_path=default_path,
        ),
        request_payload=request_biometric_lock_payload,
        write_signal=write_signal,
    )


def run_encrypt_biometric_password_stdin_cli_flow(
    *,
    args: Any,
    default_public_key_path: str,
    default_output_path: str,
    read_passwords: Callable[[], list[str]],
    encrypt_password: Callable[..., Path],
) -> dict[str, object]:
    return run_encrypt_biometric_password_stdin(
        args=args,
        read_passwords=read_passwords,
        resolve_public_key_path=lambda *, args: resolve_biometric_arg_path(
            args=args,
            attr_name="biometric_password_public_key",
            default_path=default_public_key_path,
        ),
        resolve_output_path=lambda *, args: resolve_biometric_arg_path(
            args=args,
            attr_name="biometric_password_file",
            default_path=default_output_path,
        ),
        encrypt_payload=encrypt_biometric_password_payload,
        encrypt_password=encrypt_password,
    )
