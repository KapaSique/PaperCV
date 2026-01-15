from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from cv.config import CVSettings


def load_settings(path: str) -> CVSettings:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return CVSettings()
    with cfg_path.open("r") as fh:
        data: Dict[str, Any] = yaml.safe_load(fh) or {}
    return CVSettings.from_dict(data)


def persist_settings(path: str, payload: Dict[str, Any]) -> None:
    cfg_path = Path(path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w") as fh:
        yaml.safe_dump(payload, fh)
