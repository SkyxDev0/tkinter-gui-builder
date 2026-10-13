"""Prüft die gebaute App, bevor sie veröffentlicht wird.

1. --version liefert die Versionsnummer.
2. --run-script startet ein Programm mit customtkinter-Fenster und gibt seine
   Ausgabe weiter (so arbeitet „▶ Ausführen“ in der App, ohne installiertes Python).
3. Die Oberfläche startet und läuft nach einigen Sekunden noch.
4. Öffnen-, Speichern- und Interpreter-Dialog öffnen sich, ohne dass die App
   abstürzt – über genau den Code hinter Menü und Knöpfen (MainWindow-Methoden).
   Hintergrund: Tk 8.6.13–8.6.16 stürzt unter macOS ab, wenn ein Dateityp eine
   Endung mit Punkt hat (Tk-Ticket 080a28104e).
5. Gegenproben: Ein absichtlicher Absturz und ein absichtlicher Fehler
   (TclError) im Dialogaufruf müssen erkannt werden – sonst wäre Schritt 4
   auf diesem System wertlos.

Aufruf:  python tools/smoke_test.py   (Linux ohne Display: xvfb-run -a …)
"""

from __future__ import annotations

import plistlib
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ctk_builder import __version__  # noqa: E402
from app_paths import app_path  # noqa: E402
from build import bundle_version  # noqa: E402

PROGRAM = """\
import customtkinter as ctk

app = ctk.CTk()
ctk.CTkLabel(app, text="Test").pack()
app.after(500, app.destroy)
app.mainloop()
print("Grüße aus der App", ctk.__version__)
"""


# Läuft in der gebauten App (--run-script). Ein modaler Dialog blockiert die
# Tk-Ereignisschleife; ein Wächter-Thread meldet „offen“ und beendet die App.
# _tkinter gibt den GIL während Tcl-Aufrufen frei, also läuft der Wächter weiter.
# Er darf Tk nie anfassen. Statusmeldungen gehen in eine Datei, nicht nach stdout.
# Eine Ausnahme im Dialogaufruf beendet die App sofort mit „error“ – sonst liefe
# die Ereignisschleife weiter und der Wächter meldete einen Dialog, den es nie gab.
DIALOG_PROGRAM = """\
import os, threading, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIND = Path(__file__).stem.split("_", 1)[1]   # dialog_save.py -> "save"
HOLD = 4.0                                    # so lange muss der Dialog offen bleiben


def mark(text):
    with open(HERE / "status.txt", "a", encoding="utf-8") as fh:
        fh.write(text + "\\n")
        fh.flush()
        os.fsync(fh.fileno())


from ctk_builder.settings import Settings
from ctk_builder.ui.main_window import MainWindow


def fail(exc, value, tb):
    text = "".join(traceback.format_exception(exc, value, tb))
    mark("error " + KIND + " " + text.replace("\\n", " | "))
    os._exit(2)


win = MainWindow(settings=Settings(HERE / "settings.json"))
win.report_callback_exception = fail
mark("tk " + str(win.tk.call("info", "patchlevel")))


def watchdog():
    time.sleep(HOLD)
    mark("open " + KIND)
    os._exit(0)


def open_dialog():
    mark("calling " + KIND)
    threading.Thread(target=watchdog, daemon=True).start()
    action = {"save": win.save_as, "open": win.open_project,
              "interpreter": win.choose_interpreter}[KIND]
    try:
        result = action()
    except BaseException as exc:
        fail(type(exc), exc, exc.__traceback__)
    mark(f"returned {KIND} {result!r}")
    win.destroy()


win.after(1000, open_dialog)
win.mainloop()
"""

DIALOGS = ("save", "open", "interpreter")
DIALOG_TIMEOUT = 120  # Start der App (Entpacken, erster Start unter macOS) + HOLD


