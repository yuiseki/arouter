from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from arouter.voice_command_entrypoint import (
    load_voice_command_runtime_module,
    run_voice_command_entrypoint_main,
)


def _load_runtime_script_module(module_name: str) -> Any:
    script_path = Path("/home/yuiseki/Workspaces/repos/arouter/scripts/voice_command_runtime.py")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    runtime_module: Any = importlib.util.module_from_spec(spec)
    fake_websocket = ModuleType("websocket")
    original_websocket = sys.modules.get("websocket")
    sys.modules[spec.name] = runtime_module
    sys.modules["websocket"] = fake_websocket
    try:
        spec.loader.exec_module(runtime_module)
    finally:
        if original_websocket is None:
            sys.modules.pop("websocket", None)
        else:
            sys.modules["websocket"] = original_websocket
    return runtime_module


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
        parse_args=lambda argv: _record_parse_args(events, argv),
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


def _record_parse_args(events: list[tuple[str, object]], argv: object) -> SimpleNamespace:
    events.append(("parse_args", argv))
    return SimpleNamespace(run_command="システムおはよう")


def test_runtime_script_defaults_speaker_master_to_ahear_models() -> None:
    runtime_module = _load_runtime_script_module("runtime_speaker_master_test")

    args = runtime_module.parse_args([])

    assert args.speaker_master == str(
        Path("/home/yuiseki/Workspaces/repos/ahear/python/src/ahear/models/master_voiceprint.npy")
    )


def test_runtime_script_defaults_moonshine_vad_for_quiet_input() -> None:
    runtime_module = _load_runtime_script_module("runtime_moonshine_vad_test")

    args = runtime_module.parse_args([])

    assert args.start_rms == 0.004
    assert args.stop_rms == 0.0015
    assert args.start_rms_min == 0.004
    assert args.start_rms_max == 0.008
    assert args.stop_rms_min == 0.0015
    assert args.stop_rms_max == 0.0035


def test_runtime_script_accepts_simulated_mic_command_flag() -> None:
    runtime_module = _load_runtime_script_module("runtime_simulated_mic_command_test")

    args = runtime_module.parse_args(
        ["--simulate-mic-command", "システム バイオメトリクス認証"]
    )

    assert args.simulate_mic_command == "システム バイオメトリクス認証"


def test_runtime_script_voice_command_loop_exposes_wmctrl_rows_for_load_check() -> None:
    runtime_module = _load_runtime_script_module("runtime_load_check_wmctrl_rows_test")

    assert hasattr(runtime_module.VoiceCommandLoop, "_wmctrl_rows")
    assert hasattr(runtime_module.VoiceCommandLoop, "_x11_env")


def test_runtime_script_exports_bgm_tile_scorer_for_vacuumtube_host_runtime() -> None:
    runtime_module = _load_runtime_script_module("runtime_bgm_scorer_test")

    assert callable(runtime_module.score_vacuumtube_bgm_tile)


def test_runtime_script_exports_news_blob_filter_for_vacuumtube_host_runtime() -> None:
    runtime_module = _load_runtime_script_module("runtime_news_blob_filter_test")

    assert callable(runtime_module.looks_like_vacuumtube_news_blob)


def test_runtime_script_exports_news_tile_scorer_for_vacuumtube_host_runtime() -> None:
    runtime_module = _load_runtime_script_module("runtime_news_tile_scorer_test")

    assert callable(runtime_module.score_vacuumtube_news_tile)


@pytest.mark.parametrize(
    ("text", "required_symbols", "required_attrs"),
    [
        (
            "システム バイオメトリクス認証",
            (),
            (),
        ),
        (
            "システム 負荷を確認して",
            (),
            ("_wmctrl_rows", "_x11_env"),
        ),
        (
            "システム 音楽を流して",
            ("score_vacuumtube_bgm_tile",),
            (),
        ),
        (
            "システム おはよう",
            (
                "looks_like_vacuumtube_news_blob",
                "score_vacuumtube_news_tile",
            ),
            (),
        ),
        (
            "システム おやすみ",
            (),
            (),
        ),
    ],
)
def test_runtime_script_exposes_acceptance_contract(
    text: str,
    required_symbols: tuple[str, ...],
    required_attrs: tuple[str, ...],
) -> None:
    runtime_module = _load_runtime_script_module(
        "runtime_acceptance_contract_" + str(abs(hash(text)))
    )

    args = runtime_module.parse_args(["--simulate-mic-command", text])

    assert args.simulate_mic_command == text
    for symbol in required_symbols:
        assert callable(getattr(runtime_module, symbol))
    for attr in required_attrs:
        assert hasattr(runtime_module.VoiceCommandLoop, attr)
