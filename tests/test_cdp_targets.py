from __future__ import annotations

import pytest

from arouter import require_cdp_target_list, run_cdp_target_list_query


def test_require_cdp_target_list_filters_non_dict_items() -> None:
    assert require_cdp_target_list([{"type": "page"}, "ignored", 1], "bad payload") == [
        {"type": "page"}
    ]


def test_require_cdp_target_list_raises_for_non_list_payload() -> None:
    with pytest.raises(RuntimeError, match="bad payload"):
        require_cdp_target_list({"type": "page"}, "bad payload")


def test_run_cdp_target_list_query_fetches_and_validates_payload() -> None:
    assert run_cdp_target_list_query(
        fetch_json=lambda: [{"type": "page"}, "ignored"],
        validate=require_cdp_target_list,
        error_message="bad payload",
    ) == [{"type": "page"}]
