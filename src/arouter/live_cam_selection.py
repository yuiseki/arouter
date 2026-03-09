from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

LiveCamCommandRunner = Callable[[list[str], float], tuple[int, str, str]]
LiveCamProcessRunner = Callable[..., Any]
LiveCamPageVerifier = Callable[[dict[str, Any]], bool]
LiveCamCandidateExpander = Callable[[dict[str, Any]], list[dict[str, Any]]]
LiveCamForceIdNormalizer = Callable[[dict[str, Any]], str]
LiveCamForceCommandBuilder = Callable[[dict[str, Any], str], list[str]]
LiveCamBrowseCommandBuilder = Callable[[dict[str, Any]], list[str]]
LiveCamJsonParseFailureBuilder = Callable[[dict[str, Any], int, str], dict[str, Any]]
LiveCamForceRetryFailureBuilder = Callable[[dict[str, Any], str], dict[str, Any]]
LiveCamCommandFailureBuilder = Callable[
    [dict[str, Any], int, dict[str, Any] | None, str],
    dict[str, Any],
]
LiveCamRetryVideoResolver = Callable[[dict[str, Any]], str]
LiveCamPayloadAnnotator = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
LiveCamSelectionErrorFormatter = Callable[[int, list[dict[str, Any]]], str]
LiveCamLogger = Callable[[str], None]


