from __future__ import annotations

import json
import socket
import time
from collections.abc import Callable
from contextlib import nullcontext
from typing import Any

from .vacuumtube_state import vacuumtube_is_watch_state
from .window_query_runtime import build_xprop_wm_state_command


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


def run_vacuumtube_state_query(
    *,
    evaluate: Callable[[str], Any],
) -> dict[str, Any]:
    expr = r"""
(() => {
  const txt = ((document.body && document.body.innerText) || '').replace(/\s+/g, ' ').trim();
  const bodyText = txt.slice(0, 4000);
  const ov = document.getElementById('vt-settings-overlay-root');
  const ovVisible = !!(
    ov &&
    getComputedStyle(ov).display !== 'none' &&
    getComputedStyle(ov).visibility !== 'hidden'
  );
  const v =
    (window.yt &&
      window.yt.player &&
      window.yt.player.utils &&
      window.yt.player.utils.videoElement_) ||
    document.querySelector('video');
  return {
    title: document.title || '',
    href: location.href,
    hash: location.hash || '',
    bodyText,
    accountSelectHint:
      bodyText.includes('アカウントを追加') ||
      bodyText.includes('ゲストとして視聴'),
    homeHint: bodyText.includes('あなたへのおすすめ'),
    watchUiHint:
      bodyText.includes('次の動画') ||
      bodyText.includes('チャンネル登録') ||
      bodyText.includes('高く評価') ||
      bodyText.includes('低く評価') ||
      bodyText.includes('一時停止') ||
      bodyText.includes('再生中'),
    overlayVisible: ovVisible,
    video: v
      ? {
          paused: !!v.paused,
          muted: !!v.muted,
          currentTime: Number(v.currentTime || 0),
          readyState: Number(v.readyState || 0),
        }
      : null,
  };
})()
"""
    data = evaluate(expr)
    return data if isinstance(data, dict) else {}


def run_vacuumtube_state_host_runtime_query(*, cdp: Any) -> dict[str, Any]:
    return run_vacuumtube_state_query(evaluate=lambda expr: cdp.evaluate(expr))


def run_vacuumtube_hide_overlay(
    *,
    evaluate: Callable[[str], Any],
) -> None:
    expr = r"""
(() => {
  const el = document.getElementById('vt-settings-overlay-root');
  if (!el) return false;
  el.style.setProperty('display', 'none', 'important');
  el.style.setProperty('visibility', 'hidden', 'important');
  return true;
})()
"""
    evaluate(expr)


def run_vacuumtube_snapshot_state(
    *,
    query_state: Callable[[], dict[str, Any]],
    enumerate_tiles: Callable[[], list[dict[str, Any]]],
) -> dict[str, Any]:
    state = query_state()
    if not isinstance(state, dict):
        state = {}

    try:
        tiles = enumerate_tiles()
    except Exception:
        tiles = []

    sample_titles: list[str] = []
    for tile in tiles[:3]:
        sample_titles.append(str(tile.get("title") or tile.get("text") or "")[:100])

    return {
        "hash": state.get("hash"),
        "title": state.get("title"),
        "accountSelectHint": state.get("accountSelectHint"),
        "homeHint": state.get("homeHint"),
        "watchUiHint": state.get("watchUiHint"),
        "overlayVisible": state.get("overlayVisible"),
        "video": state.get("video"),
        "tilesCount": len(tiles),
        "tilesSample": sample_titles,
    }


def run_vacuumtube_snapshot_state_host_runtime(
    *,
    runtime: Any,
    cdp: Any,
) -> dict[str, Any]:
    return run_vacuumtube_snapshot_state(
        query_state=lambda: run_vacuumtube_state_host_runtime_query(cdp=cdp),
        enumerate_tiles=lambda: runtime._enumerate_tiles(cdp),
    )


def run_vacuumtube_context_query(
    *,
    ts: float,
    cdp_port: int | None,
    find_window_row_by_cdp_port: Callable[[int], dict[str, Any] | None],
    find_window_id: Callable[[], str],
    get_window_geometry: Callable[[str], dict[str, Any] | None],
    current_window_is_fullscreenish: Callable[[str], bool],
    read_fullscreen_state: Callable[[str], str],
    quadrant_mode_enabled: Callable[[], bool],
    cdp_ready: Callable[[], bool],
    query_cdp_state: Callable[[], dict[str, Any] | None],
) -> dict[str, Any]:
    context = build_vacuumtube_context_base(ts=ts)

    try:
        geom: dict[str, Any] | None
        row = find_window_row_by_cdp_port(int(cdp_port)) if cdp_port else None
        if row:
            window_id = str(row.get("id") or "")
            geom = {
                "x": row.get("x"),
                "y": row.get("y"),
                "w": row.get("w"),
                "h": row.get("h"),
            }
        else:
            window_id = str(find_window_id() or "")
            geom = get_window_geometry(window_id) if window_id else None

        fullscreenish = False
        if window_id:
            try:
                fullscreenish = bool(current_window_is_fullscreenish(window_id))
            except Exception:
                pass
            try:
                if "_NET_WM_STATE_FULLSCREEN" in str(read_fullscreen_state(window_id) or ""):
                    fullscreenish = True
            except Exception:
                pass

        try:
            quadrantish = bool(quadrant_mode_enabled())
        except Exception:
            quadrantish = False

        context = merge_vacuumtube_window_snapshot(
            context,
            window_id=window_id,
            geom=geom,
            fullscreenish=fullscreenish,
            quadrantish=quadrantish,
        )
    except Exception:
        pass

    try:
        if cdp_ready():
            context = merge_vacuumtube_cdp_state(context, query_cdp_state())
        context = finalize_vacuumtube_context(context)
    except Exception:
        pass

    return context


