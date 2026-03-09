from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

from arouter import (
    run_speaker_auth_enabled,
    run_speaker_auth_initialization,
    run_speaker_identity_verification,
)


def test_run_speaker_auth_initialization_returns_defaults_without_helper() -> None:
    runtime = run_speaker_auth_initialization(
        enabled=True,
        requested_device="cpu",
        speaker_master="/tmp/master.npy",
        logger=lambda _: None,
        initialize_runtime=None,
    )

    assert runtime == {
        "classifier": None,
        "voiceprint": None,
        "np_module": None,
        "torch_module": None,
        "torchaudio_module": None,
        "device": "cpu",
    }


def test_run_speaker_auth_initialization_delegates_to_helper() -> None:
    initialize_runtime = mock.Mock(
        return_value=mock.Mock(
            classifier="classifier",
            voiceprint="voiceprint",
            np_module="np",
            torch_module="torch",
            torchaudio_module="torchaudio",
            device="cuda:0",
        )
    )

    runtime = run_speaker_auth_initialization(
        enabled=True,
        requested_device="cpu",
        speaker_master="/tmp/master.npy",
        logger=lambda _: None,
        initialize_runtime=initialize_runtime,
    )

    assert runtime == {
        "classifier": "classifier",
        "voiceprint": "voiceprint",
        "np_module": "np",
        "torch_module": "torch",
        "torchaudio_module": "torchaudio",
        "device": "cuda:0",
    }
    initialize_runtime.assert_called_once_with(
        enabled=True,
        requested_device="cpu",
        speaker_master="/tmp/master.npy",
        logger=mock.ANY,
    )


def test_run_speaker_auth_enabled_delegates_to_helper() -> None:
    enabled_check = mock.Mock(return_value=True)

    ok = run_speaker_auth_enabled(
        classifier="classifier",
        voiceprint="voiceprint",
        enabled_check=enabled_check,
    )

    assert ok is True
    enabled_check.assert_called_once_with(
        classifier="classifier",
        voiceprint="voiceprint",
    )


def test_run_speaker_identity_verification_returns_success_when_voiceprint_is_missing() -> None:
    ok, err = run_speaker_identity_verification(
        wav_path=Path("/tmp/test.wav"),
        classifier=None,
        voiceprint=None,
        torchaudio_module=None,
        torch_module=None,
        np_module=None,
        device="cpu",
        threshold=0.5,
        topk=5,
        auth_error_text="auth failed",
        logger=lambda _: None,
        log_label="test",
        intent="system_status_report",
        verify_identity=None,
    )

    assert ok is True
    assert err is None


def test_run_speaker_identity_verification_delegates_to_helper() -> None:
    verify_identity = mock.Mock(return_value=(True, None))

    ok, err = run_speaker_identity_verification(
        wav_path=Path("/tmp/test.wav"),
        classifier="classifier",
        voiceprint="voiceprint",
        torchaudio_module="torchaudio",
        torch_module="torch",
        np_module="np",
        device="cuda:0",
        threshold=0.6,
        topk=7,
        auth_error_text="auth failed",
        logger=mock.Mock(),
        log_label="test",
        intent="system_status_report",
        verify_identity=verify_identity,
    )

    assert ok is True
    assert err is None
    verify_identity.assert_called_once_with(
        wav_path=Path("/tmp/test.wav"),
        classifier="classifier",
        voiceprint="voiceprint",
        torchaudio_module="torchaudio",
        torch_module="torch",
        np_module="np",
        device="cuda:0",
        threshold=0.6,
        topk=7,
        auth_error_text="auth failed",
        logger=mock.ANY,
        log_label="test",
        intent="system_status_report",
    )


class _FakeSignal:
    def to(self, _device: str) -> _FakeSignal:
        return self


class _FakeEmbeddings:
    def __init__(self, values: np.ndarray) -> None:
        self._values = values

    def squeeze(self) -> _FakeEmbeddings:
        return self

    def cpu(self) -> _FakeEmbeddings:
        return self

    def numpy(self) -> np.ndarray:
        return self._values


class _FakeClassifier:
    def __init__(self, embedding: np.ndarray) -> None:
        self._embedding = embedding

    def encode_batch(self, _signal: _FakeSignal) -> _FakeEmbeddings:
        return _FakeEmbeddings(self._embedding)


class _FakeTorch:
    @staticmethod
    def no_grad():
        return nullcontext()


def _fake_resample(_src: int, _dest: int) -> None:
    raise AssertionError("Resample should not be called in this test")


class _FakeTorchaudio:
    transforms = SimpleNamespace(Resample=_fake_resample)

    @staticmethod
    def load(_path: str) -> tuple[_FakeSignal, int]:
        return _FakeSignal(), 16_000


def test_run_speaker_identity_verification_fallback_passes_when_similarity_exceeds_threshold(
) -> None:
    logs: list[str] = []

    ok, err = run_speaker_identity_verification(
        wav_path=Path("/tmp/test.wav"),
        classifier=_FakeClassifier(np.array([1.0, 0.0])),
        voiceprint=np.array([1.0, 0.0]),
        torchaudio_module=_FakeTorchaudio(),
        torch_module=_FakeTorch(),
        np_module=np,
        device="cpu",
        threshold=0.5,
        topk=5,
        auth_error_text="auth failed",
        logger=logs.append,
        log_label="test",
        intent="system_status_report",
        verify_identity=None,
    )

    assert ok is True
    assert err is None
    assert len(logs) == 1
    assert logs[0].startswith(
        "test AUTH PASSED: intent=system_status_report similarity=1.0000 SV_elapsed="
    )


def test_run_speaker_identity_verification_fallback_rejects_below_threshold() -> None:
    logs: list[str] = []

    ok, err = run_speaker_identity_verification(
        wav_path=Path("/tmp/test.wav"),
        classifier=_FakeClassifier(np.array([0.0, 1.0])),
        voiceprint=np.array([1.0, 0.0]),
        torchaudio_module=_FakeTorchaudio(),
        torch_module=_FakeTorch(),
        np_module=np,
        device="cpu",
        threshold=0.5,
        topk=5,
        auth_error_text="auth failed",
        logger=logs.append,
        log_label="test",
        intent="system_status_report",
        verify_identity=None,
    )

    assert ok is False
    assert err == "auth failed"
    assert len(logs) == 1
    assert logs[0].startswith(
        "test AUTH FAILED: intent=system_status_report "
        "similarity=0.0000 (threshold=0.5) SV_elapsed="
    )


def test_run_speaker_identity_verification_fallback_returns_auth_error_on_exception() -> None:
    logs: list[str] = []

    torchaudio_module = mock.Mock()
    torchaudio_module.load.side_effect = RuntimeError("boom")

    ok, err = run_speaker_identity_verification(
        wav_path=Path("/tmp/test.wav"),
        classifier=_FakeClassifier(np.array([1.0, 0.0])),
        voiceprint=np.array([1.0, 0.0]),
        torchaudio_module=torchaudio_module,
        torch_module=_FakeTorch(),
        np_module=np,
        device="cpu",
        threshold=0.5,
        topk=5,
        auth_error_text="auth failed",
        logger=logs.append,
        log_label="test",
        intent="system_status_report",
        verify_identity=None,
    )

    assert ok is False
    assert err == "auth failed"
    assert logs == ["Speaker ID verification error: boom"]
