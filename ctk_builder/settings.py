"""Builder-Einstellungen (z. B. Python-Interpreter) in ~/.ctk_builder.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path.home() / ".ctk_builder.json"


class Settings:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError):
            pass  # fehlende oder kaputte Einstellungen -> Standardwerte

    @property
    def interpreter(self) -> str:
        return self.data.get("interpreter") or sys.executable

    @interpreter.setter
    def interpreter(self, value: str) -> None:
        self.data["interpreter"] = value
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
