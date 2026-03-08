from __future__ import annotations

import json
import socket
from collections.abc import Callable
from typing import Any

from .vacuumtube_state import vacuumtube_is_watch_state


def build_vacuumtube_context_base(*, ts: float) -> dict[str, Any]:
    return {
        "ts": float(ts),
        "available": False,
        "windowFound": False,
        "fullscreenish": False,
        "quadrantish": False,
        "watchRoute": False,
        "homeRoute": False,
        "videoPlaying": False,
        "videoPaused": None,
    }


def merge_vacuumtube_window_snapshot(
    context: dict[str, Any],
    *,
    window_id: str | None,
    geom: dict[str, Any] | None,
    fullscreenish: bool,
    quadrantish: bool,
) -> dict[str, Any]:
    merged = dict(context)
    merged["quadrantish"] = bool(quadrantish)
    if not window_id:
        return merged

    merged["windowFound"] = True
    if isinstance(geom, dict):
        merged["geom"] = {
            "x": int(geom.get("x") or 0),
            "y": int(geom.get("y") or 0),
            "w": int(geom.get("w") or 0),
            "h": int(geom.get("h") or 0),
        }
    merged["fullscreenish"] = bool(fullscreenish)
    return merged


def merge_vacuumtube_cdp_state(
    context: dict[str, Any],
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(context)
    if not isinstance(state, dict):
        return merged

    hash_value = str(state.get("hash") or "")
    merged["hash"] = hash_value
    merged["watchRoute"] = vacuumtube_is_watch_state(state)
    merged["homeRoute"] = hash_value == "#/"

    video = state.get("video")
    if isinstance(video, dict):
        paused = bool(video.get("paused", True))
        merged["videoPaused"] = paused
        merged["videoPlaying"] = not paused

    merged["accountSelectHint"] = bool(state.get("accountSelectHint"))
    merged["homeHint"] = bool(state.get("homeHint"))
    merged["watchUiHint"] = bool(state.get("watchUiHint"))
    return merged


def finalize_vacuumtube_context(context: dict[str, Any]) -> dict[str, Any]:
    finalized = dict(context)
    finalized["available"] = bool(finalized.get("windowFound")) or bool(finalized.get("hash"))
    return finalized


def is_recoverable_vacuumtube_error(
    err: Exception,
    *,
    timeout_exception_type: type[BaseException] | None = None,
) -> bool:
    if isinstance(err, (TimeoutError, socket.timeout)):
        return True
    if timeout_exception_type and isinstance(err, timeout_exception_type):
        return True

    msg = str(err or "").lower()
    return any(
        token in msg
        for token in (
            "timed out",
            "cdp not ready",
            "vacuumtube window not found",
            "no vacuumtube/youtube tv page target",
            "websocket is already closed",
            "broken pipe",
            "connection reset",
            "connection refused",
        )
    )


def ensure_vacuumtube_started_and_positioned(
    *,
    ensure_running: Callable[[], None],
    wait_window: Callable[[float], str],
    restart_tmux_session: Callable[[], None],
    wait_cdp_ready: Callable[[float], bool],
    select_account_if_needed: Callable[[], None],
    capture_window_presentation: Callable[[str], dict[str, Any]],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
    base_url: str,
) -> dict[str, Any]:
    ensure_running()
    try:
        win_id = wait_window(20.0)
    except Exception as err:
        log(f"VacuumTube window missing after startup; restarting session: {err}")
        restart_tmux_session()
        if not wait_cdp_ready(35.0):
            raise RuntimeError(f"VacuumTube CDP not ready at {base_url}") from err
        win_id = wait_window(20.0)

    select_account_if_needed()
    presentation = capture_window_presentation(win_id)
    if bool(presentation.get("fullscreen")):
        payload = json.dumps(presentation, ensure_ascii=False)
        log(f"VacuumTube window position preserved (fullscreen): {payload}")
        return presentation

    try:
        position = ensure_top_right_position()
        log(f"VacuumTube window position check: {json.dumps(position, ensure_ascii=False)}")
    except Exception as err:
        log(f"tile top-right skipped: {err}")

    return capture_window_presentation(win_id)


def run_vacuumtube_resume_playback(
    *,
    find_window_id: Callable[[], str | None],
    snapshot_state: Callable[[], dict[str, Any]],
    is_watch_state: Callable[[dict[str, Any]], bool],
    confirm_already_playing: Callable[[], None],
    try_resume_current_video: Callable[[], None],
    confirm_dom_resume: Callable[[], None],
    send_space_key: Callable[[], None],
    confirm_space_resume: Callable[[], None],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
) -> str:
    win_id = find_window_id()
    if not win_id:
        return "VacuumTube window not found (no-op)"

    before = snapshot_state()
    if not is_watch_state(before):
        log("resume_playback skipped: not on watch route")
        return "not on watch route (no-op)"

    def log_position(prefix: str) -> None:
        try:
            position = ensure_top_right_position()
            payload = json.dumps(position, ensure_ascii=False)
            log(f"{prefix} window position: {payload}")
        except Exception as err:
            log(f"{prefix} position check skipped: {err}")

    try:
        confirm_already_playing()
        log_position("RESUME already-playing")
        return "watch route already playing (no-op)"
    except Exception:
        pass

    try_resume_current_video()
    try:
        confirm_dom_resume()
        log_position("RESUME post-action")
        return f"resumed playback via DOM ({win_id})"
    except Exception:
        send_space_key()
        confirm_space_resume()
        log_position("RESUME space-toggle")
        return f"resumed playback via Space toggle ({win_id})"


def run_vacuumtube_go_home(
    *,
    presentation_before: dict[str, Any],
    hide_overlay_if_needed: Callable[[], None],
    ensure_home: Callable[[], dict[str, Any]],
    restore_window_presentation: Callable[..., None],
    log: Callable[[str], None],
) -> str:
    hide_overlay_if_needed()
    snapshot = ensure_home()
    try:
        restore_window_presentation(presentation_before, label="YOUTUBE_HOME")
    except Exception as err:
        log(f"YOUTUBE_HOME presentation restore skipped: {err}")
    return "youtube home verified " + json.dumps(
        {"hash": snapshot.get("hash"), "tiles": snapshot.get("tilesCount")},
        ensure_ascii=False,
    )


def run_vacuumtube_play_bgm(
    *,
    get_state: Callable[[], dict[str, Any]],
    send_return_key: Callable[[], None],
    send_space_key: Callable[[], None],
    sleep: Callable[[float], None],
    try_resume_current_video: Callable[[], None],
    confirm_watch_playback: Callable[..., None],
    open_from_home: Callable[[], str],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
) -> str:
    state = get_state()
    if state.get("accountSelectHint"):
        send_return_key()
        sleep(0.6)
        state = get_state()

    def log_position(prefix: str) -> None:
        try:
            position = ensure_top_right_position()
            payload = json.dumps(position, ensure_ascii=False)
            log(f"{prefix} window position: {payload}")
        except Exception as err:
            log(f"{prefix} position check skipped: {err}")

    if str(state.get("hash") or "").startswith("#/watch"):
        try_resume_current_video()
        try:
            confirm_watch_playback(
                timeout_sec=4.0,
                allow_soft_confirm_when_unpaused=True,
            )
            log_position("BGM watch-resume")
            return "watch page detected; confirmed playback"
        except Exception:
            send_space_key()
            confirm_watch_playback(
                timeout_sec=5.0,
                allow_soft_confirm_when_unpaused=True,
            )
            log_position("BGM watch-toggle")
            return "watch page detected; sent Space toggle and confirmed playback"

    return open_from_home()


def run_vacuumtube_open_from_home(
    *,
    label: str,
    scorer: Callable[[dict[str, Any]], float],
    filter_fn: Callable[[dict[str, Any]], bool] | None,
    allow_soft_playback_confirm: bool,
    hide_overlay_if_needed: Callable[[], None],
    capture_window_presentation: Callable[[], dict[str, Any]],
    ensure_home: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
    enumerate_tiles: Callable[[], list[dict[str, Any]]],
    click_tile_center: Callable[[dict[str, Any]], None],
    wait_watch_route: Callable[[float], bool],
    dom_click_tile: Callable[[dict[str, Any]], bool],
    send_return_key: Callable[[], None],
    try_resume_current_video: Callable[[], None],
    wait_confirmed_watch_playback: Callable[[float, bool], dict[str, Any]],
    restore_window_presentation: Callable[[dict[str, Any], str], None],
) -> str:
    hide_overlay_if_needed()
    presentation_before = capture_window_presentation()
    snap = ensure_home()
    log(
        f"{label} precondition home verified: "
        f"hash={snap.get('hash')} tiles={snap.get('tilesCount')}"
    )
    tiles = enumerate_tiles()
    if not tiles:
        raise RuntimeError("no home tiles found")

    if filter_fn is not None:
        filtered = [tile for tile in tiles if filter_fn(tile)]
        log(f"{label} filtered candidates: {len(filtered)}/{len(tiles)}")
        if filtered:
            tiles = filtered
        else:
            raise RuntimeError(f"{label} candidates not found on home screen")

    ranked = sorted(tiles, key=scorer, reverse=True)
    preview: list[str] = []
    for tile in ranked[: min(3, len(ranked))]:
        try:
            score = scorer(tile)
        except Exception:
            score = 0.0
        title = str(tile.get("title") or tile.get("text") or "<no title>")
        badge = " [ライブ]" if tile.get("hasJaLiveBadge") else ""
        preview.append(f"{score:.1f}:{title[:80]}{badge}")
    if preview:
        log(f"{label} tile candidates: " + " | ".join(preview))

    selected_title = "<none>"
    routed = False
    for idx, best in enumerate(ranked[: min(3, len(ranked))], start=1):
        selected_title = str(best.get("title") or best.get("text") or "<no title>")
        log(f"{label} tile selected attempt={idx}: {selected_title}")
        click_tile_center(best)
        if wait_watch_route(2.5):
            routed = True
            break
        click_tile_center(best)
        if wait_watch_route(2.5):
            routed = True
            break
        if dom_click_tile(best) and wait_watch_route(2.5):
            routed = True
            break
        send_return_key()
        if wait_watch_route(2.0):
            routed = True
            break
    if not routed:
        raise RuntimeError(
            "route did not change to watch after tile click "
            "(all fallback attempts failed)"
        )

    try_resume_current_video()
    state = wait_confirmed_watch_playback(8.0, allow_soft_playback_confirm)
    log(
        f"{label} post-click state: "
        + json.dumps(
            {"hash": state.get("hash"), "title": state.get("title"), "video": state.get("video")},
            ensure_ascii=False,
        )
    )
    try:
        restore_window_presentation(presentation_before, label)
    except Exception as err:
        log(f"{label} post-action presentation restore skipped: {err}")
    return f"opened watch route {state.get('hash') or ''}".strip()


def run_vacuumtube_fullscreen(
    *,
    ensure_started_and_positioned: Callable[[], Any],
    wait_window: Callable[[], str],
    activate_window: Callable[[str], None],
    get_window_geometry: Callable[[str], dict[str, Any] | None],
    set_fullscreen: Callable[..., None],
    wait_fullscreen: Callable[..., bool],
) -> str:
    ensure_started_and_positioned()
    win_id = wait_window()
    activate_window(win_id)
    before = get_window_geometry(win_id)
    set_fullscreen(win_id, enabled=True)
    ok = wait_fullscreen(win_id, enabled=True, timeout_sec=3.0)
    after = get_window_geometry(win_id)
    return "youtube fullscreen " + json.dumps(
        {"fullscreen": ok, "before": before, "after": after},
        ensure_ascii=False,
    )


def run_vacuumtube_quadrant(
    *,
    ensure_started_and_positioned: Callable[[], Any],
    ensure_top_right_position: Callable[[], dict[str, Any]],
) -> str:
    ensure_started_and_positioned()
    position = ensure_top_right_position()
    return "youtube quadrant " + json.dumps(position, ensure_ascii=False)


def run_vacuumtube_minimize(
    *,
    find_window_id: Callable[[], str | None],
    build_minimize_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], None],
) -> str:
    win_id = find_window_id()
    if not win_id:
        return "VacuumTube window not found (no-op)"

    run_command(build_minimize_command(win_id))
    return f"youtube minimize: ok (win_id={win_id})"


