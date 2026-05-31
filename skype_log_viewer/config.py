from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "SkypeLogViewer"
MAX_RECENT = 10


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = config_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


_DEFAULTS = {
    "last_file": None,
    "recent_files": [],
    "show_system": False,
    "show_empty": False,
    "positions": {},  # conversation id -> message index
}


class Config:
    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path) if path else (config_dir() / "config.json")
        self.data = dict(_DEFAULTS)
        self.data["recent_files"] = []
        self.data["positions"] = {}
        self.load()

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                merged = dict(_DEFAULTS)
                merged["recent_files"] = []
                merged["positions"] = {}
                merged.update(loaded)
                self.data = merged
        except Exception:
            pass  # missing or corrupt -> keep defaults

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    # --- typed accessors ---
    @property
    def last_file(self) -> Optional[str]:
        return self.data.get("last_file")

    @last_file.setter
    def last_file(self, value: Optional[str]) -> None:
        self.data["last_file"] = value

    @property
    def recent_files(self) -> list[str]:
        return self.data.get("recent_files", [])

    @property
    def show_system(self) -> bool:
        return bool(self.data.get("show_system", False))

    @show_system.setter
    def show_system(self, value: bool) -> None:
        self.data["show_system"] = bool(value)

    @property
    def show_empty(self) -> bool:
        return bool(self.data.get("show_empty", False))

    @show_empty.setter
    def show_empty(self, value: bool) -> None:
        self.data["show_empty"] = bool(value)

    def add_recent(self, file_path: str) -> None:
        recent = [f for f in self.recent_files if f != file_path]
        recent.insert(0, file_path)
        self.data["recent_files"] = recent[:MAX_RECENT]

    def get_position(self, conv_id: str) -> Optional[int]:
        value = self.data.get("positions", {}).get(conv_id)
        return int(value) if value is not None else None

    def set_position(self, conv_id: str, index: int) -> None:
        self.data.setdefault("positions", {})[conv_id] = int(index)
