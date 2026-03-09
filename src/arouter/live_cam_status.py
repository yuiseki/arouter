from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .cdp_targets import require_cdp_target_list, run_cdp_target_list_http_query


def select_live_cam_page_url(targets: Any) -> str | None:
    if not isinstance(targets, list):
        return None
    for item in targets:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        url = str(item.get("url") or "")
        if "youtube.com/tv" in url:
            return url
    return None


def select_live_cam_page_target(targets: Any) -> dict[str, Any] | None:
    if not isinstance(targets, list):
        return None
    target: dict[str, Any] | None = None
    for item in targets:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        url = str(item.get("url") or "")
        if "youtube.com/tv" in url:
            return item
        if target is None:
            target = item
    return target


def build_live_cam_runtime_url_entry(
    *,
    port: int,
    targets_or_error: Any,
) -> dict[str, Any]:
    if isinstance(targets_or_error, Exception):
        return {"port": int(port), "error": str(targets_or_error)}
    return {"port": int(port), "url": select_live_cam_page_url(targets_or_error)}


def collect_live_cam_runtime_urls(
    specs: list[dict[str, Any]],
    *,
    fetch_targets: Callable[[int], Any],
) -> list[dict[str, Any]]:
    urls: list[dict[str, Any]] = []
    for spec in specs:
        port = int(spec["port"])
        try:
            targets_or_error = fetch_targets(port)
        except Exception as exc:
            targets_or_error = exc
        urls.append(build_live_cam_runtime_url_entry(port=port, targets_or_error=targets_or_error))
    return urls


def collect_live_cam_runtime_state(
    specs: list[dict[str, Any]],
    *,
    rows: list[dict[str, Any]],
    fetch_targets: Callable[[int], Any],
) -> dict[str, Any]:
    return {
        "windows": list(rows),
        "urls": collect_live_cam_runtime_urls(specs, fetch_targets=fetch_targets),
    }


def run_live_cam_runtime_state_cdp_runtime(
    specs: list[dict[str, Any]],
    *,
    rows: list[dict[str, Any]],
    fetch_targets: Callable[[int], Any],
    validate_target_list: Callable[[Any, str], Any] | None,
) -> dict[str, Any]:
    def _validated_targets(port: int) -> Any:
        payload = fetch_targets(int(port))
        if validate_target_list is None:
            if not isinstance(payload, list):
                raise RuntimeError(f"unexpected CDP target list on port {int(port)}")
            return payload
        return validate_target_list(
            payload,
            f"unexpected CDP target list on port {int(port)}",
        )

    return collect_live_cam_runtime_state(
        specs,
        rows=rows,
        fetch_targets=_validated_targets,
    )


def run_live_cam_runtime_state_http_query(
    specs: list[dict[str, Any]],
    *,
    rows: list[dict[str, Any]],
    fetch_json: Callable[..., Any],
    timeout: float = 2.0,
) -> dict[str, Any]:
    return run_live_cam_runtime_state_cdp_runtime(
        specs,
        rows=rows,
        fetch_targets=lambda port: run_cdp_target_list_http_query(
            url=f"http://127.0.0.1:{int(port)}/json",
            timeout=timeout,
            fetch_json=fetch_json,
            validate=require_cdp_target_list,
            error_message=f"unexpected CDP target list on port {int(port)}",
        ),
        validate_target_list=None,
    )


def run_live_cam_runtime_state_host_runtime_query(
    *,
    runtime: Any,
    pids_by_port: dict[int, int],
    fetch_json: Callable[..., Any],
) -> dict[str, Any]:
    rows = runtime._window_rows_by_pids(list(pids_by_port.values()))
    return run_live_cam_runtime_state_http_query(
        list(runtime.instances),
        rows=rows,
        fetch_json=fetch_json,
        timeout=2.0,
    )


def collect_live_cam_pages_by_port(
    specs: list[dict[str, Any]],
    *,
    fetch_page_brief: Callable[[int], dict[str, Any]],
) -> dict[int, dict[str, Any] | Exception]:
    pages_by_port: dict[int, dict[str, Any] | Exception] = {}
    for spec in specs:
        port = int(spec["port"])
        try:
            pages_by_port[port] = fetch_page_brief(port)
        except Exception as exc:
            pages_by_port[port] = exc
    return pages_by_port


def build_live_cam_page_brief(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": str(target.get("url") or ""),
        "title": str(target.get("title") or ""),
    }


def merge_live_cam_page_snapshot(
    brief: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
    inspect_error: Exception | None = None,
) -> dict[str, Any]:
    out = dict(brief)
    if inspect_error is not None:
        out["inspectError"] = str(inspect_error)
        return out
    if not isinstance(snapshot, dict):
        return out
    for key in ("title", "url", "hash", "bodyText", "watchText"):
        value = snapshot.get(key)
        if isinstance(value, str):
            out[key] = value
    return out


