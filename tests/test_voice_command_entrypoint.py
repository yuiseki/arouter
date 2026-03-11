from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from arouter.voice_command_entrypoint import (
    load_legacy_voice_command_module,
    run_voice_command_entrypoint_main,
)


def test_load_legacy_voice_command_module_inserts_tmp_path(monkeypatch) -> None:
    imported: list[str] = []
    module_dir = Path("/workspaces/tmp/whispercpp-listen")
    fake_module = object()

    def fake_import_module(name: str) -> object:
        imported.append(name)
        return fake_module

    monkeypatch.setattr("sys.path", ["/already-present"])

    loaded = load_legacy_voice_command_module(
        module_dir=module_dir,
        import_module=fake_import_module,
    )

    assert loaded is fake_module
    assert imported == ["voice_command_loop"]
    assert str(module_dir) == __import__("sys").path[0]


def test_run_voice_command_entrypoint_main_delegates_to_host_runtime() -> None:
    events: list[tuple[str, object]] = []

    fake_module = SimpleNamespace(
        parse_args=lambda argv: events.append(("parse_args", argv))
        or SimpleNamespace(run_command="システムおはよう"),
        VoiceCommandLoop=object(),
        arouter_run_request_biometric_lock_cli_flow=lambda **kwargs: {"ok": True, "kind": "lock"},
        arouter_run_encrypt_biometric_password_stdin_cli_flow=lambda **kwargs: {
            "ok": True,
            "kind": "encrypt",
        },
        DEFAULT_BIOMETRIC_LOCK_SIGNAL_FILE="/tmp/lock.signal",
        DEFAULT_BIOMETRIC_PASSWORD_PUBLIC_KEY="/tmp/public.pem",
        DEFAULT_BIOMETRIC_PASSWORD_FILE="/tmp/password.bin",
        write_biometric_signal_file=lambda path: events.append(("write_signal", path)),
        _read_password_secret_lines_from_stdin=lambda: ["secret"],
        encrypt_biometric_password_file=lambda **kwargs: events.append(("encrypt", kwargs)),
    )

    def fake_host_runtime(**kwargs: object) -> int:
        events.append(("host_runtime", kwargs["args"]))
        assert kwargs["build_loop"] is fake_module.VoiceCommandLoop
        assert callable(kwargs["emit_json"])
        assert callable(kwargs["request_biometric_lock_cli_flow"])
        assert callable(kwargs["encrypt_biometric_password_stdin_cli_flow"])
        assert callable(kwargs["install_signal_handlers"])
        return 42

    exit_code = run_voice_command_entrypoint_main(
        ["--run-command", "システムおはよう"],
        load_module=lambda: fake_module,
        host_runtime=fake_host_runtime,
    )

    assert exit_code == 42
    assert events == [
        ("parse_args", ["--run-command", "システムおはよう"]),
        ("host_runtime", SimpleNamespace(run_command="システムおはよう")),
    ]
