from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, object] = {
    "show_agent_windows": False,
}


class SettingsStore:
    def __init__(self, data_dir: Path) -> None:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self._file = Path(data_dir) / "settings.json"
        self._lock = Lock()
        self._data: dict[str, object] = {**DEFAULTS}
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for key, default_val in DEFAULTS.items():
                    if key in loaded and not isinstance(loaded[key], type(default_val)):
                        logger.warning(
                            "settings_store: ignoring %r with unexpected type %s (expected %s)",
                            key, type(loaded[key]).__name__, type(default_val).__name__,
                        )
                        loaded.pop(key)
                self._data.update(loaded)
            except Exception:
                logger.warning("settings_store: failed to load %s, using defaults", self._file)

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._file)

    def get(self, key: str) -> object:
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: object) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def get_all(self) -> dict[str, object]:
        with self._lock:
            return {**DEFAULTS, **self._data}
