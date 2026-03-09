from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


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
