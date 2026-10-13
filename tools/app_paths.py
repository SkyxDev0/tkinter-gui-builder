"""Wo PyInstaller die App ablegt (gemeinsam für package.py und smoke_test.py)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def app_path() -> Path:
    """Pfad zur ausführbaren Datei der gebauten App."""
    dist = ROOT / "dist"
    if sys.platform == "darwin":
        return dist / "CTk Builder.app" / "Contents" / "MacOS" / "CTk Builder"
    if sys.platform == "win32":
        return dist / "CTk-Builder.exe"
    return dist / "ctk-builder"
