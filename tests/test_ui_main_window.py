"""Hauptfenster: Titel, Löschen/Duplizieren, Speichern, Export, Ausführen."""

import time

from conftest import click, node_named
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


def test_arrow_keys_move_selected_widget(app):
    session = app.session
    switch = AddWidget("window", "CTkSwitch", 4, 0)
    session.execute(switch)
    session.select(switch.node_id)
    app.nudge(0, 1)
    assert session.project.find(switch.node_id).layout.column == 1
    app.nudge(0, -5)  # außerhalb: nichts passiert
    assert session.project.find(switch.node_id).layout.column == 1


def test_overlay_and_drag_are_wired(app):
    assert app.grid_overlay.canvas is app.canvas
    assert app.canvas.on_press == app.drag.press_on_canvas


def test_keys_reach_canvas_after_click(app):
    """Nach einem Klick hat die Arbeitsfläche den Fokus; Pfeiltasten und Entf wirken dort."""
    session = app.session
    switch = AddWidget("window", "CTkSwitch", 4, 0)
    session.execute(switch)
    app.update()
    app.focus_force()
    click(app.canvas.views[switch.node_id].winfo_children()[0])
    assert app.focus_get() is app.canvas
    app.canvas.event_generate("<Right>")
    assert session.project.find(switch.node_id).layout.column == 1
    app.canvas.event_generate("<Delete>")
    assert session.project.find(switch.node_id) is None
