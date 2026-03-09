from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from arouter import (
    encrypt_biometric_password_payload,
    request_biometric_lock_payload,
    run_encrypt_biometric_password_stdin,
    run_request_biometric_lock,
)


def test_request_biometric_lock_payload_writes_signal_and_returns_json_shape() -> None:
    written_paths: list[Path] = []

    def fake_write_signal(*, signal_path: Path, action: str) -> Path:
        written_paths.append(signal_path)
        assert action == "lock"
        return signal_path

    payload = request_biometric_lock_payload(
        signal_path=Path("/tmp/lock.signal"),
        write_signal=fake_write_signal,
    )

    assert payload == {"ok": True, "lockSignalFile": "/tmp/lock.signal"}
    assert written_paths == [Path("/tmp/lock.signal")]


def test_encrypt_biometric_password_payload_writes_file_and_returns_json_shape() -> None:
    written_args: list[tuple[Path, Path, list[str]]] = []

    def fake_encrypt(
        *,
        public_key_path: Path,
        output_path: Path,
        password_lines: list[str],
    ) -> Path:
        written_args.append((public_key_path, output_path, password_lines))
        return output_path

    payload = encrypt_biometric_password_payload(
        public_key_path=Path("/tmp/id_rsa.pub"),
        output_path=Path("/tmp/biometric-password.enc"),
        password_lines=["alpha", "beta"],
        encrypt_password=fake_encrypt,
    )

    assert payload == {"ok": True, "passwordFile": "/tmp/biometric-password.enc"}
    assert written_args == [
        (
            Path("/tmp/id_rsa.pub"),
            Path("/tmp/biometric-password.enc"),
            ["alpha", "beta"],
        )
    ]


def test_run_request_biometric_lock_resolves_path_and_builds_payload() -> None:
    args = SimpleNamespace(biometric_lock_signal_file="/tmp/custom-lock.signal")

    payload = run_request_biometric_lock(
        args=args,
        resolve_path=lambda *, args: Path(args.biometric_lock_signal_file),
        request_payload=lambda *, signal_path, write_signal: {
            "ok": True,
            "lockSignalFile": str(signal_path),
            "writeSignalIsCallable": callable(write_signal),
        },
        write_signal=lambda **_: Path("/tmp/custom-lock.signal"),
    )

    assert payload == {
        "ok": True,
        "lockSignalFile": "/tmp/custom-lock.signal",
        "writeSignalIsCallable": True,
    }


def test_run_encrypt_biometric_password_stdin_resolves_paths_and_builds_payload() -> None:
    args = SimpleNamespace(
        biometric_password_public_key="/tmp/id_rsa.pub",
        biometric_password_file="/tmp/biometric-password.enc",
    )

    payload = run_encrypt_biometric_password_stdin(
        args=args,
        read_passwords=lambda: ["alpha"],
        resolve_public_key_path=lambda *, args: Path(args.biometric_password_public_key),
        resolve_output_path=lambda *, args: Path(args.biometric_password_file),
        encrypt_payload=lambda *, public_key_path, output_path, password_lines, encrypt_password: {
            "ok": True,
            "passwordFile": str(output_path),
            "publicKeyPath": str(public_key_path),
            "passwordLines": password_lines,
            "encryptPasswordIsCallable": callable(encrypt_password),
        },
        encrypt_password=lambda **_: Path("/tmp/biometric-password.enc"),
    )

    assert payload == {
        "ok": True,
        "passwordFile": "/tmp/biometric-password.enc",
        "publicKeyPath": "/tmp/id_rsa.pub",
        "passwordLines": ["alpha"],
        "encryptPasswordIsCallable": True,
    }
