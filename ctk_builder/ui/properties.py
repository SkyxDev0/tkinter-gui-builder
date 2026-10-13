"""Eigenschaften-Panel für Widget, Fenster oder Zeile/Spalte."""

from __future__ import annotations

import tkinter
from typing import Any, Callable, Optional

import customtkinter as ctk

from ctk_builder.commands import (
    Command, RenameWidget, SetLayout, SetLineConfig, SetProperty, SetWindowProperty,
)
from ctk_builder.model import WidgetNode, WindowNode
from ctk_builder.session import Session
from ctk_builder.widget_specs import CHOICE, SPECS, format_value, parse_value

ERROR_BORDER = "#d9534f"


class PropertiesPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, session: Session):
        super().__init__(master, label_text="Eigenschaften")
        self.session = session
        self.grid_columnconfigure(1, weight=1)
        self.fields: dict[str, ctk.CTkBaseClass] = {}  # für Tests: Feldname -> Widget
        self._rebuilding = False
        self._row = 0
        session.subscribe(self.rebuild)
        session.subscribe_selection(self.rebuild)
        self.rebuild()

    # ------------------------------------------------------------ Aufbau

    def rebuild(self) -> None:
        self._rebuilding = True
        try:
            for child in self.winfo_children():
                child.destroy()
            self.fields.clear()
            self._row = 0
            session = self.session
            node = session.project.find(session.selected_id)
            if session.selected_line is not None:
                self._build_line(*session.selected_line)
            elif isinstance(node, WindowNode):
                self._build_window(node)
            elif isinstance(node, WidgetNode):
                self._build_widget(node)
        finally:
            self._rebuilding = False

    def _heading(self, text: str) -> None:
        ctk.CTkLabel(self, text=text, font=ctk.CTkFont(weight="bold")).grid(
            row=self._row, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self._row += 1

    def _field_label(self, text: str) -> None:
        ctk.CTkLabel(self, text=text, anchor="w").grid(
            row=self._row, column=0, sticky="w", padx=(0, 8), pady=2)

    def _entry(self, key: str, label: str, value: str,
               commit: Callable[[str], Optional[Command]]) -> ctk.CTkEntry:
        """Eingabefeld; commit wandelt Text in Befehl (ValueError = ungültig)."""
        self._field_label(label)
        entry = ctk.CTkEntry(self)
        entry.insert(0, value)
        entry.grid(row=self._row, column=1, sticky="ew", pady=2)
        default_border = entry.cget("border_color")

        def on_commit(_event=None) -> None:
            if self._rebuilding or not entry.winfo_exists():
                return
            text = entry.get()
            if text == value:
                entry.configure(border_color=default_border)
                return
            try:
                command = commit(text)
            except ValueError as exc:
                entry.configure(border_color=ERROR_BORDER)
                self.session.on_status(str(exc))
                return
            if command is not None and not self.session.execute(command):
                entry.configure(border_color=ERROR_BORDER)

        entry.bind("<Return>", on_commit)
        entry.bind("<FocusOut>", on_commit)
        self.fields[key] = entry
        self._row += 1
        return entry

    def _choice(self, key: str, label: str, value: str, choices: tuple[str, ...],
                make: Callable[[str], Command]) -> ctk.CTkOptionMenu:
        self._field_label(label)
        menu = ctk.CTkOptionMenu(
            self, values=list(choices),
            command=lambda chosen: self.session.execute(make(chosen)),
        )
        menu.set(value)
        menu.grid(row=self._row, column=1, sticky="ew", pady=2)
        self.fields[key] = menu
        self._row += 1
        return menu

    def _check(self, key: str, label: str, value: bool,
               make: Callable[[bool], Command]) -> ctk.CTkCheckBox:
        variable = tkinter.BooleanVar(self, value=value)
        box = ctk.CTkCheckBox(
            self, text=label, variable=variable,
            command=lambda: self.session.execute(make(variable.get())),
        )
        box.grid(row=self._row, column=0, columnspan=2, sticky="w", pady=2)
        self.fields[key] = box
        self._row += 1
        return box

    # ------------------------------------------------------------ Widget

    def _build_widget(self, node: WidgetNode) -> None:
        spec = SPECS[node.type]
        self._heading(node.type)
        self._entry("name", "name", node.name, lambda text: RenameWidget(node.id, text))
        for prop in spec.props:
            value = node.props.get(prop.name, prop.default)
            if prop.kind == CHOICE:
                self._choice(prop.name, prop.name, value, prop.choices,
                             lambda chosen, p=prop: SetProperty(node.id, p.name, chosen))
            else:
                self._entry(prop.name, prop.name, format_value(value),
                            lambda text, p=prop: SetProperty(
                                node.id, p.name, parse_value(p, text, self._color_ok)))
        self._build_layout(node)

    def _color_ok(self, name: str) -> bool:
        try:
            self.winfo_rgb(name)
        except tkinter.TclError:
            return False
        return True

    def _build_layout(self, node: WidgetNode) -> None:
        self._heading("Layout")
        layout = node.layout
        for key in ("row", "column", "rowspan", "columnspan", "padx", "pady"):
            self._entry(key, key, str(getattr(layout, key)),
                        lambda text, k=key: SetLayout(node.id, **{k: _int(k, text)}))
        self._field_label("sticky")
        boxes = ctk.CTkFrame(self, fg_color="transparent")
        boxes.grid(row=self._row, column=1, sticky="w", pady=2)
        for i, side in enumerate("nsew"):
            variable = tkinter.BooleanVar(self, value=side in layout.sticky)

            def toggle(side=side, variable=variable) -> None:
                sticky = layout.sticky.replace(side, "")
                if variable.get():
                    sticky += side
                self.session.execute(SetLayout(node.id, sticky=sticky))

            box = ctk.CTkCheckBox(boxes, text=side.upper(), width=48,
                                  variable=variable, command=toggle)
            box.grid(row=0, column=i)
            self.fields[f"sticky_{side}"] = box
        self._row += 1

    # ------------------------------------------------------------ Fenster

    def _build_window(self, window: WindowNode) -> None:
        self._heading("Fenster")
        self._entry("class_name", "Klassenname", window.class_name,
                    lambda text: SetWindowProperty("class_name", text.strip()))
        self._entry("title", "Titel", window.title,
                    lambda text: SetWindowProperty("title", text))
        for key, label in (("width", "Breite"), ("height", "Höhe")):
            self._entry(key, label, str(getattr(window, key)),
                        lambda text, k=key: SetWindowProperty(k, _int(k, text)))
        self._check("resizable", "Größe veränderbar", window.resizable,
                    lambda value: SetWindowProperty("resizable", value))
        self._choice("appearance_mode", "Modus", window.appearance_mode,
                     ("system", "light", "dark"),
                     lambda value: SetWindowProperty("appearance_mode", value))
        self._choice("color_theme", "Farbthema", window.color_theme,
                     ("blue", "green", "dark-blue"),
                     lambda value: SetWindowProperty("color_theme", value))

    # ------------------------------------------------------------ Zeile/Spalte

    def _build_line(self, container_id: str, axis: str, index: int) -> None:
        container = self.session.project.find(container_id)
        config = container.grid.lines(axis)[index]
        owner = "Fenster" if container_id == "window" else container.name
        self._heading(f"{'Zeile' if axis == 'row' else 'Spalte'} {index} · {owner}")

        def make(**change: Any) -> SetLineConfig:
            values = {"weight": config.weight, "minsize": config.minsize,
                      "uniform": config.uniform, **change}
            return SetLineConfig(container_id, axis, index, **values)

        self._entry("weight", "weight", str(config.weight),
                    lambda text: make(weight=_int("weight", text)))
        self._entry("minsize", "minsize", str(config.minsize),
                    lambda text: make(minsize=_int("minsize", text)))
        self._entry("uniform", "uniform", config.uniform,
                    lambda text: make(uniform=text.strip()))


def _int(name: str, text: str) -> int:
    text = text.strip()
    if not text.isdigit():
        raise ValueError(f"{name}: ganze Zahl >= 0 erwartet")
    return int(text)