def run_live_cam_page_snapshot_query(
    *,
    evaluate: Callable[[str], Any],
) -> dict[str, Any]:
    expr = r"""
(() => {
  const txt = ((document.body && document.body.innerText) || '').replace(/\s+/g, ' ').trim();
  const bodyText = txt.slice(0, 4000);
  const tags = ['ytlr-video-title-tray', 'ytlr-watch-metadata', 'ytlr-video-owner-renderer'];
  const watchParts = [];
  for (const tag of tags) {
    try {
      document.querySelectorAll(tag).forEach((el) => {
        const t = ((el.innerText || el.textContent) || '').replace(/\s+/g, ' ').trim();
        if (t) watchParts.push(t);
      });
    } catch (_) {}
  }
  return {
    title: document.title || '',
    url: location.href || '',
    hash: location.hash || '',
    bodyText,
    watchText: watchParts.join(' | ').slice(0, 1000),
  };
})()
"""
    data = evaluate(expr)
    return data if isinstance(data, dict) else {}


def run_live_cam_page_snapshot_via_websocket(
    *,
    ws_url: str,
    create_client: Callable[[str], Any],
    enable_client: Callable[[Any], None],
    query_snapshot: Callable[[Any], dict[str, Any] | None],
) -> dict[str, Any] | None:
    client = create_client(ws_url)
    enable_client(client)
    snapshot = query_snapshot(client)
    return snapshot if isinstance(snapshot, dict) else None


def run_live_cam_target_inspection(
    *,
    target: dict[str, Any],
    inspect_websocket: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any] | None:
    ws_url = target.get("webSocketDebuggerUrl")
    if not isinstance(ws_url, str) or not ws_url:
        return None
    snapshot = inspect_websocket(ws_url)
    return snapshot if isinstance(snapshot, dict) else None


def run_live_cam_target_snapshot_runtime(
    *,
    target: dict[str, Any],
    create_client: Callable[[str], Any],
    enable_client: Callable[[Any], None],
    query_snapshot: Callable[[Any], dict[str, Any] | None],
) -> dict[str, Any] | None:
    return run_live_cam_target_inspection(
        target=target,
        inspect_websocket=lambda ws_url: run_live_cam_page_snapshot_via_websocket(
            ws_url=ws_url,
            create_client=create_client,
            enable_client=enable_client,
            query_snapshot=query_snapshot,
        ),
    )


