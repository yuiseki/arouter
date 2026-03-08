from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

type RunCmd = Callable[..., subprocess.CompletedProcess[str]]


def read_password_secret_lines(raw: str) -> list[str]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(
            "stdin にパスワードがありません。1行以上のパスワードを stdin から渡してください。"
        )
    return lines


def encrypt_password_file(
    *,
    public_key_path: Path,
    output_path: Path,
    password_lines: list[str],
    run_cmd: RunCmd = subprocess.run,
) -> Path:
    payload = "\n".join(line.strip() for line in password_lines if line.strip())
    if not payload:
        raise RuntimeError("パスワードが空です。")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="biometric-password-encrypt-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        pub_pem = tmp_root / "public.pem"
        plain_path = tmp_root / "plain.txt"
        cipher_path = tmp_root / "cipher.bin"

        export_cp = run_cmd(
            ["ssh-keygen", "-e", "-m", "PKCS8", "-f", str(public_key_path)],
            check=True,
            text=True,
            capture_output=True,
        )
        pub_pem.write_text(export_cp.stdout, encoding="utf-8")
        plain_path.write_text(payload, encoding="utf-8")

        run_cmd(
            [
                "openssl",
                "pkeyutl",
                "-encrypt",
                "-pubin",
                "-inkey",
                str(pub_pem),
                "-in",
                str(plain_path),
                "-out",
                str(cipher_path),
                "-pkeyopt",
                "rsa_padding_mode:oaep",
                "-pkeyopt",
                "rsa_oaep_md:sha256",
            ],
            check=True,
            capture_output=True,
        )
        encoded = base64.b64encode(cipher_path.read_bytes()).decode("ascii")
        output_path.write_text(encoded + "\n", encoding="utf-8")
    return output_path


def load_password_candidates(
    *,
    encrypted_path: Path,
    private_key_path: Path,
    debug: Callable[[str], None],
    log: Callable[[str], None],
    run_cmd: RunCmd = subprocess.run,
) -> list[str]:
    if not encrypted_path.exists():
        debug(f"biometric password file missing: {encrypted_path}")
        return []
    if not private_key_path.exists():
        debug(f"biometric private key missing: {private_key_path}")
        return []

    try:
        cipher_text = encrypted_path.read_text(encoding="utf-8").strip()
        cipher_bytes = base64.b64decode(cipher_text)
    except Exception as exc:
        log(f"biometric password load failed: {exc}")
        return []

    with tempfile.TemporaryDirectory(prefix="biometric-password-decrypt-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        cipher_path = tmp_root / "cipher.bin"
        temp_key = tmp_root / "private_key"
        cipher_path.write_bytes(cipher_bytes)
        shutil.copyfile(private_key_path, temp_key)
        temp_key.chmod(0o600)

        try:
            run_cmd(
                [
                    "ssh-keygen",
                    "-p",
                    "-m",
                    "PEM",
                    "-N",
                    "",
                    "-P",
                    "",
                    "-f",
                    str(temp_key),
                    "-q",
                ],
                check=True,
                capture_output=True,
            )
            cp = run_cmd(
                [
                    "openssl",
                    "pkeyutl",
                    "-decrypt",
                    "-inkey",
                    str(temp_key),
                    "-in",
                    str(cipher_path),
                    "-pkeyopt",
                    "rsa_padding_mode:oaep",
                    "-pkeyopt",
                    "rsa_oaep_md:sha256",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            err = (exc.stderr or exc.stdout or "").strip()
            log(f"biometric password decrypt failed: {err}")
            return []

    return [line.strip() for line in (cp.stdout or "").splitlines() if line.strip()]


def verify_unlock_password(
    *,
    provided_secret: str,
    candidates: Iterable[str],
    normalize: Callable[[str], str],
) -> bool:
    provided = normalize(provided_secret)
    if not provided:
        return False
    return any(normalize(candidate) == provided for candidate in candidates)
