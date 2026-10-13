import os
import sys

import pytest

from ctk_builder.commands import (
    AddWidget, CommandStack, InsertLine, RenameWidget, SetLayout, SetLineConfig,
    SetProperty, SetWindowProperty,
)
from ctk_builder.model import Project


def build_kontakt() -> Project:
    """Beispielprojekt: Formular mit Name, E-Mail, Newsletter-Auswahl und Buttons."""
    stack = CommandStack(Project())

    def add(widget_type, parent="window", row=None, column=None, name=None, **props):
        cmd = AddWidget(parent, widget_type, row, column)
        stack.execute(cmd)
        if name:
            stack.execute(RenameWidget(cmd.node_id, name))
        for key, value in props.items():
            stack.execute(SetProperty(cmd.node_id, key, value))
        return cmd.node_id

    stack.execute(SetWindowProperty("class_name", "Kontakt"))
    stack.execute(SetWindowProperty("title", "Kontakt"))
    stack.execute(SetWindowProperty("width", 420))
    stack.execute(SetWindowProperty("height", 260))
    stack.execute(SetWindowProperty("resizable", False))
    stack.execute(SetWindowProperty("appearance_mode", "dark"))

    name_label = add("CTkLabel", row=0, column=0, name="label_name", text="Name:")
    stack.execute(SetLayout(name_label, sticky="w", padx=8, pady=4))
    entry = add("CTkEntry", row=0, column=1, name="entry_name", placeholder_text="Max Muster")
    stack.execute(SetLayout(entry, sticky="ew", padx=8, pady=4))
    add("CTkLabel", row=1, column=0, name="label_mail", text="E-Mail:")
    add("CTkEntry", row=1, column=1, name="entry_mail")
    stack.execute(SetLineConfig("window", "column", 1, 1, 0, ""))

    add("CTkRadioButton", row=2, column=0, name="radio_ja", text="Newsletter",
        variable_group="newsletter", value="ja")
    add("CTkRadioButton", row=2, column=1, name="radio_nein", text="Kein Newsletter",
        variable_group="newsletter", value="nein")

    buttons = add("CTkFrame", row=3, column=0, name="frame_buttons", fg_color="transparent")
    stack.execute(SetLayout(buttons, columnspan=2, sticky="e"))
    stack.execute(InsertLine(buttons, "column", 1))
    add("CTkButton", parent=buttons, row=0, column=0, name="button_cancel",
        text="Abbrechen", command="on_cancel", fg_color="#555555")
    save = add("CTkButton", parent=buttons, row=0, column=1, name="button_save",
               text="Speichern", command="on_save", font_size=14)
    stack.execute(SetLayout(save, padx=4))
    return stack.project


@pytest.fixture
def kontakt() -> Project:
    return build_kontakt()


def has_display() -> bool:
    """Ohne Fenster-Test: unter Linux ohne DISPLAY gibt es keins.

    Achtung: Nicht mit tkinter.Tk() testen – ein zerstörtes tk.Tk gefolgt von
    ctk.CTk bringt Tk auf macOS zum Absturz.
    """
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


requires_display = pytest.mark.skipif(not has_display(), reason="kein Display verfügbar")


@pytest.fixture
def root():
    """Ein CTk-Hauptfenster für Panel-Tests."""
    if not has_display():
        pytest.skip("kein Display verfügbar")
    import customtkinter as ctk

    window = ctk.CTk()
    yield window
    window.destroy()


@pytest.fixture
def app(tmp_path):
    """Komplettes Builder-Fenster mit dem Kontakt-Beispielprojekt."""
    if not has_display():
        pytest.skip("kein Display verfügbar")
    from ctk_builder.session import Session
    from ctk_builder.settings import Settings
    from ctk_builder.ui.main_window import MainWindow

    session = Session()
    session.replace_project(build_kontakt(), None)
    window = MainWindow(session, Settings(tmp_path / "settings.json"))
    window.update()
    yield window
    window.runner.stop()
    window.destroy()


@pytest.fixture
def canvas(root):
    """Arbeitsfläche allein, mit dem Kontakt-Beispielprojekt."""
    from ctk_builder.session import Session
    from ctk_builder.ui.canvas import DesignCanvas

    session = Session()
    session.replace_project(build_kontakt(), None)
    root.geometry("800x600")
    design = DesignCanvas(root, session)
    design.pack(fill="both", expand=True)
    root.update()
    return design


def node_named(session, name):
    return next(w for w in session.project.iter_widgets() if w.name == name)


def click(widget, x=3, y=3):
    """Simuliert einen Mausklick (Enter, Drücken, Loslassen) auf ein Tk-Widget."""
    root_x, root_y = widget.winfo_rootx() + x, widget.winfo_rooty() + y
    widget.event_generate("<Enter>", x=x, y=y)
    widget.event_generate("<Button-1>", x=x, y=y, rootx=root_x, rooty=root_y)
    widget.event_generate("<ButtonRelease-1>", x=x, y=y, rootx=root_x, rooty=root_y)
    widget.update()


def type_into(entry, text):
    """Ersetzt den Inhalt eines CTkEntry und bestätigt mit Enter.

    CTkEntry leitet bind() an das innere tkinter.Entry (_entry) weiter, und
    Tastaturereignisse gehen an das Widget mit Fokus – daher erst fokussieren.
    """
    entry.delete(0, "end")
    entry.insert(0, text)
    entry._entry.focus_force()
    entry.update()
    entry._entry.event_generate("<Return>")
    entry.update()
