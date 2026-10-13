"""Baut die eigenständige App mit PyInstaller.

Aufruf (im Projektordner):  python tools/build.py
Ergebnis in dist/:
  macOS    CTk Builder.app
  Windows  CTk-Builder.exe
  Linux    ctk-builder
"""

from __future__ import annotations

import plistlib
import re
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent

NAMES = {"darwin": "CTk Builder", "win32": "CTk-Builder"}


def app_name() -> str:
    return NAMES.get(sys.platform, "ctk-builder")


def bundle_version(version: str) -> str:
    """Versionsnummer für Info.plist: 1–3 durch Punkte getrennte Zahlen („1.0.1“)."""
    match = re.match(r"\d+(?:\.\d+){0,2}", version)
    if not match:
        raise SystemExit(f"Version {version!r} passt nicht in Info.plist")
    return match.group(0)


def stamp_macos_bundle(bundle: Path, version: str) -> None:
    """Schreibt die Version ins Info.plist und signiert das Bundle neu (ad hoc).

    PyInstaller trägt ohne Spec-Datei nur „0.0.0“ und keine CFBundleVersion ein.
    Info.plist gehört zur Signatur, die PyInstaller schon erstellt hat – ohne
    neue Signatur meldet macOS die heruntergeladene App als „beschädigt“.
    """
    number = bundle_version(version)
    plist_path = bundle / "Contents" / "Info.plist"
    info = plistlib.loads(plist_path.read_bytes())
    info["CFBundleShortVersionString"] = number
    info["CFBundleVersion"] = number
    plist_path.write_bytes(plistlib.dumps(info))
    # derselbe Befehl, mit dem PyInstaller signiert (PyInstaller/utils/osx.py)
    subprocess.run(["/usr/bin/codesign", "-s", "-", "--force", "--all-architectures",
                    "--timestamp", "--deep", str(bundle)], check=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2",
                    str(bundle)], check=True)


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
    print(f"Baue {app_name()} {__version__} ...")
    PyInstaller.__main__.run(args)
    if sys.platform == "darwin":
        stamp_macos_bundle(ROOT / "dist" / f"{app_name()}.app", __version__)


if __name__ == "__main__":
    main()