def run_vacuumtube_stop_music(
    *,
    find_window_id: Callable[[], str | None],
    snapshot_state: Callable[[], dict[str, Any]],
    is_watch_state: Callable[[dict[str, Any]], bool],
    send_space_key: Callable[[], None],
    time_now: Callable[[], float],
    sleep: Callable[[float], None],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
) -> str:
    win_id = find_window_id()
    if not win_id:
        return "VacuumTube window not found (no-op)"

    before = snapshot_state()
    if not is_watch_state(before):
        log("stop_music skipped: not on watch route")
        return "not on watch route (no-op)"

    send_space_key()
    deadline = time_now() + 4.0
    last = before
    while time_now() < deadline:
        try:
            last = snapshot_state()
            if is_watch_state(last):
                video = last.get("video")
                if isinstance(video, dict) and bool(video.get("paused", False)):
                    try:
                        position = ensure_top_right_position()
                        payload = json.dumps(position, ensure_ascii=False)
                        log(f"STOP post-action window position: {payload}")
                    except Exception as err:
                        log(f"STOP post-action position check skipped: {err}")
                    return f"sent Space toggle to VacuumTube ({win_id}); pause confirmed"
        except Exception:
            pass
        sleep(0.25)

    payload = json.dumps(last, ensure_ascii=False)
    return f"sent Space toggle to VacuumTube ({win_id}); pause not confirmed ({payload})"


def run_vacuumtube_play_news(
    *,
    slot: str,
    get_state: Callable[[], dict[str, Any]],
    send_return_key: Callable[[], None],
    sleep: Callable[[float], None],
    open_from_home: Callable[[str], str],
) -> str:
    state = get_state()
    if state.get("accountSelectHint"):
        send_return_key()
        sleep(0.6)
    label = "NEWS" if slot == "generic" else f"NEWS-{slot.upper()}"
    return open_from_home(label)
