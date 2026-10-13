import os
import sys
from pathlib import Path

from conftest import build_kontakt, requires_display
from ctk_builder.codegen import HEADER, generate
from ctk_builder.model import Project

SNAPSHOTS = Path(__file__).parent / "snapshots"


def check_snapshot(name: str, actual: str) -> None:
    """Vergleicht mit tests/snapshots/<name>; UPDATE_SNAPSHOTS=1 schreibt neu."""
    path = SNAPSHOTS / name
    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.write_text(actual, encoding="utf-8")
    assert actual == path.read_text(encoding="utf-8")


def test_ui_snapshot(kontakt):
    check_snapshot("kontakt_ui.py.txt", generate(kontakt, "kontakt").ui_source)


def test_logic_snapshot(kontakt):
    check_snapshot("kontakt.py.txt", generate(kontakt, "kontakt").logic_source)


def test_empty_project():
    files = generate(Project(), "leer")
    assert files.ui_source.startswith(HEADER + "\n")
    assert "class AppUI(ctk.CTk):" in files.ui_source
    assert "    pass" in files.logic_source
    compile(files.ui_source, "leer_ui.py", "exec")
    compile(files.logic_source, "leer.py", "exec")


def test_generated_code_compiles(kontakt):
    files = generate(kontakt, "kontakt")
    compile(files.ui_source, "kontakt_ui.py", "exec")
    compile(files.logic_source, "kontakt.py", "exec")


def test_deterministic():
    assert generate(build_kontakt(), "kontakt") == generate(build_kontakt(), "kontakt")


@requires_display
def test_generated_ui_runs(tmp_path, kontakt, monkeypatch):
    """Instanziiert das generierte Fenster wirklich."""
    files = generate(kontakt, "kontakt")
    (tmp_path / "kontakt_ui.py").write_text(files.ui_source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("kontakt_ui", None)
    import kontakt_ui

    app = kontakt_ui.KontaktUI()
    try:
        app.update()
        assert app.entry_name.cget("placeholder_text") == "Max Muster"
        assert app.button_save.grid_info()["column"] == 1
    finally:
        app.destroy()
