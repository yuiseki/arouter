from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import pytest

from arouter import (
    encrypt_password_file,
    load_password_candidates,
    read_password_secret_lines,
    verify_unlock_password,
)


def test_read_password_secret_lines_strips_blank_lines() -> None:
    assert read_password_secret_lines(" first \n\n second \n") == ["first", "second"]


def test_read_password_secret_lines_rejects_empty_input() -> None:
    with pytest.raises(RuntimeError, match="stdin にパスワードがありません"):
        read_password_secret_lines(" \n \n")


def test_encrypt_password_file_writes_base64_ciphertext(tmp_path: Path) -> None:
    public_key_path = tmp_path / "id_rsa.pub"
    output_path = tmp_path / "secrets" / "biometric-password.enc"
    command_log: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        *,
        check: bool,
        text: bool = False,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command_log.append(cmd)
        if cmd[:3] == ["ssh-keygen", "-e", "-m"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="PUBLIC KEY", stderr="")
        if cmd[:2] == ["openssl", "pkeyutl"]:
            cipher_index = cmd.index("-out") + 1
            Path(cmd[cipher_index]).write_bytes(b"cipher-bytes")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    written_path = encrypt_password_file(
        public_key_path=public_key_path,
        output_path=output_path,
        password_lines=["secret-a", "", " secret-b "],
        run_cmd=fake_run,
    )

    assert written_path == output_path
    expected = base64.b64encode(b"cipher-bytes").decode("ascii") + "\n"
    assert output_path.read_text(encoding="utf-8") == expected
    assert command_log[0][:4] == ["ssh-keygen", "-e", "-m", "PKCS8"]
    assert command_log[1][:2] == ["openssl", "pkeyutl"]


def test_encrypt_password_file_rejects_empty_payload(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="パスワードが空です"):
        encrypt_password_file(
            public_key_path=tmp_path / "id_rsa.pub",
            output_path=tmp_path / "biometric-password.enc",
            password_lines=["", "  "],
        )


def test_load_password_candidates_returns_empty_when_file_missing(tmp_path: Path) -> None:
    debug_logs: list[str] = []

    candidates = load_password_candidates(
        encrypted_path=tmp_path / "missing.enc",
        private_key_path=tmp_path / "id_rsa",
        debug=debug_logs.append,
        log=lambda _msg: None,
    )

    assert candidates == []
    assert debug_logs == [f"biometric password file missing: {tmp_path / 'missing.enc'}"]


def test_load_password_candidates_returns_empty_when_private_key_missing(tmp_path: Path) -> None:
    encrypted_path = tmp_path / "biometric-password.enc"
    encrypted_path.write_text(base64.b64encode(b"x").decode("ascii"), encoding="utf-8")
    debug_logs: list[str] = []

    candidates = load_password_candidates(
        encrypted_path=encrypted_path,
        private_key_path=tmp_path / "missing-key",
        debug=debug_logs.append,
        log=lambda _msg: None,
    )

    assert candidates == []
    assert debug_logs == [f"biometric private key missing: {tmp_path / 'missing-key'}"]


def test_load_password_candidates_decodes_and_decrypts_payload(tmp_path: Path) -> None:
    encrypted_path = tmp_path / "biometric-password.enc"
    private_key_path = tmp_path / "id_rsa"
    encrypted_path.write_text(base64.b64encode(b"cipher-bytes").decode("ascii"), encoding="utf-8")
    private_key_path.write_text("PRIVATE KEY", encoding="utf-8")
    command_log: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command_log.append(cmd)
        if cmd[:2] == ["ssh-keygen", "-p"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["openssl", "pkeyutl"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="alpha\nbeta\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    candidates = load_password_candidates(
        encrypted_path=encrypted_path,
        private_key_path=private_key_path,
        debug=lambda _msg: None,
        log=lambda _msg: None,
        run_cmd=fake_run,
    )

    assert candidates == ["alpha", "beta"]
    assert command_log[0][:2] == ["ssh-keygen", "-p"]
    assert command_log[1][:2] == ["openssl", "pkeyutl"]


def test_load_password_candidates_logs_decrypt_error(tmp_path: Path) -> None:
    encrypted_path = tmp_path / "biometric-password.enc"
    private_key_path = tmp_path / "id_rsa"
    encrypted_path.write_text(base64.b64encode(b"cipher-bytes").decode("ascii"), encoding="utf-8")
    private_key_path.write_text("PRIVATE KEY", encoding="utf-8")
    logs: list[str] = []

    def fake_run(
        cmd: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["ssh-keygen", "-p"]:
            raise subprocess.CalledProcessError(1, cmd, stderr="decrypt failed")
        raise AssertionError(f"unexpected command: {cmd}")

    candidates = load_password_candidates(
        encrypted_path=encrypted_path,
        private_key_path=private_key_path,
        debug=lambda _msg: None,
        log=logs.append,
        run_cmd=fake_run,
    )

    assert candidates == []
    assert logs == ["biometric password decrypt failed: decrypt failed"]


def test_verify_unlock_password_uses_normalizer() -> None:
    assert verify_unlock_password(
        provided_secret=" システム パスワード ",
        candidates=["システムパスワード", "other"],
        normalize=lambda value: "".join(value.split()),
    )
    assert not verify_unlock_password(
        provided_secret="different",
        candidates=["secret"],
        normalize=lambda value: value,
    )
