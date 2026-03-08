from __future__ import annotations

from typing import Any


def build_kwin_load_script_command(script_path: str, plugin_name: str) -> list[str]:
    return [
        "qdbus",
        "org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.loadScript",
        script_path,
        plugin_name,
    ]


def build_kwin_start_script_command() -> list[str]:
    return [
        "qdbus",
        "org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.start",
    ]


def build_kwin_unload_script_command(plugin_name: str) -> list[str]:
    return [
        "qdbus",
        "org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.unloadScript",
        plugin_name,
    ]


def build_live_cam_layout_script(
    targets: list[dict[str, Any]],
    *,
    keep_above: bool = True,
    no_border: bool = True,
) -> str:
    js_lines: list[str] = [
        f"var keepAbove = {'true' if keep_above else 'false'};",
        f"var noBorder = {'true' if no_border else 'false'};",
        "var targets = [",
    ]
    for target in targets:
        js_lines.append(
            "  { pid: "
            f"{int(target['pid'])}, x: {int(target['x'])}, y: {int(target['y'])}, "
            f"w: {int(target['w'])}, h: {int(target['h'])} }}"
            ","
        )
    js_lines += [
        "];",
        "var clients = workspace.clientList();",
        "for (var ti = 0; ti < targets.length; ++ti) {",
        "  var target = targets[ti];",
        "  for (var i = 0; i < clients.length; ++i) {",
        "    var c = clients[i];",
        "    if (c.pid !== target.pid) continue;",
        "    try { c.fullScreen = false; } catch (e1) {}",
        "    try { c.minimized = false; } catch (e2) {}",
        "    try { c.keepAbove = keepAbove; } catch (e3) {}",
        "    try { c.noBorder = noBorder; } catch (e4) {}",
        "    var g = c.frameGeometry;",
        "    g.x = target.x; g.y = target.y; g.width = target.w; g.height = target.h;",
        "    c.frameGeometry = g;",
        "    break;",
        "  }",
        "}",
        "",
    ]
    return "\n".join(js_lines)


def build_live_cam_minimize_script(pids: list[int]) -> str:
    js_lines = ["var targetPids = {"]
    for pid in pids:
        js_lines.append(f"  {int(pid)}: true,")
    js_lines += [
        "};",
        "var clients = workspace.clientList();",
        "for (var i = 0; i < clients.length; ++i) {",
        "  var c = clients[i];",
        "  if (!targetPids[c.pid]) continue;",
        "  try { c.keepAbove = false; } catch (e1) {}",
        "  try { c.minimized = true; } catch (e2) {}",
        "}",
        "",
    ]
    return "\n".join(js_lines)


def build_minimize_other_windows_script(skip_pids: list[int]) -> str:
    skip_pids_js = "[" + ", ".join(str(pid) for pid in sorted(int(pid) for pid in skip_pids)) + "]"
    js_lines = [
        f"var skipPids = {skip_pids_js};",
        "var minimized = 0;",
        "var clients = workspace.clientList();",
        "for (var i = 0; i < clients.length; ++i) {",
        "  var c = clients[i];",
        "  if (c.specialWindow || c.skipTaskbar || !c.minimizable) continue;",
        "  if (c.onAllDesktops) continue;",
        "  if (skipPids.indexOf(c.pid) !== -1) continue;",
        "  try { c.fullScreen = false; } catch(e1) {}",
        "  try { c.minimized = true; } catch(e2) {}",
        "  minimized++;",
        "}",
    ]
    return "\n".join(js_lines)


def build_window_frame_geometry_script(
    *,
    pid: int,
    geom: dict[str, int],
    no_border: bool = True,
) -> str:
    js_lines = [
        f"var targetPid = {int(pid)};",
        f"var noBorder = {'true' if no_border else 'false'};",
        "var target = { "
        f"x: {int(geom['x'])}, y: {int(geom['y'])}, "
        f"w: {int(geom['w'])}, h: {int(geom['h'])} "
        "};",
        "var clients = workspace.clientList();",
        "for (var i = 0; i < clients.length; ++i) {",
        "  var c = clients[i];",
        "  if (c.pid !== targetPid) continue;",
        "  try { c.fullScreen = false; } catch (e1) {}",
        "  try { c.minimized = false; } catch (e2) {}",
        "  try { c.noBorder = noBorder; } catch (e3) {}",
        "  var g = c.frameGeometry;",
        "  g.x = target.x; g.y = target.y; g.width = target.w; g.height = target.h;",
        "  c.frameGeometry = g;",
        "  break;",
        "}",
        "",
    ]
    return "\n".join(js_lines)
