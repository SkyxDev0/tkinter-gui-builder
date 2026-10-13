from conftest import type_into
from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui.properties import ERROR_BORDER, PropertiesPanel


def test_properties_widget_fields(root):
    session = Session()
    panel = PropertiesPanel(root, session)
    panel.pack()
    button = AddWidget("window", "CTkButton")
    session.execute(button)
    session.select(button.node_id)
    assert panel.fields["name"].get() == "button_1"
    assert panel.fields["text"].get() == "Button"
    assert panel.fields["state"].get() == "normal"
    assert "sticky_n" in panel.fields

    type_into(panel.fields["text"], "Speichern")
    assert session.project.find(button.node_id).props["text"] == "Speichern"


def test_properties_invalid_value_marks_field(root):
    session = Session()
    messages = []
    session.on_status = messages.append
    panel = PropertiesPanel(root, session)
    panel.pack()
    button = AddWidget("window", "CTkButton")
    session.execute(button)
    session.select(button.node_id)
    entry = panel.fields["width"]
    type_into(entry, "breit")
    assert entry.cget("border_color") == ERROR_BORDER
    assert messages
    assert "width" not in session.project.find(button.node_id).props


def test_properties_layout_and_sticky(root):
    session = Session()
    panel = PropertiesPanel(root, session)
    panel.pack()
    label = AddWidget("window", "CTkLabel")
    session.execute(label)
    session.select(label.node_id)
    type_into(panel.fields["padx"], "6")
    panel.fields["sticky_e"].toggle()
    layout = session.project.find(label.node_id).layout
    assert layout.padx == 6
    assert layout.sticky == "e"


def test_properties_window_and_line(root):
    session = Session()
    panel = PropertiesPanel(root, session)
    panel.pack()
    assert panel.fields["title"].get() == "App"
    panel.fields["appearance_mode"].set("dark")
    panel.fields["appearance_mode"]._command("dark")  # Auswahl wie per Maus
    assert session.project.window.appearance_mode == "dark"

    session.select_line("window", "column", 0)
    type_into(panel.fields["weight"], "2")
    assert session.project.window.grid.columns[0].weight == 2
