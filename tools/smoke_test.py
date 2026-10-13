"""Prüft die gebaute App, bevor sie veröffentlicht wird.

1. --version liefert die Versionsnummer.
2. --run-script startet ein Programm mit customtkinter-Fenster und gibt seine
   Ausgabe weiter (so arbeitet „▶ Ausführen“ in der App, ohne installiertes Python).
3. Die Oberfläche startet und läuft nach einigen Sekunden noch.

Aufruf:  python tools/smoke_test.py   (Linux ohne Display: xvfb-run -a …)
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ctk_builder import __version__  # noqa: E402
from app_paths import app_path  # noqa: E402

PROGRAM = """\
import customtkinter as ctk

app = ctk.CTk()
ctk.CTkLabel(app, text="Test").pack()
app.after(500, app.destroy)
app.mainloop()
print("Grüße aus der App", ctk.__version__)
"""


def run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0:
        raise SystemExit(f"Fehlgeschlagen ({result.returncode}): {args}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def main() -> None:
    app = app_path()
    print(f"App: {app}")
    if not app.exists():
        raise SystemExit("App nicht gefunden – erst tools/build.py ausführen")

    output = run([str(app), "--version"])
    assert __version__ in output, f"Version fehlt in Ausgabe: {output!r}"
    print(f"1. Version ok: {output.strip()}")

    with tempfile.TemporaryDirectory() as folder:
        script = Path(folder) / "programm.py"
        script.write_text(PROGRAM, encoding="utf-8")
        output = run([str(app), "--run-script", script.name], cwd=Path(folder))
    assert "Grüße aus der App" in output, f"Programmausgabe fehlt: {output!r}"
    print(f"2. Programm gestartet ok: {output.strip()}")

    with tempfile.TemporaryDirectory() as home:
        process = subprocess.Popen([str(app)], cwd=home)
        time.sleep(10)
        alive = process.poll() is None
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    assert alive, f"Oberfläche hat sich beendet (Code {process.returncode})"
    print("3. Oberfläche startet ok")
    print("Alle Prüfungen bestanden.")


if __name__ == "__main__":
    main()