def run_vacuumtube_context_runtime_query(
    *,
    ts: float,
    cdp_port: int | None,
    find_window_row_by_cdp_port: Callable[[int], dict[str, Any] | None],
    find_window_id: Callable[[], str],
    get_window_geometry: Callable[[str], dict[str, Any] | None],
    current_window_is_fullscreenish: Callable[[str], bool],
    run_xprop_query: Callable[[list[str]], str],
    quadrant_mode_enabled: Callable[[], bool],
    cdp_ready: Callable[[], bool],
    open_cdp: Callable[[], Any] | None,
    read_state: Callable[[Any], dict[str, Any] | None] | None,
) -> dict[str, Any]:
    return run_vacuumtube_context_query(
        ts=ts,
        cdp_port=cdp_port,
        find_window_row_by_cdp_port=find_window_row_by_cdp_port,
        find_window_id=find_window_id,
        get_window_geometry=get_window_geometry,
        current_window_is_fullscreenish=current_window_is_fullscreenish,
        read_fullscreen_state=lambda win_id: run_xprop_query(
            build_xprop_wm_state_command(win_id)
        ),
        quadrant_mode_enabled=quadrant_mode_enabled,
        cdp_ready=cdp_ready,
        query_cdp_state=lambda: _run_vacuumtube_cdp_state_query(
            open_cdp=open_cdp,
            read_state=read_state,
        ),
    )


def run_vacuumtube_context_runtime_flow(
    *,
    ts: float,
    runtime: Any,
    find_window_row_by_cdp_port: Callable[[int], dict[str, Any] | None],
    quadrant_mode_enabled: Callable[[], bool],
    run_command: Callable[..., Any],
) -> dict[str, Any]:
    env_getter = getattr(runtime, "_x11_env", None)
    return run_vacuumtube_context_runtime_query(
        ts=ts,
        cdp_port=getattr(runtime, "cdp_port", None),
        find_window_row_by_cdp_port=find_window_row_by_cdp_port,
        find_window_id=lambda: (
            runtime.find_window_id()
            if callable(getattr(runtime, "find_window_id", None))
            else ""
        ),
        get_window_geometry=lambda win_id: (
            runtime.get_window_geometry(win_id)
            if win_id and callable(getattr(runtime, "get_window_geometry", None))
            else None
        ),
        current_window_is_fullscreenish=lambda win_id: (
            bool(runtime._current_window_is_fullscreenish(win_id))
            if callable(getattr(runtime, "_current_window_is_fullscreenish", None))
            else False
        ),
        run_xprop_query=lambda command: str(
            run_command(
                command,
                check=False,
                env=env_getter() if callable(env_getter) else None,
            ).stdout
            or ""
        ),
        quadrant_mode_enabled=quadrant_mode_enabled,
        cdp_ready=lambda: bool(
            callable(getattr(runtime, "cdp_ready", None)) and runtime.cdp_ready()
        ),
        open_cdp=getattr(runtime, "_cdp", None),
        read_state=getattr(runtime, "_state", None),
    )


def _run_vacuumtube_cdp_state_query(
    *,
    open_cdp: Callable[[], Any] | None,
    read_state: Callable[[Any], dict[str, Any] | None] | None,
) -> dict[str, Any] | None:
    if not callable(open_cdp) or not callable(read_state):
        return None
    with open_cdp() as cdp:
        return read_state(cdp)


def run_vacuumtube_action_with_recovery(
    *,
    action: Callable[[], Any],
    label: str,
    is_recoverable_error: Callable[[Exception], bool],
    recover: Callable[[], Any] | None,
    log: Callable[[str], None],
) -> str:
    try:
        return str(action())
    except Exception as err:
        if not is_recoverable_error(err):
            raise
        if not callable(recover):
            raise
        log(f"{label} recoverable VacuumTube error: {err}; restarting and retrying once")
        recover()
        return str(action())


