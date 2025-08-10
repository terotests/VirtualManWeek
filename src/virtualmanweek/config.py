import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict

APP_NAME = "VirtualManWeek"


def appdata_root() -> Path:
    base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    root = base / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def settings_path() -> Path:
    return appdata_root() / "settings.json"


DEFAULT_SETTINGS = {
    "idle_timeout_seconds": 300,
    "tag_cloud_limit": 10,
    "discard_sub_10s_entries": True,
    "language": "en",
    # Remember currently selected database path (absolute). If null, default appdata path is used.
    "database_path": None,
}


@dataclass
class Settings:
    idle_timeout_seconds: int = DEFAULT_SETTINGS["idle_timeout_seconds"]
    tag_cloud_limit: int = DEFAULT_SETTINGS["tag_cloud_limit"]
    discard_sub_10s_entries: bool = DEFAULT_SETTINGS["discard_sub_10s_entries"]
    language: str = DEFAULT_SETTINGS["language"]
    database_path: str | None = DEFAULT_SETTINGS["database_path"]

    @classmethod
    def load(cls) -> "Settings":
        p = settings_path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
        merged = {**DEFAULT_SETTINGS, **data}
        return cls(**merged)

    def save(self) -> None:
        p = settings_path()
        with p.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
