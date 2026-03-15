from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest import mock

import pytest

from arouter import execute_command, execute_simulated_mic_command_host_runtime
from arouter.execution import run_good_morning_host_runtime, run_good_night_host_runtime


@dataclass(frozen=True)
class AcceptanceCase:
    text: str
    intent: str
    result_fragments: tuple[str, ...]
    called_methods: tuple[str, ...]


class AcceptanceRuntime(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__()
        self.log = mock.Mock()
        self._god_mode_last_layout = None
        self._live_cam_last_layout = None
        self._contextualize_command_with_vacuumtube_state = lambda _text, cmd: cmd
        self._record_successful_command_activity = mock.Mock()
        self._set_system_locked = mock.Mock(return_value=True)
        self._play_music = mock.Mock(return_value="music play ok")
        self.system_load_check = mock.Mock(
            return_value="system load monitor reused (tmux=sysmon)"
        )
        self._play_morning_news = mock.Mock(return_value="morning news ok")
        self._fullscreen_morning_news = mock.Mock(return_value="fullscreen ok")
        self._lights_on = mock.Mock(return_value="switchbot lights on: ok")
        self._pause_for_night = mock.Mock(
            return_value='good_night pause {"ok": true, "afterPaused": true}'
        )
        self._lights_off = mock.Mock(return_value="switchbot lights off: ok")
        self.good_morning = mock.Mock(
            side_effect=lambda: run_good_morning_host_runtime(runtime=self)
        )
        self.good_night = mock.Mock(
            side_effect=lambda: run_good_night_host_runtime(runtime=self)
        )
        self._execute_command = lambda cmd: execute_command(self, cmd)


@pytest.mark.parametrize(
    ("case"),
    [
        AcceptanceCase(
            text="システム バイオメトリクス認証",
            intent="system_biometric_auth",
            result_fragments=("system unlocked by biometric authentication",),
            called_methods=(),
        ),
        AcceptanceCase(
            text="システム 負荷を確認して",
            intent="system_load_check",
            result_fragments=("system load monitor reused",),
            called_methods=("system_load_check",),
        ),
        AcceptanceCase(
            text="システム 音楽を流して",
            intent="music_play",
            result_fragments=("music play ok",),
            called_methods=("_play_music",),
        ),
        AcceptanceCase(
            text="システム おはよう",
            intent="good_morning",
            result_fragments=(
                "good_morning",
                "fullscreen=fullscreen ok",
                "lights=switchbot lights on: ok",
            ),
            called_methods=(
                "good_morning",
                "_play_morning_news",
                "_fullscreen_morning_news",
                "_lights_on",
            ),
        ),
        AcceptanceCase(
            text="システム おやすみ",
            intent="good_night",
            result_fragments=(
                'good_night pause {"ok": true, "afterPaused": true}',
                "lights=switchbot lights off: ok",
            ),
            called_methods=("good_night", "_pause_for_night", "_lights_off"),
        ),
    ],
)
def test_simulated_mic_command_acceptance_suite(case: AcceptanceCase) -> None:
    runtime = AcceptanceRuntime()

    payload = execute_simulated_mic_command_host_runtime(runtime=runtime, text=case.text)

    assert payload["ok"] is True
    assert payload["intent"] == case.intent
    assert payload["normalized"]
    assert payload["ackText"]
    for fragment in case.result_fragments:
        assert fragment in payload["result"]
    for method_name in case.called_methods:
        getattr(runtime, method_name).assert_called_once_with()
    runtime._record_successful_command_activity.assert_called_once_with()


def test_simulated_mic_command_acceptance_suite_unlock_reason_is_stable() -> None:
    runtime = AcceptanceRuntime()

    payload = execute_simulated_mic_command_host_runtime(
        runtime=runtime,
        text="システム バイオメトリクス認証",
    )

    assert payload["result"] == "system unlocked by biometric authentication"
    runtime._set_system_locked.assert_called_once_with(
        False,
        reason="command:system_biometric_auth",
    )
