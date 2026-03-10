from __future__ import annotations

from arouter import (
    build_vacuumtube_context_error,
    resolve_vacuumtube_context_cache,
    resolve_vacuumtube_context_cache_host_runtime,
)


def test_build_vacuumtube_context_error_returns_unavailable_payload() -> None:
    payload = build_vacuumtube_context_error(ts=12.5, error=RuntimeError("boom"))

    assert payload == {
        "ts": 12.5,
        "available": False,
        "error": "boom",
    }


def test_resolve_vacuumtube_context_cache_returns_fresh_snapshot() -> None:
    cached = {"ts": 10.0, "available": True}

    out = resolve_vacuumtube_context_cache(
        cached,
        now_ts=12.0,
        max_age_sec=3.0,
        refresh_if_stale=True,
        refresh_context=lambda: {"refreshed": True},
    )

    assert out == cached


def test_resolve_vacuumtube_context_cache_refreshes_stale_snapshot() -> None:
    out = resolve_vacuumtube_context_cache(
        {"ts": 1.0, "available": True},
        now_ts=10.0,
        max_age_sec=3.0,
        refresh_if_stale=True,
        refresh_context=lambda: {"refreshed": True},
    )

    assert out == {"refreshed": True}


def test_resolve_vacuumtube_context_cache_keeps_stale_snapshot_when_refresh_disabled() -> None:
    cached = {"ts": 1.0, "available": True}

    out = resolve_vacuumtube_context_cache(
        cached,
        now_ts=10.0,
        max_age_sec=3.0,
        refresh_if_stale=False,
        refresh_context=lambda: {"refreshed": True},
    )

    assert out == cached


def test_resolve_vacuumtube_context_cache_host_runtime_uses_runtime_refresh() -> None:
    runtime = type(
        "Runtime",
        (),
        {
            "_refresh_vacuumtube_context_cache": staticmethod(
                lambda *, reason: {"reason": reason, "refreshed": True}
            )
        },
    )()

    out = resolve_vacuumtube_context_cache_host_runtime(
        runtime=runtime,
        cached={"ts": 1.0, "available": True},
        now_ts=10.0,
        max_age_sec=3.0,
        refresh_if_stale=True,
    )

    assert out == {"reason": "on-demand", "refreshed": True}