def run_vacuumtube_ensure_home(
    *,
    snapshot_state: Callable[[], dict[str, Any]],
    is_home_browse_state: Callable[[dict[str, Any]], bool],
    route_to_home: Callable[[], None],
    hard_reload_home: Callable[[], None],
    select_account_if_needed: Callable[[], None],
    needs_hard_reload_home: Callable[[dict[str, Any]], bool],
    log: Callable[[str], None],
    now: Callable[[], float],
    sleep: Callable[[float], None],
    timeout_sec: float = 8.0,
) -> dict[str, Any]:
    snapshot = snapshot_state()
    log(f"state before ensure_home: {json.dumps(snapshot, ensure_ascii=False)}")
    if is_home_browse_state(snapshot):
        return snapshot

    route_to_home()
    deadline = now() + timeout_sec
    last_snapshot = snapshot
    did_hard_reload = False
    last_account_select_attempt = 0.0
    while now() < deadline:
        try:
            last_snapshot = snapshot_state()
            if is_home_browse_state(last_snapshot):
                log(f"state after ensure_home: {json.dumps(last_snapshot, ensure_ascii=False)}")
                return last_snapshot
            if bool(last_snapshot.get("accountSelectHint")):
                current = now()
                if (current - last_account_select_attempt) >= 0.8:
                    log("ensure_home detected account selection; trying default account focus")
                    select_account_if_needed()
                    last_account_select_attempt = current
                    continue
            if (
                not did_hard_reload
                and needs_hard_reload_home(last_snapshot)
                and (deadline - now()) > 2.0
            ):
                log(
                    "ensure_home detected stale '#/' state; forcing hard reload to home: "
                    + json.dumps(
                        {
                            "tiles": last_snapshot.get("tilesCount"),
                            "watchUiHint": last_snapshot.get("watchUiHint"),
                            "homeHint": last_snapshot.get("homeHint"),
                        },
                        ensure_ascii=False,
                    )
                )
                hard_reload_home()
                did_hard_reload = True
        except Exception:
            pass
        sleep(0.25)
    raise RuntimeError(
        "failed to reach verified home browse state: "
        + json.dumps(last_snapshot, ensure_ascii=False)
    )


def run_vacuumtube_ensure_home_host_runtime(
    *,
    runtime: Any,
    cdp: Any,
    timeout_sec: float = 8.0,
) -> dict[str, Any]:
    log = runtime.log if callable(getattr(runtime, "log", None)) else (lambda _message: None)
    return run_vacuumtube_ensure_home(
        snapshot_state=lambda: runtime._snapshot_state(cdp),
        is_home_browse_state=runtime._is_home_browse_state,
        route_to_home=lambda: runtime._route_to_home(cdp),
        hard_reload_home=lambda: runtime._hard_reload_home(cdp),
        select_account_if_needed=runtime._select_account_if_needed,
        needs_hard_reload_home=runtime._needs_hard_reload_home,
        log=log,
        now=time.time,
        sleep=time.sleep,
        timeout_sec=timeout_sec,
    )


def run_vacuumtube_try_resume_current_video(
    *,
    evaluate_async: Callable[[str], Any],
) -> bool:
    expr = r"""
(async () => {
  const v =
    (window.yt &&
      window.yt.player &&
      window.yt.player.utils &&
      window.yt.player.utils.videoElement_) ||
    document.querySelector('video');
  if (!v) return {ok:false, reason:'no-video'};
  v.muted = false;
  try { await v.play(); } catch (e) {}
  return {ok:true, paused: !!v.paused, muted: !!v.muted, currentTime: Number(v.currentTime || 0)};
})()
"""
    try:
        out = evaluate_async(expr)
        return bool(isinstance(out, dict) and out.get("ok"))
    except Exception:
        return False


def run_vacuumtube_wait_watch_route(
    *,
    get_state: Callable[[], dict[str, Any]],
    now: Callable[[], float],
    sleep: Callable[[float], None],
    timeout_sec: float = 8.0,
) -> bool:
    deadline = now() + timeout_sec
    while now() < deadline:
        try:
            state = get_state()
        except Exception:
            sleep(0.2)
            continue
        if str(state.get("hash") or "").startswith("#/watch"):
            return True
        sleep(0.2)
    return False


def run_vacuumtube_wait_watch_route_host_runtime(
    *,
    runtime: Any,
    cdp: Any,
    timeout_sec: float = 8.0,
) -> bool:
    return run_vacuumtube_wait_watch_route(
        get_state=lambda: runtime._state(cdp),
        now=time.time,
        sleep=time.sleep,
        timeout_sec=timeout_sec,
    )


def run_vacuumtube_route_to_home(
    *,
    evaluate: Callable[[str], Any],
) -> None:
    evaluate("location.hash = '#/'")


def run_vacuumtube_hard_reload_home(
    *,
    evaluate: Callable[[str], Any],
) -> None:
    evaluate("location.href = 'https://www.youtube.com/tv#/'")


def run_vacuumtube_click_tile_center(
    *,
    tile: dict[str, Any],
    mouse_click: Callable[[float, float], None],
) -> None:
    x = float(tile.get("cx") or 0)
    y = float(tile.get("cy") or 0)
    mouse_click(x, y)


