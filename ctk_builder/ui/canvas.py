"""Arbeitsfläche: zeigt das entworfene Fenster mit echten CTk-Widgets.

Die Widgets reagieren nicht wie im fertigen Programm: Jedes interne
Tk-Teil-Widget bekommt als ersten Bindtag ein eigenes Tag, dessen Handler
das Widget auswählt und mit "break" alle weiteren Handler (Button-Klick,
Eingabefokus usw.) unterdrückt.
"""

from __future__ import annotations

import tkinter
from typing import Any, Callable, Optional

import customtkinter as ctk

from ctk_builder.model import Node, WidgetNode
from ctk_builder.session import Session
from ctk_builder.widget_specs import GROUP, HANDLER, SPECS

EMPTY_LINE_MIN = 40  # Mindestgröße leerer Zeilen/Spalten, nur im Builder
SELECT_COLOR = "#f5a623"
MARGIN = 24
BLOCKED_EVENTS = ("<Button-1>", "<ButtonRelease-1>", "<B1-Motion>",
                  "<Double-Button-1>", "<Button-2>", "<Button-3>",
                  "<Enter>", "<Leave>", "<Motion>")


def widget_kwargs(node: WidgetNode) -> dict[str, Any]:
    """Keyword-Argumente für die Vorschau; entspricht codegen, ohne command/variable."""
    kwargs: dict[str, Any] = {}
    for prop in SPECS[node.type].props:
        value = node.props.get(prop.name, prop.default)
        if prop.kind in (HANDLER, GROUP) or prop.name == "value" or value == prop.default:
            continue
        if prop.name == "font_size":
            kwargs["font"] = ctk.CTkFont(size=value)
        else:
            kwargs[prop.name] = value
    return kwargs


def used_lines(node: Node, axis: str) -> set[int]:
    used = set()
    for child in node.children:
        start = child.layout.row if axis == "row" else child.layout.column
        span = child.layout.rowspan if axis == "row" else child.layout.columnspan
        used.update(range(start, start + span))
    return used


