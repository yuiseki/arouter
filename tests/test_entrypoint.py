from __future__ import annotations

from types import SimpleNamespace

from arouter.entrypoint import run_voice_command_entrypoint_host_runtime


def test_run_voice_command_entrypoint_host_runtime_runs_request_lock_flow() -> None:
    args = SimpleNamespace(
        request_biometric_lock=True,
        encrypt_biometric_password_stdin=False,
        run_command=None,
    )
    emitted: list[dict[str, object]] = []
    built: list[object] = []

    exit_code = run_voice_command_entrypoint_host_runtime(
        args=args,
        build_loop=lambda _args: built.append(_args),
        emit_json=emitted.append,
        request_biometric_lock_cli_flow=lambda: {"ok": True, "lockSignalFile": "/tmp/lock.signal"},
        encrypt_biometric_password_stdin_cli_flow=lambda: {"ok": True},
        install_signal_handlers=lambda _loop: (_ for _ in ()).throw(AssertionError("unused")),
    )

    assert exit_code == 0
    assert built == []
    assert emitted == [{"ok": True, "lockSignalFile": "/tmp/lock.signal"}]


def test_run_voice_command_entrypoint_host_runtime_runs_run_command_flow() -> None:
    args = SimpleNamespace(
        request_biometric_lock=False,
        encrypt_biometric_password_stdin=False,
        run_command="システム 街頭カメラを表示",
    )
    emitted: list[dict[str, object]] = []
    installed: list[object] = []
    loop = SimpleNamespace(
        execute_text_command=lambda text: {"ok": True, "text": text, "result": "show ok"},
    )

    exit_code = run_voice_command_entrypoint_host_runtime(
        args=args,
        build_loop=lambda _args: loop,
        emit_json=emitted.append,
        request_biometric_lock_cli_flow=lambda: {"ok": True},
        encrypt_biometric_password_stdin_cli_flow=lambda: {"ok": True},
        install_signal_handlers=installed.append,
    )

    assert exit_code == 0
    assert installed == []
    assert emitted == [{"ok": True, "text": "システム 街頭カメラを表示", "result": "show ok"}]


def test_run_voice_command_entrypoint_host_runtime_reports_run_command_error() -> None:
    args = SimpleNamespace(
        request_biometric_lock=False,
        encrypt_biometric_password_stdin=False,
        run_command="システム 街頭カメラを表示",
    )
    emitted: list[dict[str, object]] = []
    loop = SimpleNamespace(
        execute_text_command=lambda _text: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    exit_code = run_voice_command_entrypoint_host_runtime(
        args=args,
        build_loop=lambda _args: loop,
        emit_json=emitted.append,
        request_biometric_lock_cli_flow=lambda: {"ok": True},
        encrypt_biometric_password_stdin_cli_flow=lambda: {"ok": True},
        install_signal_handlers=lambda _loop: None,
    )

    assert exit_code == 1
    assert emitted == [{"ok": False, "text": "システム 街頭カメラを表示", "error": "boom"}]


def test_run_voice_command_entrypoint_host_runtime_runs_long_lived_loop() -> None:
    args = SimpleNamespace(
        request_biometric_lock=False,
        encrypt_biometric_password_stdin=False,
        run_command=None,
    )
    emitted: list[dict[str, object]] = []
    installed: list[object] = []
    loop = SimpleNamespace(run=lambda: 42)

    exit_code = run_voice_command_entrypoint_host_runtime(
        args=args,
        build_loop=lambda _args: loop,
        emit_json=emitted.append,
        request_biometric_lock_cli_flow=lambda: {"ok": True},
        encrypt_biometric_password_stdin_cli_flow=lambda: {"ok": True},
        install_signal_handlers=installed.append,
    )

    assert exit_code == 42
    assert installed == [loop]
    assert emitted == []
