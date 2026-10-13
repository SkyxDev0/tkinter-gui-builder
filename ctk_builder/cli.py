"""Startpunkt: `ctk-builder`, `python -m ctk_builder` und die gebaute App."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path
from typing import Optional

from ctk_builder import __version__

RUN_SCRIPT_FLAG = "--run-script"


def run_script(path: str) -> None:
    """Führt ein exportiertes Programm aus, als wäre es mit `python <path>` gestartet.

    Die gebaute App (PyInstaller) ist kein Python-Interpreter. Damit „▶ Ausführen“
    auch ohne installiertes Python funktioniert, startet sie sich selbst mit
    --run-script; customtkinter ist in der App enthalten.
    """
    script = Path(path).resolve()
    sys.argv = [str(script)]
    sys.path.insert(0, str(script.parent))
    # Der Runner liest UTF-8 zeilenweise; die gebaute App ignoriert
    # PYTHONIOENCODING und schriebe unter Windows sonst in der Codepage.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", line_buffering=True)
    runpy.run_path(str(script), run_name="__main__")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ctk-builder",
        description="Drag & Drop GUI-Builder für CustomTkinter")
    parser.add_argument("--version", action="version", version=f"CTk Builder {__version__}")
    parser.add_argument(RUN_SCRIPT_FLAG, metavar="SKRIPT", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.run_script:
        run_script(args.run_script)
        return

    from ctk_builder.ui.main_window import main as run_builder

    run_builder()
