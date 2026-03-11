from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from arouter.voice_command_entrypoint import (
    load_voice_command_runtime_module,
    run_voice_command_entrypoint_main,
)


def test_load_voice_command_runtime_module_uses_runtime_script_path() -> None:
    runtime_script_path = Path("/workspaces/repos/arouter/scripts/voice_command_runtime.py")
    fake_module = SimpleNamespace()
    fake_loader = SimpleNamespace(exec_module=lambda module: setattr(module, "_loaded", True))
    calls: list[tuple[str, object]] = []
    fake_spec = SimpleNamespace(loader=fake_loader)

    def fake_spec_from_file_location(name: str, path: Path) -> object:
        calls.append(("spec", (name, path)))
        return fake_spec

    def fake_module_from_spec(spec: object) -> object:
        calls.append(("module", spec))
        return fake_module

    loaded = load_voice_command_runtime_module(
        script_path=runtime_script_path,
        module_name="runtime_test",
        module_from_spec=fake_module_from_spec,
        spec_from_file_location=fake_spec_from_file_location,
    )

    assert loaded is fake_module
    assert calls == [
        ("spec", ("runtime_test", runtime_script_path)),
        ("module", fake_spec),
    ]
    assert fake_module._loaded is True


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


def test_runtime_script_defaults_speaker_master_to_ahear_models() -> None:
    script_path = Path("/home/yuiseki/Workspaces/repos/arouter/scripts/voice_command_runtime.py")
    spec = importlib.util.spec_from_file_location("runtime_speaker_master_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    runtime_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runtime_module
    spec.loader.exec_module(runtime_module)

    args = runtime_module.parse_args([])

    assert args.speaker_master == str(
        Path("/home/yuiseki/Workspaces/repos/ahear/python/src/ahear/models/master_voiceprint.npy")
    )
