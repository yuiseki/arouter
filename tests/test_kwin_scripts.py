from __future__ import annotations

from arouter import (
    build_kwin_load_script_command,
    build_kwin_start_script_command,
    build_kwin_unload_script_command,
    build_live_cam_layout_script,
    build_live_cam_minimize_script,
    build_minimize_other_windows_script,
    build_window_frame_geometry_script,
)


def test_build_kwin_load_script_command_matches_qdbus_contract() -> None:
    assert build_kwin_load_script_command("/tmp/demo.js", "plugin-name") == [
        "qdbus",
        "org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.loadScript",
        "/tmp/demo.js",
        "plugin-name",
    ]


def test_build_kwin_start_and_unload_commands_match_qdbus_contract() -> None:
    assert build_kwin_start_script_command() == [
        "qdbus",
        "org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.start",
    ]
    assert build_kwin_unload_script_command("plugin-name") == [
        "qdbus",
        "org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.unloadScript",
        "plugin-name",
    ]


def test_build_live_cam_layout_script_embeds_targets_and_flags() -> None:
    script = build_live_cam_layout_script(
        [{"pid": 123, "x": 1, "y": 2, "w": 3, "h": 4}],
        keep_above=False,
        no_border=True,
    )

    assert "var keepAbove = false;" in script
    assert "var noBorder = true;" in script
    assert "{ pid: 123, x: 1, y: 2, w: 3, h: 4 }" in script
    assert "c.keepAbove = keepAbove;" in script
    assert "c.noBorder = noBorder;" in script


def test_build_live_cam_minimize_script_embeds_target_pids() -> None:
    script = build_live_cam_minimize_script([123, 456])

    assert "var targetPids = {" in script
    assert "123: true" in script
    assert "456: true" in script
    assert "c.keepAbove = false;" in script
    assert "c.minimized = true;" in script


def test_build_minimize_other_windows_script_embeds_skip_pid_filter() -> None:
    script = build_minimize_other_windows_script([123, 456])

    assert "var skipPids = [123, 456];" in script
    assert "c.specialWindow || c.skipTaskbar || !c.minimizable" in script
    assert "c.onAllDesktops" in script
    assert "skipPids.indexOf(c.pid) !== -1" in script
    assert "c.fullScreen = false;" in script
    assert "c.minimized = true;" in script


def test_build_window_frame_geometry_script_embeds_target_pid_and_geometry() -> None:
    script = build_window_frame_geometry_script(
        pid=321,
        geom={"x": 1, "y": 2, "w": 3, "h": 4},
        no_border=False,
    )

    assert "var targetPid = 321;" in script
    assert "var noBorder = false;" in script
    assert "var target = { x: 1, y: 2, w: 3, h: 4 };" in script
    assert "if (c.pid !== targetPid) continue;" in script
    assert "c.noBorder = noBorder;" in script
