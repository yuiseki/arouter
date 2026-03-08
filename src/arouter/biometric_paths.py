from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def resolve_biometric_arg_path(
    *,
    args: Any,
    attr_name: str,
    default_path: str | Path,
) -> Path:
    raw = getattr(args, attr_name, default_path)
    return Path(os.path.expanduser(str(raw)))