def run_vacuumtube_enumerate_tiles(
    *,
    evaluate: Callable[[str], Any],
) -> list[dict[str, Any]]:
    expr = r"""
(() => {
  const out = [];
  const seenRoots = new Set();
  const seenEls = new Set();
  function walkRoot(root) {
    if (!root || seenRoots.has(root)) return;
    seenRoots.add(root);
    if (!root.querySelectorAll) return;
    for (const el of root.querySelectorAll('ytlr-tile-renderer')) {
      if (seenEls.has(el)) continue;
      seenEls.add(el);
      const r = el.getBoundingClientRect();
      const st = getComputedStyle(el);
      const visible =
        r.width > 20 &&
        r.height > 20 &&
        st.display !== 'none' &&
        st.visibility !== 'hidden';
      const txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      let title = '';
      let hasJaLiveBadge = false;
      let hasJaLiveBadgeBottomRight = false;
      for (const c of el.querySelectorAll('*')) {
        const t = (c.innerText || c.textContent || '').replace(/\s+/g, ' ').trim();
        if (t === 'ライブ') {
          hasJaLiveBadge = true;
          const cr = c.getBoundingClientRect();
          if (
            cr.width > 0 && cr.height > 0 &&
            cr.right >= r.right - Math.max(80, r.width * 0.45) &&
            cr.bottom >= r.bottom - Math.max(80, r.height * 0.45)
          ) {
            hasJaLiveBadgeBottomRight = true;
          }
        }
        if (t.length > title.length) title = t;
      }
      out.push({
        visible,
        title,
        text: txt,
        hasJaLiveBadge,
        hasJaLiveBadgeBottomRight,
        x: r.x,
        y: r.y,
        width: r.width,
        height: r.height,
        cx: r.x + r.width / 2,
        cy: r.y + r.height / 2,
      });
    }
    for (const node of root.querySelectorAll('*')) {
      if (node.shadowRoot) walkRoot(node.shadowRoot);
    }
  }
  walkRoot(document);
  return out;
})()
"""
    data = evaluate(expr)
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def run_vacuumtube_dom_click_tile(
    *,
    title: str,
    text: str,
    evaluate: Callable[[str], Any],
) -> Any:
    expr = f"""
(() => {{
  const wantTitle = {json.dumps(title)};
  const wantText = {json.dumps(text)};
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const wantTitleN = norm(wantTitle);
  const wantTextN = norm(wantText);
  const rootsSeen = new Set();
  const elemsSeen = new Set();
  const tiles = [];
  function walk(root) {{
    if (!root || rootsSeen.has(root)) return;
    rootsSeen.add(root);
    if (!root.querySelectorAll) return;
    for (const el of root.querySelectorAll('ytlr-tile-renderer')) {{
      if (elemsSeen.has(el)) continue;
      elemsSeen.add(el);
      let longest = '';
      for (const c of el.querySelectorAll('*')) {{
        const t = norm(c.innerText || c.textContent || '');
        if (t.length > longest.length) longest = t;
      }}
      tiles.push({{
        el,
        title: longest,
        text: norm(el.innerText || el.textContent || ''),
      }});
    }}
    for (const node of root.querySelectorAll('*')) {{
      if (node.shadowRoot) walk(node.shadowRoot);
    }}
  }}
  walk(document);
  let best = null;
  let bestScore = -1;
  for (const t of tiles) {{
    let score = 0;
    if (wantTitleN && t.title === wantTitleN) score += 100;
    if (wantTitleN && t.text.includes(wantTitleN)) score += 40;
    if (wantTextN && t.text === wantTextN) score += 80;
    if (
      wantTextN &&
      t.text &&
      (wantTextN.includes(t.text) || t.text.includes(wantTextN))
    ) score += 20;
    if (score > bestScore) {{
      best = t;
      bestScore = score;
    }}
  }}
  if (!best || bestScore <= 0) return {{ok:false, reason:'no-match', bestScore}};
  try {{
    best.el.scrollIntoView({{block:'center', inline:'center'}});
  }} catch (e) {{}}
  const target = best.el.querySelector('a, button, [role="button"]') || best.el;
  try {{
    for (const type of ['pointerdown', 'mousedown', 'mouseup', 'pointerup', 'click']) {{
      const ev = new MouseEvent(type, {{
        bubbles:true,
        cancelable:true,
        composed:true,
        view:window
      }});
      target.dispatchEvent(ev);
    }}
  }} catch (e) {{
    try {{ target.click(); }} catch (_e) {{}}
  }}
  return {{ok:true, bestScore, title: best.title.slice(0, 200), text: best.text.slice(0, 200)}};
}})()
"""
    return evaluate(expr)


def run_vacuumtube_good_night_pause(
    *,
    evaluate: Callable[[str], Any],
) -> dict[str, Any]:
    expr = r"""
(() => {
  try {
    const v =
      (window.yt &&
        window.yt.player &&
        window.yt.player.utils &&
        window.yt.player.utils.videoElement_) ||
      document.querySelector('video');
    if (!v) {
      return {ok: false, reason: 'video-not-found', hash: location.hash || ''};
    }
    const beforePaused = !!v.paused;
    v.pause();
    return {
      ok: true,
      beforePaused,
      afterPaused: !!v.paused,
      currentTime: Number(v.currentTime || 0),
      hash: location.hash || ''
    };
  } catch (e) {
    return {ok: false, reason: String(e), hash: location.hash || ''};
  }
})()
"""
    out = evaluate(expr)
    return out if isinstance(out, dict) else {"ok": False, "result": out}


def run_vacuumtube_good_night_pause_runtime(
    *,
    open_cdp: Callable[[], Any],
    snapshot_state: Callable[[Any], dict[str, Any]],
    run_pause: Callable[[Any], dict[str, Any]],
) -> str:
    with open_cdp() as cdp:
        snap = snapshot_state(cdp)
        payload = run_pause(cdp)
        payload.setdefault("stateHash", snap.get("hash"))
        return "good_night pause " + json.dumps(payload, ensure_ascii=False)


def run_vacuumtube_good_night_pause_flow(
    *,
    find_window_id: Callable[[], str | None],
    pause_runtime: Callable[[], str],
) -> str:
    win_id = find_window_id()
    if not win_id:
        return "good_night pause no VacuumTube window (no-op)"
    try:
        return str(pause_runtime())
    except Exception as err:
        return f"good_night pause error: {err}"


