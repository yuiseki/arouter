from __future__ import annotations

import time

from arouter import build_live_cam_open_result, run_live_cam_parallel


def test_run_live_cam_parallel_preserves_input_order() -> None:
    specs = [
        {"label": "a", "port": 9993},
        {"label": "b", "port": 9994},
        {"label": "c", "port": 9995},
    ]

    def worker(spec: dict[str, int | str]) -> dict[str, int | str]:
        if spec["label"] == "a":
            time.sleep(0.03)
        if spec["label"] == "b":
            time.sleep(0.01)
        return {"label": spec["label"], "port": spec["port"]}

    out = run_live_cam_parallel(specs, worker=worker, label="test")

    assert [x["label"] for x in out] == ["a", "b", "c"]
    assert [x["port"] for x in out] == [9993, 9994, 9995]


def test_run_live_cam_parallel_raises_with_port_context() -> None:
    specs = [
        {"label": "ok", "port": 9993},
        {"label": "ng", "port": 9994},
    ]

    def worker(spec: dict[str, int | str]) -> dict[str, bool]:
        if spec["label"] == "ng":
            raise RuntimeError("boom")
        return {"ok": True}

    try:
        run_live_cam_parallel(specs, worker=worker, label="test")
    except RuntimeError as exc:
        assert "9994" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_build_live_cam_open_result_extracts_final_href() -> None:
    result = build_live_cam_open_result(
        {"label": "akihabara", "port": 9994},
        {
            "videoId": "abc123DEF45",
            "method": "direct-id",
            "final": {"href": "https://www.youtube.com/tv#/watch?v=abc123DEF45"},
        },
    )

    assert result == {
        "label": "akihabara",
        "port": 9994,
        "videoId": "abc123DEF45",
        "finalHref": "https://www.youtube.com/tv#/watch?v=abc123DEF45",
        "method": "direct-id",
    }
