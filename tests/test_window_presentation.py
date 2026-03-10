from __future__ import annotations

from typing import Any

import pytest

from arouter import (
    build_top_right_position_attempt_plan,
    build_top_right_position_result,
    build_window_presentation_snapshot,
    finalize_top_right_position_result,
    geometry_close,
    is_window_fullscreenish,
    parse_desktop_size_from_wmctrl_output,
    parse_screen_size_from_xrandr_output,
    parse_work_area_from_wmctrl_output,
    resolve_expected_top_right_geometry,
    resolve_window_restore_plan,
    run_top_right_position_flow,
    run_top_right_position_host_runtime_flow,
    run_window_restore_flow,
    run_window_restore_host_runtime_flow,
    top_right_region_from_screen_and_work_area,
)


def _record_wmctrl_move(
    events: list[str],
    win_id: str,
    geom: dict[str, Any],
) -> None:
    events.append(f"wmctrl:{win_id}:{geom['x']}")


def _unexpected_restore_callback(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("unexpected")


def _unexpected_restore_result(*_args: object, **_kwargs: object) -> bool:
    raise AssertionError("unexpected")


def test_geometry_close_within_tolerance() -> None:
    assert geometry_close(
        {"x": 2055, "y": 30, "w": 2038, "h": 1048},
        {"x": 2048, "y": 28, "w": 2048, "h": 1052},
        tol=12,
    )


def test_geometry_close_outside_tolerance() -> None:
    assert not geometry_close(
        {"x": 1448, "y": 720, "w": 1199, "h": 677},
        {"x": 2048, "y": 28, "w": 2048, "h": 1052},
        tol=24,
    )


def test_build_window_presentation_snapshot_sets_fields() -> None:
    assert build_window_presentation_snapshot(window_id="0x123", fullscreen=True) == {
        "window_id": "0x123",
        "fullscreen": True,
    }


def test_build_top_right_position_result_sets_initial_fields() -> None:
    assert build_top_right_position_result(
        window_id="0x123",
        target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        before={"x": 10, "y": 20, "w": 300, "h": 400},
        tolerance=24,
    ) == {
        "window_id": "0x123",
        "target": {"x": 2048, "y": 0, "w": 2048, "h": 1080},
        "before": {"x": 10, "y": 20, "w": 300, "h": 400},
        "tolerance": 24,
        "ok": False,
        "method": None,
    }


def test_build_top_right_position_attempt_plan_prefers_kwin_then_tile_then_wmctrl() -> None:
    plan = build_top_right_position_attempt_plan(retries=2, has_main_pid=True)

    assert [step["method"] for step in plan] == [
        "kwin_frame_noborder_attempt_1",
        "kwin_frame_noborder_attempt_2",
        "kwin_tile_attempt_1",
        "kwin_tile_attempt_2",
        "wmctrl_move_resize",
        "kwin_frame_noborder_after_wmctrl",
        "kwin_tile_after_wmctrl",
    ]


def test_build_top_right_position_attempt_plan_skips_kwin_when_pid_missing() -> None:
    plan = build_top_right_position_attempt_plan(retries=2, has_main_pid=False)

    assert [step["method"] for step in plan] == [
        "kwin_tile_attempt_1",
        "kwin_tile_attempt_2",
        "wmctrl_move_resize",
        "kwin_tile_after_wmctrl",
    ]


def test_finalize_top_right_position_result_marks_success_when_geometry_matches() -> None:
    result = build_top_right_position_result(
        window_id="0x123",
        target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        before=None,
        tolerance=24,
    )

    updated = finalize_top_right_position_result(
        result,
        geom={"x": 2048, "y": 8, "w": 2040, "h": 1080},
        expected={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        tol=24,
        method="kwin_tile_attempt_1",
    )

    assert updated["ok"] is True
    assert updated["method"] == "kwin_tile_attempt_1"
    assert updated["after"] == {"x": 2048, "y": 8, "w": 2040, "h": 1080}


def test_finalize_top_right_position_result_keeps_failure_and_records_last_geometry() -> None:
    result = build_top_right_position_result(
        window_id="0x123",
        target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        before=None,
        tolerance=24,
    )

    updated = finalize_top_right_position_result(
        result,
        geom={"x": 100, "y": 100, "w": 800, "h": 600},
        expected={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        tol=24,
        method="wmctrl_move_resize",
    )

    assert updated["ok"] is False
    assert updated["method"] == "wmctrl_move_resize"
    assert updated["after"] == {"x": 100, "y": 100, "w": 800, "h": 600}


def test_resolve_window_restore_plan_prefers_fullscreen() -> None:
    assert resolve_window_restore_plan(
        {"window_id": "0x123", "fullscreen": True},
        fallback_window_id="0x999",
        is_fullscreenish=False,
    ) == {"window_id": "0x123", "action": "fullscreen"}


def test_resolve_window_restore_plan_skips_top_right_when_current_window_looks_fullscreen() -> None:
    assert resolve_window_restore_plan(
        {"window_id": "0x123", "fullscreen": False},
        fallback_window_id="0x999",
        is_fullscreenish=True,
    ) == {"window_id": "0x123", "action": "skip_top_right"}


def test_resolve_window_restore_plan_uses_fallback_window_id_for_top_right() -> None:
    assert resolve_window_restore_plan(
        {"fullscreen": False},
        fallback_window_id="0x999",
        is_fullscreenish=False,
    ) == {"window_id": "0x999", "action": "top_right"}


def test_resolve_expected_top_right_geometry_uses_intersection_when_available() -> None:
    assert resolve_expected_top_right_geometry(
        screen=(4096, 2160),
        work_area=(0, 0, 4096, 2116),
        fallback_geometry={"x": 1, "y": 2, "w": 3, "h": 4},
    ) == {"x": 2048, "y": 0, "w": 2048, "h": 1080}


def test_resolve_expected_top_right_geometry_falls_back_when_screen_missing() -> None:
    assert resolve_expected_top_right_geometry(
        screen=None,
        work_area=None,
        fallback_geometry={"x": 1, "y": 2, "w": 3, "h": 4},
    ) == {"x": 1, "y": 2, "w": 3, "h": 4}


def test_parse_desktop_size_from_wmctrl_output_prefers_current_desktop() -> None:
    assert parse_desktop_size_from_wmctrl_output(
        "0  - DG: 1280x720 VP: 0,0 WA: 0,0 1280x680\n"
        "1  * DG: 1920x1080 VP: 0,0 WA: 0,0 1920x1040\n"
    ) == (1920, 1080)


def test_parse_screen_size_from_xrandr_output_prefers_primary_then_connected() -> None:
    assert parse_screen_size_from_xrandr_output(
        "HDMI-0 connected 1280x720+0+0\n"
        "DP-0 connected primary 4096x2160+0+0\n"
    ) == (4096, 2160)


def test_parse_work_area_from_wmctrl_output_returns_current_desktop_work_area() -> None:
    assert parse_work_area_from_wmctrl_output(
        "0  * DG: 4096x2160 VP: 0,0 WA: 0,0 4096x2116\n"
    ) == (0, 0, 4096, 2116)


def test_top_right_region_intersects_work_area() -> None:
    assert top_right_region_from_screen_and_work_area(
        screen_w=4096,
        screen_h=2160,
        work_area=(0, 0, 4096, 2116),
    ) == (2048, 0, 2048, 1080)


def test_top_right_region_rejects_invalid_screen_size() -> None:
    with pytest.raises(ValueError, match="invalid screen size"):
        top_right_region_from_screen_and_work_area(
            screen_w=0,
            screen_h=2160,
            work_area=None,
        )


def test_is_window_fullscreenish_matches_near_fullscreen_geometry() -> None:
    assert is_window_fullscreenish(
        {"x": 0, "y": 8, "w": 1910, "h": 1080},
        (1920, 1080),
        tol=16,
    )


def test_is_window_fullscreenish_rejects_small_window() -> None:
    assert not is_window_fullscreenish(
        {"x": 100, "y": 100, "w": 640, "h": 480},
        (1920, 1080),
    )


def test_run_top_right_position_flow_returns_already_ok_without_actions() -> None:
    events: list[str] = []

    result = run_top_right_position_flow(
        win_id="0x123",
        target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        before={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        tolerance=24,
        retries=2,
        main_pid=123,
        clear_fullscreen_if_needed=lambda: events.append("clear"),
        kwin_frame_action=lambda pid, geom: events.append(f"kwin_frame:{pid}:{geom['x']}"),
        kwin_tile_action=lambda: events.append("kwin_tile"),
        wmctrl_move_resize_action=lambda win_id, geom: _record_wmctrl_move(
            events,
            win_id,
            geom,
        ),
        geometry_fetcher=lambda _win_id: {"x": 2048, "y": 0, "w": 2048, "h": 1080},
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
    )

    assert result["ok"] is True
    assert result["method"] == "already_ok"
    assert events == []


def test_run_top_right_position_flow_retries_after_kwin_frame_failure() -> None:
    events: list[str] = []
    geometries = [
        {"x": 100, "y": 100, "w": 800, "h": 600},
        {"x": 2048, "y": 4, "w": 2044, "h": 1080},
    ]

    def kwin_frame_action(_pid: int, _geom: dict[str, Any]) -> None:
        raise RuntimeError("kwin unavailable")

    def geometry_fetcher(_win_id: str) -> dict[str, Any]:
        return geometries.pop(0)

    result = run_top_right_position_flow(
        win_id="0x123",
        target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        before={"x": 0, "y": 0, "w": 640, "h": 480},
        tolerance=24,
        retries=1,
        main_pid=321,
        clear_fullscreen_if_needed=lambda: events.append("clear"),
        kwin_frame_action=kwin_frame_action,
        kwin_tile_action=lambda: events.append("kwin_tile"),
        wmctrl_move_resize_action=lambda win_id, geom: _record_wmctrl_move(
            events,
            win_id,
            geom,
        ),
        geometry_fetcher=geometry_fetcher,
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
    )

    assert result["ok"] is True
    assert result["method"] == "wmctrl_move_resize"
    assert events == [
        "clear",
        "kwin_tile",
        "sleep:0.35",
        "wmctrl:0x123:2048",
        "sleep:0.25",
    ]


def test_run_top_right_position_flow_returns_last_failed_geometry_when_all_attempts_fail() -> None:
    events: list[str] = []
    geometries = [
        {"x": 100, "y": 100, "w": 800, "h": 600},
        {"x": 110, "y": 110, "w": 810, "h": 610},
        {"x": 120, "y": 120, "w": 820, "h": 620},
    ]

    result = run_top_right_position_flow(
        win_id="0x123",
        target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
        before=None,
        tolerance=24,
        retries=1,
        main_pid=None,
        clear_fullscreen_if_needed=lambda: events.append("clear"),
        kwin_frame_action=lambda _pid, _geom: events.append("kwin_frame"),
        kwin_tile_action=lambda: events.append("kwin_tile"),
        wmctrl_move_resize_action=lambda win_id, geom: _record_wmctrl_move(
            events,
            win_id,
            geom,
        ),
        geometry_fetcher=lambda _win_id: geometries.pop(0),
        sleep=lambda seconds: events.append(f"sleep:{seconds}"),
    )

    assert result["ok"] is False
    assert result["method"] == "kwin_tile_after_wmctrl"
    assert result["after"] == {"x": 120, "y": 120, "w": 820, "h": 620}
    assert events == [
        "clear",
        "kwin_tile",
        "sleep:0.35",
        "wmctrl:0x123:2048",
        "sleep:0.25",
        "kwin_tile",
        "sleep:0.35",
    ]


def test_run_window_restore_flow_executes_fullscreen_branch() -> None:
    events: list[str] = []

    result = run_window_restore_flow(
        presentation={"window_id": "0x123", "fullscreen": True},
        fallback_window_id="0x999",
        is_fullscreenish=False,
        activate_window=lambda win_id: events.append(f"activate:{win_id}"),
        set_fullscreen=lambda win_id, enabled: events.append(f"fullscreen:{win_id}:{enabled}"),
        wait_fullscreen=lambda win_id, enabled, timeout_sec: events.append(
            f"wait:{win_id}:{enabled}:{timeout_sec}"
        )
        or True,
        geometry_fetcher=lambda win_id: {"window_id": win_id, "x": 0, "y": 0},
        ensure_top_right_position=lambda: {"ok": True},
    )

    assert result == {
        "action": "fullscreen",
        "window_id": "0x123",
        "fullscreen": True,
        "after": {"window_id": "0x123", "x": 0, "y": 0},
    }
    assert events == [
        "activate:0x123",
        "fullscreen:0x123:True",
        "wait:0x123:True:3.0",
    ]


def test_run_window_restore_flow_skips_top_right_when_guarded() -> None:
    result = run_window_restore_flow(
        presentation={"window_id": "0x123", "fullscreen": False},
        fallback_window_id="0x999",
        is_fullscreenish=True,
        activate_window=_unexpected_restore_callback,
        set_fullscreen=_unexpected_restore_callback,
        wait_fullscreen=_unexpected_restore_result,
        geometry_fetcher=_unexpected_restore_callback,
        ensure_top_right_position=_unexpected_restore_callback,
    )

    assert result == {"action": "skip_top_right", "window_id": "0x123"}


def test_run_window_restore_flow_uses_top_right_branch() -> None:
    result = run_window_restore_flow(
        presentation={"window_id": "0x123", "fullscreen": False},
        fallback_window_id="0x999",
        is_fullscreenish=False,
        activate_window=_unexpected_restore_callback,
        set_fullscreen=_unexpected_restore_callback,
        wait_fullscreen=_unexpected_restore_result,
        geometry_fetcher=_unexpected_restore_callback,
        ensure_top_right_position=lambda: {"ok": True, "method": "delegated"},
    )

    assert result == {
        "action": "top_right",
        "window_id": "0x123",
        "position": {"ok": True, "method": "delegated"},
    }


def test_run_window_restore_host_runtime_flow_reads_runtime_methods() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.events: list[str] = []

        def _current_window_is_fullscreenish(self, win_id: str) -> bool:
            self.events.append(f"fullscreenish:{win_id}")
            return False

        def activate_window(self, win_id: str) -> None:
            self.events.append(f"activate:{win_id}")

        def _set_fullscreen(self, win_id: str, *, enabled: bool) -> None:
            self.events.append(f"set:{win_id}:{enabled}")

        def _wait_fullscreen(
            self,
            win_id: str,
            *,
            enabled: bool,
            timeout_sec: float,
        ) -> bool:
            self.events.append(f"wait:{win_id}:{enabled}:{timeout_sec}")
            return True

        def get_window_geometry(self, win_id: str) -> dict[str, Any]:
            return {"window_id": win_id, "x": 0, "y": 0}

        def ensure_top_right_position(self) -> dict[str, Any]:
            return {"ok": True, "method": "delegated"}

    runtime = FakeRuntime()

    out = run_window_restore_host_runtime_flow(
        runtime=runtime,
        presentation={"window_id": "0x123", "fullscreen": True},
        fallback_window_id="0x999",
    )

    assert out == {
        "action": "fullscreen",
        "window_id": "0x123",
        "fullscreen": True,
        "after": {"window_id": "0x123", "x": 0, "y": 0},
    }
    assert runtime.events == [
        "fullscreenish:0x999",
        "activate:0x123",
        "set:0x123:True",
        "wait:0x123:True:3.0",
    ]


def test_run_top_right_position_host_runtime_flow_reads_runtime_methods() -> None:
    class FakeRuntime:
        geometry_tolerance = 40

        def __init__(self) -> None:
            self.events: list[tuple[str, Any]] = []
            self._after = {"x": 2048, "y": 0, "w": 2048, "h": 1080}

        def _clear_fullscreen_if_needed(self, win_id: str) -> None:
            self.events.append(("clear", win_id))

        def _kwin_set_frame_geometry_for_pid(
            self,
            *,
            pid: int,
            geom: dict[str, Any],
            no_border: bool,
        ) -> None:
            self.events.append(("kwin", pid, dict(geom), no_border))

        def tile_top_right(self) -> None:
            self.events.append(("tile", None))

        def _wmctrl_move_resize(self, win_id: str, geom: dict[str, Any]) -> None:
            self.events.append(("wmctrl", win_id, dict(geom)))

        def get_window_geometry(self, win_id: str) -> dict[str, Any] | None:
            self.events.append(("geom", win_id))
            return dict(self._after)

    runtime = FakeRuntime()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "arouter.window_presentation.time.sleep",
            lambda sec: runtime.events.append(("sleep", sec)),
        )
        out = run_top_right_position_host_runtime_flow(
            runtime=runtime,
            win_id="0x123",
            target={"x": 2048, "y": 0, "w": 2048, "h": 1080},
            before={"x": 100, "y": 100, "w": 640, "h": 480},
            retries=1,
            main_pid=4321,
        )

    assert out["ok"] is True
    assert runtime.events[0] == ("clear", "0x123")
    assert runtime.events[1] == (
        "kwin",
        4321,
        {"x": 2048, "y": 0, "w": 2048, "h": 1080},
        True,
    )