def run_vacuumtube_good_night_pause_runtime_flow(
    *,
    find_window_id: Callable[[], str | None],
    open_cdp: Callable[[], Any],
    snapshot_state: Callable[[Any], dict[str, Any]],
    run_pause: Callable[[Any], dict[str, Any]],
) -> str:
    return run_vacuumtube_good_night_pause_flow(
        find_window_id=find_window_id,
        pause_runtime=lambda: run_vacuumtube_good_night_pause_runtime(
            open_cdp=open_cdp,
            snapshot_state=snapshot_state,
            run_pause=run_pause,
        ),
    )


def run_vacuumtube_good_night_pause_cdp_runtime_flow(
    *,
    find_window_id: Callable[[], str | None],
    open_cdp: Callable[[], Any],
    snapshot_state: Callable[[Any], dict[str, Any]],
    cdp_getter: Callable[[Any], Any],
) -> str:
    return run_vacuumtube_good_night_pause_runtime_flow(
        find_window_id=find_window_id,
        open_cdp=open_cdp,
        snapshot_state=snapshot_state,
        run_pause=lambda cdp: run_vacuumtube_good_night_pause(
            evaluate=lambda expr: cdp_getter(cdp).evaluate(expr),
        ),
    )


def run_vacuumtube_good_night_pause_host_runtime(
    *,
    runtime: Any,
    cdp_getter: Callable[[Any], Any],
) -> str:
    return run_vacuumtube_good_night_pause_cdp_runtime_flow(
        find_window_id=runtime.find_window_id,
        open_cdp=runtime._cdp,
        snapshot_state=runtime._snapshot_state,
        cdp_getter=cdp_getter,
    )


def run_vacuumtube_select_account_if_needed(
    *,
    snapshot_state: Callable[[], dict[str, Any]],
    send_return_key: Callable[[], None],
    log: Callable[[str], None],
    now: Callable[[], float],
    sleep: Callable[[float], None],
    timeout_sec: float = 8.0,
    poll_interval_sec: float = 0.4,
) -> bool:
    try:
        state = snapshot_state()
        if not state.get("accountSelectHint"):
            return False
        log("VacuumTube account selection detected; sending Enter for default focus")
    except Exception as e:
        log(f"account selection check failed (continuing): {e}")
        return False

    send_return_key()
    deadline = now() + timeout_sec
    while now() < deadline:
        try:
            state = snapshot_state()
            if not state.get("accountSelectHint"):
                return True
        except Exception:
            pass
        sleep(poll_interval_sec)
    return False


def run_vacuumtube_confirm_watch_playback(
    *,
    snapshot_state: Callable[[], dict[str, Any]],
    is_watch_state: Callable[[dict[str, Any]], bool],
    playback_confirmed: Callable[[dict[str, Any], dict[str, Any]], bool],
    try_resume_current_video: Callable[[], None],
    log: Callable[[str], None],
    now: Callable[[], float],
    sleep: Callable[[float], None],
    timeout_sec: float = 8.0,
    allow_resume_attempts: bool = True,
    allow_soft_confirm_when_unpaused: bool = False,
    resume_interval_sec: float = 1.0,
    poll_interval_sec: float = 0.35,
) -> dict[str, Any]:
    deadline = now() + timeout_sec
    first_watch_snapshot: dict[str, Any] | None = None
    last_snapshot: dict[str, Any] | None = None
    last_resume_try = 0.0
    while now() < deadline:
        snap = snapshot_state()
        last_snapshot = snap
        if is_watch_state(snap):
            if first_watch_snapshot is None:
                first_watch_snapshot = snap
            if playback_confirmed(first_watch_snapshot, snap):
                log(
                    "watch playback confirmed: "
                    + json.dumps(
                        {"hash": snap.get("hash"), "video": snap.get("video")},
                        ensure_ascii=False,
                    )
                )
                return snap
            if allow_soft_confirm_when_unpaused:
                video = snap.get("video")
                if isinstance(video, dict) and not bool(video.get("paused", True)):
                    log(
                        "watch playback soft-confirmed: "
                        + json.dumps(
                            {"hash": snap.get("hash"), "video": video},
                            ensure_ascii=False,
                        )
                    )
                    return snap
            if allow_resume_attempts and (now() - last_resume_try) >= resume_interval_sec:
                try_resume_current_video()
                last_resume_try = now()
        sleep(poll_interval_sec)
    raise RuntimeError(
        "watch route reached but playback not confirmed: "
        + json.dumps(last_snapshot or {}, ensure_ascii=False)
    )


def run_vacuumtube_confirm_watch_playback_host_runtime(
    *,
    runtime: Any,
    cdp: Any,
    playback_confirmed: Callable[[dict[str, Any], dict[str, Any]], bool],
    timeout_sec: float = 8.0,
    allow_resume_attempts: bool = True,
    allow_soft_confirm_when_unpaused: bool = False,
) -> dict[str, Any]:
    log = runtime.log if callable(getattr(runtime, "log", None)) else (lambda _message: None)
    return run_vacuumtube_confirm_watch_playback(
        snapshot_state=lambda: runtime._snapshot_state(cdp),
        is_watch_state=runtime._is_watch_state,
        playback_confirmed=playback_confirmed,
        try_resume_current_video=lambda: runtime._try_resume_current_video(cdp),
        log=log,
        now=time.time,
        sleep=time.sleep,
        timeout_sec=timeout_sec,
        allow_resume_attempts=allow_resume_attempts,
        allow_soft_confirm_when_unpaused=allow_soft_confirm_when_unpaused,
    )


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


