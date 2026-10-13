"""Widget-Palette: Kacheln mit Vorschau, Suche, Klick fügt ein."""

from __future__ import annotations

import tkinter
from typing import Callable

import customtkinter as ctk

from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui import theme
from ctk_builder.ui.icons import draw_preview
from ctk_builder.ui.widgets import add_bindtag, all_parts, pointer_inside
from ctk_builder.widget_specs import SPECS

PREVIEW_W, PREVIEW_H = 72, 44


def tile_label(widget_type: str) -> str:
    return widget_type.removeprefix("CTk")


class PaletteTile(ctk.CTkFrame):
    """Kachel für einen Widget-Typ. Loslassen über der Kachel ruft command auf."""

    def __init__(self, master, widget_type: str, command: Callable[[], None]):
        super().__init__(master, fg_color=theme.CARD, corner_radius=10, border_width=1,
                         border_color=theme.BORDER)
        self.widget_type = widget_type
        self.command = command
        self.preview = tkinter.Canvas(self, width=PREVIEW_W, height=PREVIEW_H,
                                      bg=theme.pick(theme.CARD), highlightthickness=0, bd=0)
        self.preview.pack(padx=10, pady=(10, 2))
        draw_preview(self.preview, widget_type, PREVIEW_W / 2, PREVIEW_H / 2)
        self.label = ctk.CTkLabel(self, text=tile_label(widget_type), height=18,
                                  text_color=theme.TEXT, font=theme.font(12))
        self.label.pack(pady=(0, 8))

        tag = f"palette-tile-{widget_type}"
        add_bindtag(self, tag)
        self.bind_class(tag, "<Enter>", lambda e: self._hover(True))
        self.bind_class(tag, "<Leave>", self._leave)
        self.bind_class(tag, "<ButtonRelease-1>",
                        lambda e: self.command() if pointer_inside(self, e) else None)

    def _hover(self, on: bool) -> None:
        self.configure(border_color=theme.ACCENT if on else theme.BORDER)

    def _leave(self, event: tkinter.Event) -> None:
        under = self.winfo_containing(event.x_root, event.y_root)
        if under not in all_parts(self):
            self._hover(False)


class Palette(ctk.CTkFrame):
    def __init__(self, master, session: Session):
        super().__init__(master, fg_color="transparent")
        self.session = session
        ctk.CTkLabel(self, text="Widgets", font=theme.font(15, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x", padx=14, pady=(14, 0))
        ctk.CTkLabel(self, text="Klicken oder auf die Fläche ziehen", font=theme.font(12),
                     text_color=theme.MUTED, anchor="w").pack(fill="x", padx=14)
        self.search = ctk.CTkEntry(self, placeholder_text="Suchen …", height=34,
                                   corner_radius=8, border_width=1,
                                   border_color=theme.BORDER, fg_color=theme.INPUT,
                                   text_color=theme.TEXT, font=theme.font(13))
        self.search.pack(fill="x", padx=12, pady=(10, 10))
        self.search.bind("<KeyRelease>", lambda e: self.filter(self.search.get()))

        self.tiles = ctk.CTkFrame(self, fg_color="transparent")
        self.tiles.pack(fill="x", padx=8)
        self.tiles.grid_columnconfigure((0, 1), weight=1, uniform="tile")
        self.buttons: dict[str, PaletteTile] = {}
        for widget_type in SPECS:
            self.buttons[widget_type] = PaletteTile(
                self.tiles, widget_type, lambda t=widget_type: self.add(t))
        self.filter("")

    def filter(self, text: str) -> list[str]:
        """Zeigt nur Kacheln, deren Name text enthält; liefert die sichtbaren Typen."""
        needle = text.strip().lower()
        visible = [t for t in SPECS if needle in tile_label(t).lower()]
        for tile in self.buttons.values():
            tile.grid_forget()
        for i, widget_type in enumerate(visible):
            self.buttons[widget_type].grid(row=i // 2, column=i % 2, sticky="ew",
                                           padx=4, pady=4)
        return visible

    def add(self, widget_type: str) -> None:
        """Fügt in die nächste freie Zelle des Ziel-Containers ein und wählt aus."""
        command = AddWidget(self.session.target_container_id(), widget_type)
        if self.session.execute(command):
            self.session.select(command.node_id)
