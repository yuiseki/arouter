from __future__ import annotations

from pathlib import Path

from arouter import encrypt_biometric_password_payload, request_biometric_lock_payload


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
