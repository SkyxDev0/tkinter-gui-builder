"""Widget-Palette: ein Knopf pro Widget-Typ."""

from __future__ import annotations

import customtkinter as ctk

from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.widget_specs import SPECS


class Palette(ctk.CTkFrame):
    def __init__(self, master, session: Session):
        super().__init__(master)
        self.session = session
        ctk.CTkLabel(self, text="Widgets", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4))
        self.buttons: dict[str, ctk.CTkButton] = {}
        for widget_type in SPECS:
            button = ctk.CTkButton(
                self, text=widget_type.removeprefix("CTk"), height=26, anchor="w",
                command=lambda t=widget_type: self.add(t),
            )
            button.pack(fill="x", padx=8, pady=2)
            self.buttons[widget_type] = button

    def add(self, widget_type: str) -> None:
        """Fügt in die nächste freie Zelle des Ziel-Containers ein und wählt aus."""
        command = AddWidget(self.session.target_container_id(), widget_type)
        if self.session.execute(command):
            self.session.select(command.node_id)
