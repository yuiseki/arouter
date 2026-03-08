from __future__ import annotations

from arouter import run_system_normal_mode, run_system_webcam_mode


def test_run_system_webcam_mode_minimizes_then_shows_webcam() -> None:
    events: list[str] = []

    out = run_system_webcam_mode(
        minimize_live_camera=lambda: events.append("minimize") or "street minimized",
        god_mode_layout=lambda mode: events.append(f"god:{mode}") or "webcam ok",
    )

    assert out == "street minimized; webcam ok"
    assert events == ["minimize", "god:frontmost"]


def test_run_system_normal_mode_runs_fullscreen_then_backmost_then_compact_and_minimize() -> None:
    events: list[str] = []

    out = run_system_normal_mode(
        god_mode_layout=lambda mode: events.append(f"god:{mode}") or f"god {mode}",
        show_live_camera_compact=lambda: events.append("compact") or "compact ok",
        minimize_other_windows=lambda: events.append("minimize") or "minimized ok",
    )

    assert out == "god backmost; compact ok; minimized ok"
    assert events == ["god:full-screen", "god:backmost", "compact", "minimize"]


def test_run_system_normal_mode_collects_individual_step_errors() -> None:
    def god_mode_layout(mode: str) -> str:
        if mode == "full-screen":
            raise RuntimeError("fullscreen failed")
        return f"god {mode}"

    out = run_system_normal_mode(
        god_mode_layout=god_mode_layout,
        show_live_camera_compact=lambda: (_ for _ in ()).throw(RuntimeError("compact failed")),
        minimize_other_windows=lambda: (_ for _ in ()).throw(RuntimeError("minimize failed")),
    )

    assert out == (
        "god_mode_layout error: fullscreen failed; "
        "live_cam_wall error: compact failed; "
        "minimize error: minimize failed"
    )
