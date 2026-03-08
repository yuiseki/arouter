from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from arouter import resolve_biometric_arg_path


def test_resolve_biometric_arg_path_prefers_explicit_arg(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    args = SimpleNamespace(signal_file="~/signals/unlock.signal")

    path = resolve_biometric_arg_path(
        args=args,
        attr_name="signal_file",
        default_path="/tmp/fallback.signal",
    )

    assert path == tmp_path / "signals" / "unlock.signal"


def test_resolve_biometric_arg_path_uses_default_when_attr_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    args = SimpleNamespace()

    path = resolve_biometric_arg_path(
        args=args,
        attr_name="missing_attr",
        default_path="~/signals/lock.signal",
    )

    assert path == tmp_path / "signals" / "lock.signal"
