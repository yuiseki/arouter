from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


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
