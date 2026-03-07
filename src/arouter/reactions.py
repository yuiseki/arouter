from __future__ import annotations

import re


def detect_non_command_reaction(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    compact = re.sub(r"[\s、,。．!！?？・…]+", "", raw)
    if re.search(r"(?:[はハ][っッ]){2,}", compact):
        return "laugh"
    return None
