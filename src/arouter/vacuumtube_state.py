from __future__ import annotations

from typing import Any


def vacuumtube_is_watch_state(snapshot: dict[str, Any]) -> bool:
    return str(snapshot.get("hash") or "").startswith("#/watch")


def vacuumtube_video_playing(snapshot: dict[str, Any]) -> bool:
    video = snapshot.get("video")
    return isinstance(video, dict) and not bool(video.get("paused", True))


def vacuumtube_video_current_time(snapshot: dict[str, Any]) -> float:
    video = snapshot.get("video")
    if not isinstance(video, dict):
        return 0.0
    try:
        return float(video.get("currentTime") or 0.0)
    except Exception:
        return 0.0


def vacuumtube_is_home_browse_state(snapshot: dict[str, Any]) -> bool:
    if str(snapshot.get("hash") or "") != "#/":
        return False
    if bool(snapshot.get("accountSelectHint")):
        return False
    if bool(snapshot.get("watchUiHint")):
        return False

    tiles_count = int(snapshot.get("tilesCount") or 0)
    if tiles_count <= 0:
        return False

    if vacuumtube_video_playing(snapshot) and vacuumtube_video_current_time(snapshot) >= 0.15:
        return False

    if bool(snapshot.get("homeHint")):
        return True
    return tiles_count >= 6


def vacuumtube_needs_hard_reload_home(snapshot: dict[str, Any]) -> bool:
    if str(snapshot.get("hash") or "") != "#/":
        return False
    tiles_count = int(snapshot.get("tilesCount") or 0)
    if tiles_count == 0:
        return True
    if bool(snapshot.get("watchUiHint")):
        return True
    return False
