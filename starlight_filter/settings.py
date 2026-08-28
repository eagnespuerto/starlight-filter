"""Persist the current preset across launches.

Stored in ``%APPDATA%\\Starlight Filter\\state.json`` so autostart at sign-in
can bring the last chosen color temperature straight back.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


APP_NAME = "Starlight Filter"


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def _config_file() -> Path:
    return _config_dir() / "state.json"


def save(temperature_k: float) -> None:
    try:
        _config_dir().mkdir(parents=True, exist_ok=True)
        _config_file().write_text(
            json.dumps({"temperature_k": float(temperature_k)}),
            encoding="utf-8",
        )
    except OSError:
        # Best-effort — losing persistence should never crash the app.
        pass


def load() -> Optional[float]:
    try:
        data = json.loads(_config_file().read_text(encoding="utf-8"))
        return float(data["temperature_k"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