class DesignCanvas(ctk.CTkFrame):
    def __init__(self, master, session: Session):
        super().__init__(master, fg_color=("gray85", "gray12"), corner_radius=0)
        self.session = session
        self.surface = ctk.CTkFrame(self, corner_radius=0, border_width=1)
        self.surface.place(x=MARGIN, y=MARGIN)
        self.surface.grid_propagate(False)
        self.views: dict[str, tkinter.Misc] = {}  # Knoten-ID -> Tk-Widget
        self._placeholders: list[tkinter.Frame] = []
        self._tags: dict[str, str] = {}
        # Erweiterungen (Raster, Drag & Drop) hängen sich hier ein:
        self.after_render: list[Callable[[], None]] = []
        self.on_press: Optional[Callable[[str, tkinter.Event], None]] = None
        self.on_motion: Optional[Callable[[tkinter.Event], None]] = None
        self.on_release: Optional[Callable[[tkinter.Event], None]] = None
        self._outline: list[tkinter.Frame] = [
            tkinter.Frame(self.surface, bg=SELECT_COLOR) for _ in range(4)
        ]
        session.subscribe(self.render)
        session.subscribe_selection(self.show_selection)
        self.render()

    # ------------------------------------------------------------ Rendern

    def view_of(self, node_id: str) -> tkinter.Misc:
        return self.surface if node_id == "window" else self.views[node_id]

    def render(self) -> None:
        window = self.session.project.window
        for widget in [*self._placeholders, *self.views.values()]:
            widget.destroy()
        self._placeholders.clear()
        self.views.clear()
        self.surface.configure(width=window.width, height=window.height)
        self._configure_grid(self.surface, window)
        for child in window.children:
            self._create(child, self.surface)
        self._install_bindings()
        for callback in self.after_render:
            callback()
        self.show_selection()

    def _configure_grid(self, view: tkinter.Misc, node: Node) -> None:
        # Alte Konfiguration zurücksetzen (Grid kann geschrumpft sein)
        columns, rows = view.grid_size()
        for axis, count in (("row", rows), ("column", columns)):
            configure = view.grid_rowconfigure if axis == "row" else view.grid_columnconfigure
            for index in range(count):
                configure(index, weight=0, minsize=0, uniform="")
        for axis in ("row", "column"):
            configure = view.grid_rowconfigure if axis == "row" else view.grid_columnconfigure
            used = used_lines(node, axis)
            for index, config in enumerate(node.grid.lines(axis)):
                minsize = config.minsize if index in used else max(config.minsize, EMPTY_LINE_MIN)
                configure(index, weight=config.weight, minsize=minsize,
                          uniform=config.uniform)
        if not node.children:
            # Ohne Kinder berechnet Tk kein Raster (grid_bbox = 0 0 0 0): Ein
            # unsichtbarer Platzhalter macht die leeren Zellen messbar und sichtbar
            placeholder = tkinter.Frame(view, width=0, height=0)
            placeholder.grid(row=0, column=0)
            placeholder.lower()
            self._placeholders.append(placeholder)
            view.grid_propagate(False)  # leerer Frame behält seine Größe wie im Programm

    def _create(self, node: WidgetNode, master: tkinter.Misc) -> None:
        view = getattr(ctk, node.type)(master, **widget_kwargs(node))
        layout = node.layout
        view.grid(row=layout.row, column=layout.column, rowspan=layout.rowspan,
                  columnspan=layout.columnspan, sticky=layout.sticky,
                  padx=layout.padx, pady=layout.pady)
        self.views[node.id] = view
        if node.is_container:
            self._configure_grid(view, node)
            for child in node.children:
                self._create(child, view)

    # ------------------------------------------------------------ Klicks abfangen

    def _install_bindings(self) -> None:
        designed = set(self.views.values())
        for node_id, view in [("window", self.surface), *self.views.items()]:
            tag = f"design-{node_id}"
            for event in BLOCKED_EVENTS:
                self.bind_class(tag, event, lambda e: "break")
            self.bind_class(tag, "<Button-1>",
                            lambda e, n=node_id: self._pressed(n, e))
            self.bind_class(tag, "<B1-Motion>", self._moved)
            self.bind_class(tag, "<ButtonRelease-1>", self._released)
            self._tag_tree(view, tag, designed)

    def _tag_tree(self, view: tkinter.Misc, tag: str, designed: set) -> None:
        """Setzt tag vor die Bindtags von view und allen internen Teil-Widgets."""
        tags = view.bindtags()
        if not tags[0].startswith("design-"):
            view.bindtags((tag, *tags))
        # tkinter.Misc.winfo_children: CTkFrame verbirgt sein internes Canvas in
        # winfo_children(), Klicks auf leere Frame-Flächen landen aber genau dort
        for child in tkinter.Misc.winfo_children(view):
            if child in designed or child in self._outline:
                continue
            self._tag_tree(child, tag, designed)

    def _pressed(self, node_id: str, event: tkinter.Event) -> str:
        self.session.select(node_id)
        self.focus_set()
        if self.on_press is not None:
            self.on_press(node_id, event)
        return "break"

    def _moved(self, event: tkinter.Event) -> str:
        if self.on_motion is not None:
            self.on_motion(event)
        return "break"

    def _released(self, event: tkinter.Event) -> str:
        if self.on_release is not None:
            self.on_release(event)
        return "break"

    def node_at(self, x_root: int, y_root: int) -> Optional[str]:
        """ID des entworfenen Knotens unter der Bildschirmposition, sonst None."""
        widget = self.winfo_containing(x_root, y_root)
        by_view = {view: node_id for node_id, view in self.views.items()}
        by_view[self.surface] = "window"
        while widget is not None:
            if widget in by_view:
                return by_view[widget]
            widget = widget.master
        return None

    # ------------------------------------------------------------ Auswahl

    def show_selection(self) -> None:
        node_id = self.session.selected_id
        if node_id == "window" or node_id not in self.views:
            for bar in self._outline:
                bar.place_forget()
            return
        view = self.views[node_id]
        top, bottom, left, right = self._outline
        top.place(in_=view, x=-2, y=-2, relwidth=1, width=4, height=2)
        bottom.place(in_=view, x=-2, rely=1, relwidth=1, width=4, height=2)
        left.place(in_=view, x=-2, y=-2, relheight=1, width=2, height=4)
        right.place(in_=view, relx=1, y=-2, relheight=1, width=2, height=4)
        for bar in self._outline:
            bar.lift()
