"""Baut die eigenständige App mit PyInstaller.

Aufruf (im Projektordner):  python tools/build.py
Ergebnis in dist/:
  macOS    CTk Builder.app
  Windows  CTk-Builder.exe
  Linux    ctk-builder
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent

NAMES = {"darwin": "CTk Builder", "win32": "CTk-Builder"}


def app_name() -> str:
    return NAMES.get(sys.platform, "ctk-builder")


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from ctk_builder import __version__

    args = [
        str(ROOT / "tools" / "launcher.py"),
        "--name", app_name(),
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths", str(ROOT),
        "--collect-data", "customtkinter",  # Farbthemen und Schriften
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
    ]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "io.github.skyxdev0.ctkbuilder"]
    else:
        args.append("--onefile")
    print(f"Baue {app_name()} {__version__} …")
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
