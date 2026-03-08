from __future__ import annotations

import json
import time
from pathlib import Path

from arouter import consume_signal_file, write_signal_file


def test_consume_signal_file_is_edge_triggered(tmp_path: Path) -> None:
    signal_path = tmp_path / "unlock.signal"
    write_signal_file(signal_path=signal_path, action="unlock", requested_at=123.0)

    consumed, seen_mtime = consume_signal_file(signal_path=signal_path, seen_mtime=0.0)
    consumed_again, seen_mtime_again = consume_signal_file(
        signal_path=signal_path,
        seen_mtime=seen_mtime,
    )

    assert consumed is True
    assert seen_mtime > 0.0
    assert consumed_again is False
    assert seen_mtime_again == seen_mtime


def test_consume_signal_file_detects_newer_write(tmp_path: Path) -> None:
    signal_path = tmp_path / "lock.signal"
    write_signal_file(signal_path=signal_path, action="lock", requested_at=1.0)
    _, seen_mtime = consume_signal_file(signal_path=signal_path, seen_mtime=0.0)

    time.sleep(0.02)
    write_signal_file(signal_path=signal_path, action="lock", requested_at=2.0)

    consumed, next_seen_mtime = consume_signal_file(
        signal_path=signal_path,
        seen_mtime=seen_mtime,
    )

    assert consumed is True
    assert next_seen_mtime > seen_mtime


def test_consume_signal_file_returns_false_for_missing_path(tmp_path: Path) -> None:
    signal_path = tmp_path / "missing.signal"

    consumed, seen_mtime = consume_signal_file(signal_path=signal_path, seen_mtime=0.0)

    assert consumed is False
    assert seen_mtime == 0.0


def test_write_signal_file_writes_json_payload(tmp_path: Path) -> None:
    signal_path = tmp_path / "nested" / "lock.signal"

    written_path = write_signal_file(signal_path=signal_path, action="lock", requested_at=45.5)

    assert written_path == signal_path
    payload = json.loads(signal_path.read_text(encoding="utf-8"))
    assert payload == {"action": "lock", "requestedAt": 45.5}
