import tkinter

import customtkinter as ctk
import pytest

from conftest import click
from ctk_builder.ui.icons import ICONS, draw_icon, draw_preview
from ctk_builder.ui.widgets import (
    IconButton, RailItem, ToggleChip, Tooltip, add_bindtag, all_parts,
)
from ctk_builder.widget_specs import SPECS


def test_icons_and_previews_draw(root):
    canvas = tkinter.Canvas(root, width=80, height=50)
    for name in ICONS:
        draw_icon(canvas, name, 20, 20, 20, "#000000", "#ffffff")
    for widget_type in SPECS:
        draw_preview(canvas, widget_type, 40, 25)
    assert canvas.find_all()
    with pytest.raises(ValueError):
        draw_icon(canvas, "gibtsnicht", 0, 0, 20, "#000000", "#ffffff")


def test_icon_button_and_rail_item_click(root):
    calls = []
    button = IconButton(root, "undo", lambda: calls.append("icon"))
    item = RailItem(root, "tree", "Struktur", lambda: calls.append("rail"))
    button.pack()
    item.pack()
    root.update()
    click(button)
    click(item)
    assert calls == ["icon", "rail"]
    button.set_active(True)
    item.set_active(True)
    assert button.active and item.active


def test_toggle_chip(root):
    values = []
    chip = ToggleChip(root, "N", False, values.append)
    chip.toggle()
    chip.toggle()
    assert values == [True, False]
    assert not chip.get()


def test_add_bindtag_reaches_hidden_ctk_parts(root):
    frame = ctk.CTkFrame(root)
    ctk.CTkLabel(frame, text="x").pack()
    add_bindtag(frame, "mein-tag")
    hidden = frame._canvas  # von CTkFrame.winfo_children() verborgen
    assert hidden in all_parts(frame)
    assert all(part.bindtags()[0] == "mein-tag" for part in all_parts(frame))


def test_tooltip_show_and_hide(root):
    button = IconButton(root, "copy", lambda: None)
    button.pack()
    root.update()
    tip = Tooltip(button, "Duplizieren")
    tip._show()
    assert tip._tip is not None and tip._tip.winfo_exists()
    tip._hide()
    assert tip._tip is None
