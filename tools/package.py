"""Verpackt die gebaute App aus dist/ als Download-Datei in release/.

Aufruf nach tools/build.py:  python tools/package.py
  macOS    CTk-Builder-<version>-macOS-AppleSilicon.zip  (enthält CTk Builder.app)
  Windows  CTk-Builder-<version>-Windows.exe
  Linux    CTk-Builder-<version>-Linux.tar.gz           (enthält ctk-builder)
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ctk_builder import __version__  # noqa: E402
from app_paths import app_path  # noqa: E402


def main() -> Path:
    out = ROOT / "release"
    out.mkdir(exist_ok=True)
    app = app_path()
    stem = f"CTk-Builder-{__version__}"
    if sys.platform == "darwin":
        arch = "AppleSilicon" if platform.machine() == "arm64" else "Intel"
        target = out / f"{stem}-macOS-{arch}.zip"
        bundle = app.parents[2]  # …/CTk Builder.app/Contents/MacOS/CTk Builder
        # ditto erhält Symlinks und Rechte im App-Bundle (zipfile täte das nicht)
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(bundle), str(target)], check=True)
    elif sys.platform == "win32":
        target = out / f"{stem}-Windows.exe"
        shutil.copy2(app, target)
    else:
        target = out / f"{stem}-Linux.tar.gz"
        with tarfile.open(target, "w:gz") as archive:
            archive.add(app, arcname=app.name)
    print(f"Erstellt: {target.relative_to(ROOT)} ({target.stat().st_size / 1e6:.1f} MB)")
    return target


if __name__ == "__main__":
    main()