def ensure_vacuumtube_runtime_ready(
    *,
    cdp_ready: Callable[[], bool],
    tmux_has: Callable[[], bool],
    wait_cdp_ready: Callable[[float], bool],
    restart_tmux_session: Callable[[], None],
    start_in_tmux: Callable[[], None],
    log: Callable[[str], None],
    tmux_session: str,
    base_url: str,
) -> None:
    if cdp_ready():
        return
    if tmux_has():
        if wait_cdp_ready(2.5):
            return
        log(f"VacuumTube tmux session stale or crashed; restarting: {tmux_session}")
        restart_tmux_session()
    else:
        start_in_tmux()
    if not wait_cdp_ready(35.0):
        raise RuntimeError(f"VacuumTube CDP not ready at {base_url}")


def recover_vacuumtube_unresponsive_state(
    *,
    restart_tmux_session: Callable[[], None],
    wait_cdp_ready: Callable[[float], bool],
    ensure_started_and_positioned: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
    tmux_session: str,
    base_url: str,
) -> dict[str, Any]:
    log(f"VacuumTube recovery requested; restarting tmux session: {tmux_session}")
    restart_tmux_session()
    if not wait_cdp_ready(35.0):
        raise RuntimeError(f"VacuumTube CDP not ready at {base_url}")
    return ensure_started_and_positioned()


def start_vacuumtube_tmux_session(
    *,
    start_script: str,
    tmux_session: str,
    path_exists: Callable[[str], bool],
    tmux_has: Callable[[], bool],
    resolve_display: Callable[[], str],
    build_start_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], None],
    log: Callable[[str], None],
) -> None:
    if not path_exists(start_script):
        raise RuntimeError(f"VacuumTube start script not found: {start_script}")
    if tmux_has():
        log(f"VacuumTube tmux session already exists: {tmux_session}")
        return

    display = resolve_display()
    run_command(build_start_command(display))
    log(f"VacuumTube tmux start requested: {tmux_session}")


def restart_vacuumtube_tmux_session(
    *,
    tmux_has: Callable[[], bool],
    build_kill_command: Callable[[], list[str]],
    run_command: Callable[[list[str]], None],
    sleep: Callable[[float], None],
    start_tmux_session: Callable[[], None],
) -> None:
    if tmux_has():
        run_command(build_kill_command())
        sleep(0.25)
    start_tmux_session()


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


def run_vacuumtube_resume_playback_runtime(
    *,
    open_cdp: Callable[[], Any],
    find_window_id: Callable[[], str | None],
    snapshot_state: Callable[[Any], dict[str, Any]],
    is_watch_state: Callable[[dict[str, Any]], bool],
    confirm_watch_playback: Callable[..., Any],
    try_resume_current_video: Callable[[Any], None],
    send_space_key: Callable[[], None],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
) -> str:
    with open_cdp() as cdp:
        return run_vacuumtube_resume_playback(
            find_window_id=find_window_id,
            snapshot_state=lambda: snapshot_state(cdp),
            is_watch_state=is_watch_state,
            confirm_already_playing=lambda: confirm_watch_playback(
                cdp,
                timeout_sec=1.2,
                allow_resume_attempts=False,
            ),
            try_resume_current_video=lambda: try_resume_current_video(cdp),
            confirm_dom_resume=lambda: confirm_watch_playback(
                cdp,
                timeout_sec=4.5,
            ),
            send_space_key=send_space_key,
            confirm_space_resume=lambda: confirm_watch_playback(
                cdp,
                timeout_sec=5.0,
            ),
            ensure_top_right_position=ensure_top_right_position,
            log=log,
        )


def run_vacuumtube_resume_playback_host_runtime(*, runtime: Any) -> str:
    log = runtime.log if hasattr(runtime, "log") else None
    return run_vacuumtube_resume_playback_runtime(
        open_cdp=runtime._cdp,
        find_window_id=runtime.find_window_id,
        snapshot_state=runtime._snapshot_state,
        is_watch_state=runtime._is_watch_state,
        confirm_watch_playback=runtime._wait_confirmed_watch_playback,
        try_resume_current_video=runtime._try_resume_current_video,
        send_space_key=lambda: runtime.send_key("space"),
        ensure_top_right_position=runtime.ensure_top_right_position,
        log=log if callable(log) else (lambda _message: None),
    )


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


def run_vacuumtube_go_home_runtime(
    *,
    open_cdp: Callable[[], Any],
    presentation_before: dict[str, Any],
    hide_overlay_if_needed: Callable[[Any], None],
    ensure_home: Callable[[Any], dict[str, Any]],
    restore_window_presentation: Callable[..., None],
    log: Callable[[str], None],
) -> str:
    with open_cdp() as cdp:
        return run_vacuumtube_go_home(
            presentation_before=presentation_before,
            hide_overlay_if_needed=lambda: hide_overlay_if_needed(cdp),
            ensure_home=lambda: ensure_home(cdp),
            restore_window_presentation=restore_window_presentation,
            log=log,
        )