def run(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0:
        raise SystemExit(f"Fehlgeschlagen ({result.returncode}): {args}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def stop(process: subprocess.Popen) -> None:
    """Beendet die App samt Kindprozessen.

    Die Ein-Datei-App startet unter Windows einen zweiten Prozess; terminate()
    träfe nur den Starter, die eigentliche App liefe weiter.
    """
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def describe(code: int | None) -> str:
    if code is None:
        return "läuft noch"
    if code < 0:  # POSIX: durch Signal beendet (SIGABRT = Absturz)
        try:
            return f"durch {signal.Signals(-code).name} beendet"
        except ValueError:
            return f"durch Signal {-code} beendet"
    return f"Exit-Code {code} (0x{code & 0xFFFFFFFF:08X})"


# Gegenproben: ersetzen den Dialogaufruf durch einen absichtlichen Fehler
CALL = "        result = action()"
PROBES = {
    # SIGABRT wie beim echten macOS-Absturz; unter Windows hartes Beenden mit
    # Code 3, weil abort() dort die Fehlerberichterstattung öffnen und hängen kann
    "Absturz": "os._exit(3)" if sys.platform == "win32" else "os.abort()",
    "Fehler": "raise __import__('tkinter').TclError('Gegenprobe')",
}


def check_dialog(app: Path, kind: str, probe: str | None = None) -> str:
    """Öffnet einen Dialog in der App; nur ein offener Dialog ist ok.

    probe: Name aus PROBES – baut statt des Dialogs einen absichtlichen Fehler ein.
    """
    program = DIALOG_PROGRAM
    if probe:
        assert CALL in program
        program = program.replace(CALL, f"        {PROBES[probe]}")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        script = folder / f"dialog_{kind}.py"
        script.write_text(program, encoding="utf-8")
        started = time.monotonic()
        process = subprocess.Popen([str(app), "--run-script", script.name], cwd=folder,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            out, _ = process.communicate(timeout=DIALOG_TIMEOUT)
            hung = False
        except subprocess.TimeoutExpired:
            hung = True
            stop(process)
            out, _ = process.communicate()
        elapsed = time.monotonic() - started
        status_file = folder / "status.txt"
        lines = status_file.read_text(encoding="utf-8").splitlines() if status_file.exists() else []
    tk = next((line[3:] for line in lines if line.startswith("tk ")), "?")
    error = next((line for line in lines if line.startswith("error ")), None)
    if not error and f"open {kind}" in lines and process.returncode == 0:
        return f"{kind}-Dialog bleibt offen ({elapsed:.0f} s, Tk {tk}) ok"
    if error:  # letzte Zeile des Tracebacks, z. B. „_tkinter.TclError: …“
        last = [part for part in error.split(" | ") if part.strip()][-1]
        reason = f"Fehler im Dialogaufruf: {last.strip()}"
    elif hung:
        # der Wächter läuft, solange die App lebt – ohne „open“ hängt sie fest
        reason = f"App hängt (nach {DIALOG_TIMEOUT} s beendet, Wächter lief nicht)"
    elif any(line.startswith(f"returned {kind}") for line in lines):
        reason = "Dialog hat sich von selbst geschlossen, war nie wirklich offen"
    elif f"calling {kind}" in lines:
        reason = f"App ist im Dialog abgestürzt: {describe(process.returncode)}"
    else:
        reason = f"App hat den Dialog nie erreicht: {describe(process.returncode)}"
    raise SystemExit(f"{kind}: {reason} (Tk {tk})\nStatus: {lines}\n"
                     f"Ausgabe:\n{out.decode('utf-8', 'replace')}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # lesbares Log auch unter Windows
    app = app_path()
    print(f"App: {app}")
    if not app.exists():
        raise SystemExit("App nicht gefunden – erst tools/build.py ausführen")

    output = run([str(app), "--version"])
    assert __version__ in output, f"Version fehlt in Ausgabe: {output!r}"
    if sys.platform == "darwin":
        bundle = app.parents[2]
        info = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
        for key in ("CFBundleShortVersionString", "CFBundleVersion"):
            assert info.get(key) == bundle_version(__version__), f"{key} = {info.get(key)!r}"
        run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)])
        output += " (Info.plist und Signatur ok)"
    print(f"1. Version ok: {output.strip()}")

    with tempfile.TemporaryDirectory() as folder:
        script = Path(folder) / "programm.py"
        script.write_text(PROGRAM, encoding="utf-8")
        output = run([str(app), "--run-script", script.name], cwd=Path(folder))
    assert "Grüße aus der App" in output, f"Programmausgabe fehlt: {output!r}"
    print(f"2. Programm gestartet ok: {output.strip()}")

    process = subprocess.Popen([str(app)], cwd=app.parent)
    time.sleep(10)
    alive = process.poll() is None
    stop(process)
    assert alive, f"Oberfläche hat sich beendet (Code {process.returncode})"
    print("3. Oberfläche startet ok")

    for kind in DIALOGS:
        print(f"4. {check_dialog(app, kind)}")

    for probe in PROBES:
        try:
            check_dialog(app, "save", probe=probe)
        except SystemExit as detected:
            print(f"5. Gegenprobe ok, {probe} erkannt: {str(detected).splitlines()[0]}")
        else:
            raise SystemExit(f"Gegenprobe: absichtlicher {probe} wurde NICHT erkannt")
    print("Alle Prüfungen bestanden.")


if __name__ == "__main__":
    main()