def run_live_cam_target_snapshot_cdp_runtime(
    *,
    target: dict[str, Any],
    create_client: Callable[[str], Any],
    query_snapshot: Callable[[Any], dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    snapshot_query = query_snapshot or (
        lambda client: run_live_cam_page_snapshot_query(
            evaluate=lambda expr: client.evaluate(expr),
        )
    )
    return run_live_cam_target_snapshot_runtime(
        target=target,
        create_client=create_client,
        enable_client=lambda client: client.enable_basics(),
        query_snapshot=snapshot_query,
    )


def run_live_cam_page_brief_flow(
    *,
    port: int,
    fetch_targets: Callable[[int], Any],
    validate_target_list: Callable[[Any, str], Any] | None,
    select_target: Callable[[Any], dict[str, Any] | None],
    build_brief: Callable[[dict[str, Any]], dict[str, Any]],
    inspect_target: Callable[[dict[str, Any]], dict[str, Any] | None],
    merge_snapshot: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    data = fetch_targets(int(port))
    if validate_target_list is not None:
        data = validate_target_list(data, f"unexpected CDP target list on port {int(port)}")
    elif not isinstance(data, list):
        raise RuntimeError(f"unexpected CDP target list on port {int(port)}")

    target = select_target(data)
    if not target:
        raise RuntimeError(f"no page target on port {int(port)}")

    brief = build_brief(target)
    try:
        snapshot = inspect_target(target)
    except Exception as exc:
        return merge_snapshot(brief, inspect_error=exc)
    return merge_snapshot(brief, snapshot=snapshot if isinstance(snapshot, dict) else None)


def run_live_cam_page_brief_cdp_runtime(
    *,
    port: int,
    fetch_targets: Callable[[int], Any],
    validate_target_list: Callable[[Any, str], Any] | None,
    select_target: Callable[[Any], dict[str, Any] | None],
    build_brief: Callable[[dict[str, Any]], dict[str, Any]],
    create_client: Callable[[str], Any],
    query_snapshot: Callable[[Any], dict[str, Any] | None] | None = None,
    merge_snapshot: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    return run_live_cam_page_brief_flow(
        port=port,
        fetch_targets=fetch_targets,
        validate_target_list=validate_target_list,
        select_target=select_target,
        build_brief=build_brief,
        inspect_target=lambda target: run_live_cam_target_snapshot_cdp_runtime(
            target=target,
            create_client=create_client,
            query_snapshot=query_snapshot,
        ),
        merge_snapshot=merge_snapshot,
    )


def run_live_cam_page_brief_http_query(
    *,
    port: int,
    fetch_json: Callable[..., Any],
    create_client: Callable[[str], Any],
    query_snapshot: Callable[[Any], dict[str, Any] | None] | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    return run_live_cam_page_brief_cdp_runtime(
        port=port,
        fetch_targets=lambda current_port: run_cdp_target_list_http_query(
            url=f"http://127.0.0.1:{int(current_port)}/json",
            timeout=timeout,
            fetch_json=fetch_json,
            validate=require_cdp_target_list,
            error_message=f"unexpected CDP target list on port {int(current_port)}",
        ),
        validate_target_list=None,
        select_target=select_live_cam_page_target,
        build_brief=build_live_cam_page_brief,
        create_client=create_client,
        query_snapshot=query_snapshot,
        merge_snapshot=merge_live_cam_page_snapshot,
    )


def run_live_cam_page_brief_runtime_flow(
    *,
    port: int,
    fetch_json: Callable[..., Any],
    client_factory: Callable[..., Any],
    http_timeout: float = 2.0,
    client_timeout: float = 4.0,
) -> dict[str, Any]:
    return run_live_cam_page_brief_http_query(
        port=port,
        fetch_json=fetch_json,
        create_client=lambda ws_url: client_factory(
            ws_url,
            timeout_sec=client_timeout,
        ),
        timeout=http_timeout,
    )


def run_live_cam_page_brief_host_runtime_flow(
    *,
    runtime: Any,
    port: int,
    fetch_json: Callable[..., Any],
    client_factory: Callable[..., Any],
) -> dict[str, Any]:
    return run_live_cam_page_brief_runtime_flow(
        port=port,
        fetch_json=fetch_json,
        client_factory=client_factory,
        http_timeout=2.0,
        client_timeout=4.0,
    )


def page_matches_live_camera_spec(spec: dict[str, Any], page: dict[str, Any]) -> bool:
    url = str(page.get("url") or "")
    if "youtube.com/tv" not in url or "watch?v=" not in url:
        return False

    patterns: list[str] = []
    primary_pattern = (
        str(spec.get("verify_regex") or "").strip()
        or str(spec.get("keyword") or "").strip()
    )
    if primary_pattern:
        patterns.append(primary_pattern)
    for fallback in spec.get("fallbacks") or []:
        if not isinstance(fallback, dict):
            continue
        fallback_pattern = str(fallback.get("verify_regex") or "").strip() or str(
            fallback.get("keyword") or ""
        ).strip()
        if fallback_pattern:
            patterns.append(fallback_pattern)
    if not patterns:
        return True

    combined = " ".join(
        part
        for part in (
            str(page.get("title") or ""),
            str(page.get("watchText") or ""),
            str(page.get("bodyText") or ""),
        )
        if part
    )
    if not combined.strip():
        return False
    for pattern in patterns:
        try:
            if re.search(pattern, combined, flags=re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in combined.lower():
                return True
    return False


def find_stuck_live_cam_specs(
    specs: list[dict[str, Any]],
    *,
    pages_by_port: dict[int, dict[str, Any] | Exception],
) -> list[dict[str, Any]]:
    stuck: list[dict[str, Any]] = []
    for spec in specs:
        port = int(spec["port"])
        page_or_error = pages_by_port.get(port)
        if isinstance(page_or_error, Exception) or page_or_error is None:
            stuck.append(spec)
            continue
        if not page_matches_live_camera_spec(spec, page_or_error):
            stuck.append(spec)
    return stuck


def run_live_cam_stuck_specs_query(
    specs: list[dict[str, Any]],
    *,
    fetch_page_brief: Callable[[int], dict[str, Any]],
) -> list[dict[str, Any]]:
    pages_by_port = collect_live_cam_pages_by_port(
        specs,
        fetch_page_brief=fetch_page_brief,
    )
    return find_stuck_live_cam_specs(specs, pages_by_port=pages_by_port)


def run_live_cam_stuck_specs_host_runtime_query(*, runtime: Any) -> list[dict[str, Any]]:
    return run_live_cam_stuck_specs_query(
        list(runtime.instances),
        fetch_page_brief=runtime._page_brief_for_port,
    )