def expand_live_cam_candidates(spec: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [dict(spec)]
    for fallback in spec.get("fallbacks") or []:
        if not isinstance(fallback, dict):
            continue
        merged = dict(spec)
        merged.update(fallback)
        merged.pop("fallbacks", None)
        candidates.append(merged)
    return candidates


def normalize_live_cam_force_video_id(candidate: dict[str, Any]) -> str:
    force_video_id = str(candidate.get("force_video_id") or "")
    if force_video_id and re.match(r"^[A-Za-z0-9_-]{11}$", force_video_id):
        return force_video_id
    return ""


def web_watch_retry_video_id(payload: dict[str, Any]) -> str:
    if str(payload.get("method") or "") != "web-streams-fallback-web-watch":
        return ""
    video_id = str(payload.get("videoId") or "")
    if video_id and re.match(r"^[A-Za-z0-9_-]{11}$", video_id):
        return video_id
    return ""


def annotate_live_cam_payload_selection(
    payload: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    payload.setdefault("selectedKeyword", str(candidate.get("keyword") or ""))
    payload.setdefault("selectedVerifyRegex", str(candidate.get("verify_regex") or ""))
    return payload


def build_live_cam_force_video_command(
    fast_open_script: str | Path,
    candidate: dict[str, Any],
    *,
    force_video_id: str,
) -> list[str]:
    return [
        "node",
        str(fast_open_script),
        "--cdp-port",
        str(candidate["port"]),
        "--force-video-id",
        str(force_video_id),
        "--keyword",
        str(candidate.get("keyword") or ""),
    ]


def build_live_cam_browse_command(
    fast_open_script: str | Path,
    candidate: dict[str, Any],
) -> list[str]:
    return [
        "node",
        str(fast_open_script),
        "--cdp-port",
        str(candidate["port"]),
        "--browse-url",
        str(candidate["browse_url"]),
        "--keyword",
        str(candidate["keyword"]),
        "--verify-regex",
        str(candidate["verify_regex"]),
    ]


def build_live_cam_json_parse_failure(
    candidate: dict[str, Any],
    *,
    returncode: int,
    error: str,
) -> dict[str, Any]:
    return {
        "keyword": str(candidate.get("keyword") or ""),
        "returncode": int(returncode),
        "error": f"json-parse: {error}",
    }


def build_live_cam_force_retry_failure(
    candidate: dict[str, Any],
    *,
    video_id: str,
) -> dict[str, Any]:
    return {
        "keyword": str(candidate.get("keyword") or ""),
        "reason": "web-watch-rejected-force-failed",
        "videoId": str(video_id or ""),
    }


def build_live_cam_command_failure(
    candidate: dict[str, Any],
    *,
    returncode: int,
    payload: dict[str, Any] | None,
    stderr: str,
) -> dict[str, Any]:
    return {
        "keyword": str(candidate.get("keyword") or ""),
        "returncode": int(returncode),
        "payload": payload if isinstance(payload, dict) else None,
        "stderr": str(stderr or "").strip(),
    }


def format_live_cam_selection_error(port: int, failures: list[dict[str, Any]]) -> str:
    failures_json = json.dumps(failures, ensure_ascii=False)
    return f"live camera select failed on port {int(port)}: {failures_json}"


def _parse_live_cam_payload(stdout: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads((stdout or "").strip() or "{}")
    except Exception as exc:
        return None, str(exc)
    if isinstance(payload, dict):
        return payload, None
    return None, "payload is not an object"


def select_live_cam_payload(
    spec: dict[str, Any],
    *,
    expand_candidates: LiveCamCandidateExpander,
    normalize_force_video_id: LiveCamForceIdNormalizer,
    build_force_video_command: LiveCamForceCommandBuilder,
    build_browse_command: LiveCamBrowseCommandBuilder,
    build_json_parse_failure: LiveCamJsonParseFailureBuilder,
    build_force_retry_failure: LiveCamForceRetryFailureBuilder,
    build_command_failure: LiveCamCommandFailureBuilder,
    web_watch_retry_video_id: LiveCamRetryVideoResolver,
    annotate_payload_selection: LiveCamPayloadAnnotator,
    format_selection_error: LiveCamSelectionErrorFormatter,
    run_command: LiveCamCommandRunner,
    verify_force_candidate_page: LiveCamPageVerifier,
    log: LiveCamLogger | None = None,
) -> dict[str, Any]:
    def _log(message: str) -> None:
        if log is not None:
            log(message)

    def _try_force_video_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
        force_video_id = normalize_force_video_id(candidate)
        if not force_video_id:
            return None

        command = build_force_video_command(candidate, force_video_id)
        _log(
            f"LIVE_CAM force_video_id primary for {candidate.get('label', candidate['port'])}: "
            f"{force_video_id}"
        )
        _returncode, stdout, _stderr = run_command(command, 20.0)
        payload, _error = _parse_live_cam_payload(stdout)
        if not (isinstance(payload, dict) and bool(payload.get("ok"))):
            _log(
                f"LIVE_CAM force_video_id failed for {candidate.get('label', candidate['port'])}, "
                "falling back to browse search"
            )
            return None
        if not verify_force_candidate_page(candidate):
            _log(
                f"LIVE_CAM force_video_id landed on unexpected page for "
                f"{candidate.get('label', candidate['port'])}, falling back to browse search"
            )
            return None
        return annotate_payload_selection(payload, candidate)

    candidates = expand_candidates(spec)
    failures: list[dict[str, Any]] = []

    for candidate in candidates:
        force_payload = _try_force_video_candidate(candidate)
        if force_payload:
            return force_payload

        command = build_browse_command(candidate)
        returncode, stdout, stderr = run_command(command, 45.0)
        payload, parse_error = _parse_live_cam_payload(stdout)
        if payload is None:
            failures.append(
                build_json_parse_failure(
                    candidate,
                    int(returncode),
                    str(parse_error or "unknown parse error"),
                )
            )
            continue

        if bool(payload.get("ok")):
            video_id = web_watch_retry_video_id(payload)
            if video_id:
                force_command = build_force_video_command(candidate, video_id)
                _log(
                    f"LIVE_CAM web-watch rejected for {candidate.get('label', candidate['port'])}, "
                    f"retrying as TV URL via --force-video-id {video_id}"
                )
                _force_returncode, force_stdout, _force_stderr = run_command(
                    force_command,
                    15.0,
                )
                force_payload, _force_error = _parse_live_cam_payload(force_stdout)
                if isinstance(force_payload, dict) and bool(force_payload.get("ok")):
                    return annotate_payload_selection(force_payload, candidate)
                failures.append(
                    build_force_retry_failure(
                        candidate,
                        str(payload.get("videoId") or ""),
                    )
                )
                continue
            return annotate_payload_selection(payload, candidate)

        failures.append(
            build_command_failure(
                candidate,
                int(returncode),
                payload,
                str(stderr or ""),
            )
        )

    raise RuntimeError(format_selection_error(int(spec["port"]), failures))


def run_live_cam_payload_selection_runtime(
    spec: dict[str, Any],
    *,
    fast_open_script: str | Path,
    run_command: LiveCamCommandRunner,
    verify_force_candidate_page: LiveCamPageVerifier,
    log: LiveCamLogger | None = None,
) -> dict[str, Any]:
    def _build_force_video_command(
        candidate: dict[str, Any],
        force_video_id: str,
    ) -> list[str]:
        return build_live_cam_force_video_command(
            fast_open_script,
            candidate,
            force_video_id=force_video_id,
        )

    def _build_browse_command(candidate: dict[str, Any]) -> list[str]:
        return build_live_cam_browse_command(
            fast_open_script,
            candidate,
        )

    def _build_json_failure(
        candidate: dict[str, Any],
        returncode: int,
        error: str,
    ) -> dict[str, Any]:
        return build_live_cam_json_parse_failure(
            candidate,
            returncode=returncode,
            error=error,
        )

    def _build_force_retry_failure(
        candidate: dict[str, Any],
        video_id: str,
    ) -> dict[str, Any]:
        return build_live_cam_force_retry_failure(
            candidate,
            video_id=video_id,
        )

    def _build_command_failure(
        candidate: dict[str, Any],
        returncode: int,
        payload: dict[str, Any] | None,
        stderr: str,
    ) -> dict[str, Any]:
        return build_live_cam_command_failure(
            candidate,
            returncode=returncode,
            payload=payload,
            stderr=stderr,
        )

    return select_live_cam_payload(
        spec,
        expand_candidates=expand_live_cam_candidates,
        normalize_force_video_id=normalize_live_cam_force_video_id,
        build_force_video_command=_build_force_video_command,
        build_browse_command=_build_browse_command,
        build_json_parse_failure=_build_json_failure,
        build_force_retry_failure=_build_force_retry_failure,
        build_command_failure=_build_command_failure,
        web_watch_retry_video_id=web_watch_retry_video_id,
        annotate_payload_selection=annotate_live_cam_payload_selection,
        format_selection_error=format_live_cam_selection_error,
        run_command=run_command,
        verify_force_candidate_page=verify_force_candidate_page,
        log=log,
    )


def run_live_cam_payload_selection_runtime_flow(
    spec: dict[str, Any],
    *,
    fast_open_script: str | Path,
    run_process: LiveCamProcessRunner,
    page_brief_for_port: Callable[[int], dict[str, Any]],
    page_matches_spec: Callable[[dict[str, Any], dict[str, Any]], bool],
    log: LiveCamLogger | None = None,
) -> dict[str, Any]:
    def _run_command(command: list[str], timeout: float) -> tuple[int, str, str]:
        completed = run_process(command, timeout=timeout, check=False)
        return (
            int(getattr(completed, "returncode", 0)),
            str(getattr(completed, "stdout", "") or ""),
            str(getattr(completed, "stderr", "") or ""),
        )

    def _verify_force_candidate_page(candidate: dict[str, Any]) -> bool:
        try:
            page = page_brief_for_port(int(candidate["port"]))
        except Exception as exc:
            if log is not None:
                log(
                    "LIVE_CAM force_video_id verify probe failed for "
                    f"{candidate.get('label', candidate['port'])}: {exc}"
                )
            return False
        return bool(page_matches_spec(candidate, page))

    return run_live_cam_payload_selection_runtime(
        spec,
        fast_open_script=fast_open_script,
        run_command=_run_command,
        verify_force_candidate_page=_verify_force_candidate_page,
        log=log,
    )


def run_live_cam_payload_selection_host_runtime_flow(
    spec: dict[str, Any],
    *,
    runtime: Any,
) -> dict[str, Any]:
    log = runtime.log if hasattr(runtime, "log") else None
    return run_live_cam_payload_selection_runtime_flow(
        spec,
        fast_open_script=runtime.fast_open_script,
        run_process=runtime._run,
        page_brief_for_port=runtime._page_brief_for_port,
        page_matches_spec=runtime._page_matches_live_camera_spec,
        log=log if callable(log) else None,
    )
