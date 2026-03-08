from __future__ import annotations

import pytest

from arouter import require_cdp_target_list


def test_require_cdp_target_list_filters_non_dict_items() -> None:
    assert require_cdp_target_list([{"type": "page"}, "ignored", 1], "bad payload") == [
        {"type": "page"}
    ]


def test_require_cdp_target_list_raises_for_non_list_payload() -> None:
    with pytest.raises(RuntimeError, match="bad payload"):
        require_cdp_target_list({"type": "page"}, "bad payload")
