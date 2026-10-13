"""Hauptfenster: Titel, Löschen/Duplizieren, Speichern, Export, Ausführen."""

import time

from conftest import node_named
from ctk_builder.commands import AddWidget


def test_title_shows_dirty_state(app):
    assert app.title() == "Unbenannt – CTk Builder"
    app.session.execute(AddWidget("window", "CTkLabel"))
    assert app.title() == "Unbenannt • – CTk Builder"


def test_delete_and_duplicate_selected(app):
    session = app.session
    label = node_named(session, "label_mail")
    session.select(label.id)
    app.duplicate_selected()
    assert session.project.find(session.selected_id).name == "label_1"
    app.delete_selected()
    assert session.selected_id == "window"
    app.delete_selected()  # Fenster kann nicht gelöscht werden
    assert session.project.window is not None


def test_save_export_and_run(app, tmp_path, monkeypatch):
    path = tmp_path / "kontakt.ctkb.json"
    app.session.path = path
    result = app.export()
    assert path.exists()
    assert result.ui_path.exists()
    assert result.logic_created
    assert app.title() == "kontakt.ctkb.json – CTk Builder"

    # Ausführen mit einem Skript, das sofort endet, statt der echten GUI
    result.logic_path.write_text("print('läuft')\n", encoding="utf-8")
    app.run()
    deadline = time.monotonic() + 10
    while "beendet" not in app.console.text.get("1.0", "end") and time.monotonic() < deadline:
        app.update()
        time.sleep(0.05)
    output = app.console.text.get("1.0", "end")
    assert "läuft" in output
    assert "Code 0" in output


def test_confirm_discard_without_changes(app):
    assert app.confirm_discard()
