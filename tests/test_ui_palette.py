from conftest import click
from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui.palette import Palette
from ctk_builder.widget_specs import SPECS


def test_palette_click_adds_and_selects(root):
    session = Session()
    palette = Palette(root, session)
    palette.pack()
    root.update()
    assert set(palette.buttons) == set(SPECS)
    click(palette.buttons["CTkButton"].winfo_children()[0])
    widgets = list(session.project.iter_widgets())
    assert [w.name for w in widgets] == ["button_1"]
    assert session.selected_id == widgets[0].id


def test_palette_adds_into_selected_frame(root):
    session = Session()
    palette = Palette(root, session)
    frame = AddWidget("window", "CTkFrame")
    session.execute(frame)
    session.select(frame.node_id)
    palette.add("CTkLabel")
    assert session.project.find(frame.node_id).children[0].name == "label_1"