def run_vacuumtube_go_home_host_runtime(
    *,
    runtime: Any,
    presentation_before: dict[str, Any],
) -> str:
    log = runtime.log if hasattr(runtime, "log") else None
    return run_vacuumtube_go_home_runtime(
        open_cdp=runtime._cdp,
        presentation_before=presentation_before,
        hide_overlay_if_needed=runtime._hide_overlay_if_needed,
        ensure_home=runtime._ensure_home,
        restore_window_presentation=runtime._restore_window_presentation,
        log=log if callable(log) else (lambda _message: None),
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


def run_vacuumtube_play_bgm_runtime(
    *,
    open_cdp: Callable[[], Any],
    get_state: Callable[[Any], dict[str, Any]],
    send_return_key: Callable[[], None],
    send_space_key: Callable[[], None],
    sleep: Callable[[float], None],
    try_resume_current_video: Callable[[Any], None],
    confirm_watch_playback: Callable[..., Any],
    open_from_home: Callable[[Any], str],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
) -> str:
    with open_cdp() as cdp:
        return run_vacuumtube_play_bgm(
            get_state=lambda: get_state(cdp),
            send_return_key=send_return_key,
            send_space_key=send_space_key,
            sleep=sleep,
            try_resume_current_video=lambda: try_resume_current_video(cdp),
            confirm_watch_playback=lambda **kwargs: confirm_watch_playback(cdp, **kwargs),
            open_from_home=lambda: open_from_home(cdp),
            ensure_top_right_position=ensure_top_right_position,
            log=log,
        )


def run_vacuumtube_play_bgm_host_runtime(
    *,
    runtime: Any,
    sleep: Callable[[float], None],
) -> str:
    log = runtime.log if hasattr(runtime, "log") else None
    return run_vacuumtube_play_bgm_runtime(
        open_cdp=runtime._cdp,
        get_state=runtime._state,
        send_return_key=lambda: runtime.send_key("Return"),
        send_space_key=lambda: runtime.send_key("space"),
        sleep=sleep,
        try_resume_current_video=runtime._try_resume_current_video,
        confirm_watch_playback=runtime._wait_confirmed_watch_playback,
        open_from_home=lambda cdp: run_vacuumtube_open_from_home_host_runtime(
            cdp=cdp,
            runtime=runtime,
            label="BGM",
            scorer=runtime._score_bgm_tile,
            filter_fn=None,
            allow_soft_playback_confirm=True,
        ),
        ensure_top_right_position=runtime.ensure_top_right_position,
        log=log if callable(log) else (lambda _message: None),
    )


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


def run_vacuumtube_open_from_home_runtime(
    *,
    open_cdp: Callable[[], Any],
    label: str,
    scorer: Callable[[dict[str, Any]], float],
    filter_fn: Callable[[dict[str, Any]], bool] | None,
    allow_soft_playback_confirm: bool,
    hide_overlay_if_needed: Callable[[Any], None],
    capture_window_presentation: Callable[[], dict[str, Any]],
    ensure_home: Callable[[Any], dict[str, Any]],
    log: Callable[[str], None],
    enumerate_tiles: Callable[[Any], list[dict[str, Any]]],
    click_tile_center: Callable[[Any, dict[str, Any]], None],
    wait_watch_route: Callable[[Any, float], bool],
    dom_click_tile: Callable[[Any, dict[str, Any]], bool],
    send_return_key: Callable[[], None],
    try_resume_current_video: Callable[[Any], None],
    wait_confirmed_watch_playback: Callable[[Any, float, bool], dict[str, Any]],
    restore_window_presentation: Callable[[dict[str, Any], str], None],
) -> str:
    with open_cdp() as cdp:
        return run_vacuumtube_open_from_home(
            label=label,
            scorer=scorer,
            filter_fn=filter_fn,
            allow_soft_playback_confirm=allow_soft_playback_confirm,
            hide_overlay_if_needed=lambda: hide_overlay_if_needed(cdp),
            capture_window_presentation=capture_window_presentation,
            ensure_home=lambda: ensure_home(cdp),
            log=log,
            enumerate_tiles=lambda: enumerate_tiles(cdp),
            click_tile_center=lambda tile: click_tile_center(cdp, tile),
            wait_watch_route=lambda timeout: wait_watch_route(cdp, timeout),
            dom_click_tile=lambda tile: dom_click_tile(cdp, tile),
            send_return_key=send_return_key,
            try_resume_current_video=lambda: try_resume_current_video(cdp),
            wait_confirmed_watch_playback=lambda timeout, allow_soft: wait_confirmed_watch_playback(
                cdp,
                timeout,
                allow_soft,
            ),
            restore_window_presentation=restore_window_presentation,
        )


def run_vacuumtube_open_from_home_host_runtime(
    *,
    cdp: Any,
    runtime: Any,
    label: str,
    scorer: Callable[[dict[str, Any]], float],
    filter_fn: Callable[[dict[str, Any]], bool] | None,
    allow_soft_playback_confirm: bool,
) -> str:
    log = runtime.log if hasattr(runtime, "log") else None
    return run_vacuumtube_open_from_home_runtime(
        open_cdp=lambda: nullcontext(cdp),
        label=label,
        scorer=scorer,
        filter_fn=filter_fn,
        allow_soft_playback_confirm=allow_soft_playback_confirm,
        hide_overlay_if_needed=runtime._hide_overlay_if_needed,
        capture_window_presentation=runtime._capture_window_presentation,
        ensure_home=runtime._ensure_home,
        log=log if callable(log) else (lambda _message: None),
        enumerate_tiles=runtime._enumerate_tiles,
        click_tile_center=runtime._click_tile_center,
        wait_watch_route=runtime._wait_watch_route,
        dom_click_tile=runtime._dom_click_tile,
        send_return_key=lambda: runtime.send_key("Return"),
        try_resume_current_video=runtime._try_resume_current_video,
        wait_confirmed_watch_playback=lambda current_cdp, timeout, allow_soft: (
            runtime._wait_confirmed_watch_playback(
                current_cdp,
                timeout_sec=timeout,
                allow_soft_confirm_when_unpaused=allow_soft,
            )
        ),
        restore_window_presentation=lambda presentation, restore_label: (
            runtime._restore_window_presentation(
                presentation,
                label=restore_label,
            )
        ),
    )


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


def run_vacuumtube_fullscreen_host_runtime(*, runtime: Any) -> str:
    return run_vacuumtube_fullscreen(
        ensure_started_and_positioned=runtime.ensure_started_and_positioned,
        wait_window=runtime.wait_window,
        activate_window=runtime.activate_window,
        get_window_geometry=runtime.get_window_geometry,
        set_fullscreen=runtime._set_fullscreen,
        wait_fullscreen=runtime._wait_fullscreen,
    )


def run_vacuumtube_quadrant(
    *,
    ensure_started_and_positioned: Callable[[], Any],
    ensure_top_right_position: Callable[[], dict[str, Any]],
) -> str:
    ensure_started_and_positioned()
    position = ensure_top_right_position()
    return "youtube quadrant " + json.dumps(position, ensure_ascii=False)


def run_vacuumtube_quadrant_host_runtime(*, runtime: Any) -> str:
    return run_vacuumtube_quadrant(
        ensure_started_and_positioned=runtime.ensure_started_and_positioned,
        ensure_top_right_position=runtime.ensure_top_right_position,
    )


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


def run_vacuumtube_minimize_host_runtime(
    *,
    runtime: Any,
    build_minimize_command: Callable[[str], list[str]],
    run_command: Callable[[list[str]], None],
) -> str:
    return run_vacuumtube_minimize(
        find_window_id=runtime.find_window_id,
        build_minimize_command=build_minimize_command,
        run_command=run_command,
    )


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


def run_vacuumtube_stop_music_runtime(
    *,
    open_cdp: Callable[[], Any],
    find_window_id: Callable[[], str | None],
    snapshot_state: Callable[[Any], dict[str, Any]],
    is_watch_state: Callable[[dict[str, Any]], bool],
    send_space_key: Callable[[], None],
    time_now: Callable[[], float],
    sleep: Callable[[float], None],
    ensure_top_right_position: Callable[[], dict[str, Any]],
    log: Callable[[str], None],
) -> str:
    with open_cdp() as cdp:
        return run_vacuumtube_stop_music(
            find_window_id=find_window_id,
            snapshot_state=lambda: snapshot_state(cdp),
            is_watch_state=is_watch_state,
            send_space_key=send_space_key,
            time_now=time_now,
            sleep=sleep,
            ensure_top_right_position=ensure_top_right_position,
            log=log,
        )


def run_vacuumtube_stop_music_host_runtime(
    *,
    runtime: Any,
    time_now: Callable[[], float],
    sleep: Callable[[float], None],
) -> str:
    log = runtime.log if hasattr(runtime, "log") else None
    return run_vacuumtube_stop_music_runtime(
        open_cdp=runtime._cdp,
        find_window_id=runtime.find_window_id,
        snapshot_state=runtime._snapshot_state,
        is_watch_state=runtime._is_watch_state,
        send_space_key=lambda: runtime.send_key("space"),
        time_now=time_now,
        sleep=sleep,
        ensure_top_right_position=runtime.ensure_top_right_position,
        log=log if callable(log) else (lambda _message: None),
    )


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


def run_vacuumtube_play_news_runtime(
    *,
    open_cdp: Callable[[], Any],
    slot: str,
    get_state: Callable[[Any], dict[str, Any]],
    send_return_key: Callable[[], None],
    sleep: Callable[[float], None],
    open_from_home: Callable[[Any, str], str],
) -> str:
    with open_cdp() as cdp:
        return run_vacuumtube_play_news(
            slot=slot,
            get_state=lambda: get_state(cdp),
            send_return_key=send_return_key,
            sleep=sleep,
            open_from_home=lambda label: open_from_home(cdp, label),
        )


def run_vacuumtube_play_news_host_runtime(
    *,
    runtime: Any,
    slot: str,
    sleep: Callable[[float], None],
    filter_tile: Callable[[dict[str, Any]], bool],
) -> str:
    return run_vacuumtube_play_news_runtime(
        open_cdp=runtime._cdp,
        slot=slot,
        get_state=runtime._state,
        send_return_key=lambda: runtime.send_key("Return"),
        sleep=sleep,
        open_from_home=lambda cdp, label: run_vacuumtube_open_from_home_host_runtime(
            cdp=cdp,
            runtime=runtime,
            label=label,
            scorer=lambda tile: runtime._score_news_tile(tile, slot=slot),
            filter_fn=filter_tile,
            allow_soft_playback_confirm=True,
        ),
    )
