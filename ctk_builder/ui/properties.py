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
from ctk_builder.ui import theme
from ctk_builder.ui.widgets import ToggleChip
from ctk_builder.widget_specs import CHOICE, SPECS, format_value, parse_value

ERROR_BORDER = "#ef4444"
SEGMENT_MAX = 3  # Auswahlen mit bis zu so vielen Werten als Segment-Knöpfe

TRACK = ("#e8eaee", "#26262b")         # Hintergrund von Segment-Knöpfen und Menüs
TRACK_HOVER = ("#dde0e5", "#2f2f34")
PILL = ("#ffffff", "#3f3f46")          # ausgewähltes Segment


class PropertiesPanel(ctk.CTkFrame):
    def __init__(self, master, session: Session, width: int = 268):
        super().__init__(master, fg_color=theme.CARD, corner_radius=theme.RADIUS,
                         border_width=1, border_color=theme.BORDER)
        self.session = session
        self.fields: dict[str, ctk.CTkBaseClass] = {}  # für Tests: Feldname -> Widget
        self.sections: dict[str, tuple[ctk.CTkButton, ctk.CTkFrame, str]] = {}
        self._collapsed: set[str] = set()  # bleibt über Neuaufbauten erhalten
        self._rebuilding = False
        self._parent: Optional[ctk.CTkFrame] = None
        self._row = 0

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 10))
        self.title_label = ctk.CTkLabel(head, text="", anchor="w", height=22,
                                        font=theme.font(16, "bold"), text_color=theme.TEXT)
        self.title_label.pack(fill="x")
        self.subtitle_label = ctk.CTkLabel(head, text="", anchor="w", height=18,
                                           font=theme.font(12), text_color=theme.MUTED)
        self.subtitle_label.pack(fill="x")
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=theme.BORDER).pack(fill="x", padx=1)
        self.body = ctk.CTkScrollableFrame(
            self, width=width, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme.BORDER, scrollbar_button_hover_color=theme.MUTED)
        self.body.pack(fill="both", expand=True, padx=(6, 4), pady=(6, 10))

        session.subscribe(self.rebuild)
        session.subscribe_selection(self.rebuild)
        self.rebuild()

    # ------------------------------------------------------------ Aufbau

    def rebuild(self) -> None:
        self._rebuilding = True
        try:
            for child in self.body.winfo_children():
                child.destroy()
            self.fields.clear()
            self.sections.clear()
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

    def _header(self, title: str, subtitle: str) -> None:
        self.title_label.configure(text=title)
        self.subtitle_label.configure(text=subtitle)

    def _section(self, key: str, title: str) -> None:
        """Aufklappbarer Abschnitt; folgende Felder landen darin."""
        container = ctk.CTkFrame(self.body, fg_color="transparent")
        container.pack(fill="x", pady=(0, 2))
        header = ctk.CTkButton(
            container, text="", anchor="w", height=30, corner_radius=8,
            fg_color="transparent", hover_color=theme.HOVER, text_color=theme.TEXT,
            font=theme.font(13, "bold"), command=lambda: self.toggle_section(key))
        header.pack(fill="x")
        body = ctk.CTkFrame(container, fg_color="transparent")
        body.grid_columnconfigure(1, weight=1)
        self.sections[key] = (header, body, title)
        self._show_section(key, key not in self._collapsed)
        self._parent, self._row = body, 0

    def toggle_section(self, key: str) -> None:
        expanded = key in self._collapsed
        if expanded:
            self._collapsed.discard(key)
        else:
            self._collapsed.add(key)
        self._show_section(key, expanded)

    def _show_section(self, key: str, expanded: bool) -> None:
        header, body, title = self.sections[key]
        header.configure(text=f"{'▾' if expanded else '▸'}   {title}")
        if expanded:
            body.pack(fill="x", padx=(10, 6), pady=(2, 10))
        else:
            body.pack_forget()

    def _field_label(self, text: str) -> None:
        ctk.CTkLabel(self._parent, text=text, anchor="w", height=30, font=theme.font(12),
                     text_color=theme.MUTED).grid(
            row=self._row, column=0, sticky="w", padx=(0, 10), pady=3)

    def _entry(self, key: str, label: str, value: str,
               commit: Callable[[str], Optional[Command]]) -> ctk.CTkEntry:
        """Eingabefeld; commit wandelt Text in Befehl (ValueError = ungültig)."""
        self._field_label(label)
        entry = ctk.CTkEntry(self._parent, height=30, corner_radius=8, border_width=1,
                             border_color=theme.BORDER, fg_color=theme.INPUT,
                             text_color=theme.TEXT, font=theme.font(13))
        entry.insert(0, value)
        entry.grid(row=self._row, column=1, sticky="ew", pady=3)
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
                make: Callable[[str], Command]) -> ctk.CTkBaseClass:
        """Kurze Auswahl als Segment-Knöpfe, lange als Ausklappmenü."""
        self._field_label(label)
        command = lambda chosen: self.session.execute(make(chosen))  # noqa: E731
        if len(choices) <= SEGMENT_MAX:
            widget = ctk.CTkSegmentedButton(
                self._parent, values=list(choices), command=command, height=30,
                corner_radius=8, font=theme.font(12), fg_color=TRACK,
                selected_color=PILL, selected_hover_color=PILL,
                unselected_color=TRACK, unselected_hover_color=TRACK_HOVER,
                text_color=theme.TEXT)
        else:
            widget = ctk.CTkOptionMenu(
                self._parent, values=list(choices), command=command, height=30,
                corner_radius=8, font=theme.font(13), fg_color=TRACK,
                button_color=TRACK, button_hover_color=TRACK_HOVER, text_color=theme.TEXT,
                dropdown_fg_color=theme.CARD, dropdown_hover_color=theme.HOVER,
                dropdown_text_color=theme.TEXT)
        widget.set(value)
        widget.grid(row=self._row, column=1, sticky="ew", pady=3)
        self.fields[key] = widget
        self._row += 1
        return widget

    def _switch(self, key: str, label: str, value: bool,
                make: Callable[[bool], Command]) -> ctk.CTkSwitch:
        variable = tkinter.BooleanVar(self, value=value)
        switch = ctk.CTkSwitch(
            self._parent, text=label, variable=variable, font=theme.font(13),
            text_color=theme.TEXT, progress_color=theme.ACCENT,
            command=lambda: self.session.execute(make(variable.get())),
        )
        switch.grid(row=self._row, column=0, columnspan=2, sticky="w", pady=6)
        self.fields[key] = switch
        self._row += 1
        return switch

    # ------------------------------------------------------------ Widget

    def _build_widget(self, node: WidgetNode) -> None:
        spec = SPECS[node.type]
        self._header(node.name, node.type)
        self._section("widget", "Eigenschaften")
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
        self._section("layout", "Layout")
        layout = node.layout
        for key in ("row", "column", "rowspan", "columnspan", "padx", "pady"):
            self._entry(key, key, str(getattr(layout, key)),
                        lambda text, k=key: SetLayout(node.id, **{k: _int(k, text)}))
        self._field_label("sticky")
        chips = ctk.CTkFrame(self._parent, fg_color="transparent")
        chips.grid(row=self._row, column=1, sticky="w", pady=3)
        for i, side in enumerate("nsew"):

            def toggle(on: bool, side=side) -> None:
                sticky = layout.sticky.replace(side, "")
                if on:
                    sticky += side
                self.session.execute(SetLayout(node.id, sticky=sticky))

            chip = ToggleChip(chips, side.upper(), side in layout.sticky, toggle)
            chip.grid(row=0, column=i, padx=(0, 6))
            self.fields[f"sticky_{side}"] = chip
        self._row += 1

    # ------------------------------------------------------------ Fenster

    def _build_window(self, window: WindowNode) -> None:
        self._header("Fenster", f"{window.class_name}UI · {window.width} × {window.height}")
        self._section("window", "Allgemein")
        self._entry("class_name", "Klassenname", window.class_name,
                    lambda text: SetWindowProperty("class_name", text.strip()))
        self._entry("title", "Titel", window.title,
                    lambda text: SetWindowProperty("title", text))
        for key, label in (("width", "Breite"), ("height", "Höhe")):
            self._entry(key, label, str(getattr(window, key)),
                        lambda text, k=key: SetWindowProperty(k, _int(k, text)))
        self._switch("resizable", "Größe veränderbar", window.resizable,
                     lambda value: SetWindowProperty("resizable", value))
        self._section("look", "Darstellung")
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
        owner = "im Fenster" if container_id == "window" else f"in {container.name}"
        self._header(f"{'Zeile' if axis == 'row' else 'Spalte'} {index}", owner)
        self._section("line", "Größe")

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
