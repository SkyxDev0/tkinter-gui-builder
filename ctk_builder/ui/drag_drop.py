"""Drag & Drop: Widgets aus der Palette ziehen und auf der Arbeitsfläche verschieben."""

from __future__ import annotations

import tkinter
from dataclasses import dataclass
from typing import Optional

from ctk_builder.commands import AddWidget, MoveWidget
from ctk_builder.ui import theme
from ctk_builder.ui.canvas import EMPTY_LINE_MIN, DesignCanvas
from ctk_builder.ui.palette import Palette
from ctk_builder.ui.widgets import add_bindtag

DRAG_THRESHOLD = 5  # Pixel, ab denen aus einem Klick ein Ziehen wird
TARGET_COLOR = theme.DROP


@dataclass(frozen=True)
class DropTarget:
    container_id: str
    row: int
    column: int


def drop_target(canvas: DesignCanvas, x_root: int, y_root: int,
                moving: Optional[str] = None) -> Optional[DropTarget]:
    """Container und Zelle unter der Bildschirmposition.

    Ein Widget selbst ist nie Ziel: Zeigt man auf ein Nicht-Container-Widget,
    zählt die Zelle in dessen Eltern-Container. Beim Verschieben (moving) wird
    das gezogene Widget samt Inhalt übersprungen. Zeilen-/Spaltenindex gleich
    der Anzahl bedeutet „neue Zeile/Spalte anhängen“.
    """
    project = canvas.session.project
    node_id = canvas.node_at(x_root, y_root)
    if node_id is None:
        return None
    node = project.find(node_id)
    if moving is not None and project.is_descendant(node_id, moving):
        node = project.parent_of(moving)
    elif not node.is_container:
        node = project.parent_of(node_id)
    view = canvas.view_of(node.id)
    column, row = view.grid_location(x_root - view.winfo_rootx(),
                                     y_root - view.winfo_rooty())
    row = min(max(row, 0), len(node.grid.rows))
    column = min(max(column, 0), len(node.grid.columns))
    return DropTarget(node.id, row, column)


class DragController:
    def __init__(self, canvas: DesignCanvas, palette: Palette):
        self.canvas = canvas
        self.palette = palette
        self.session = canvas.session
        self._start: Optional[tuple[int, int]] = None
        self._dragging = False
        self._widget_type: Optional[str] = None  # aus der Palette
        self._moving: Optional[str] = None        # vorhandenes Widget
        self._target: Optional[DropTarget] = None
        self._marker = [tkinter.Frame(canvas.surface, bg=TARGET_COLOR) for _ in range(4)]
        canvas.on_press = self.press_on_canvas
        canvas.on_motion = self.motion
        canvas.on_release = self.release
        for widget_type, button in palette.buttons.items():
            self._hook_palette_button(button, widget_type)

    # ------------------------------------------------------------ Start

    def _hook_palette_button(self, button: tkinter.Misc, widget_type: str) -> None:
        tag = f"palette-drag-{widget_type}"
        button.bind_class(tag, "<Button-1>", lambda e: self._begin(e, widget_type=widget_type))
        button.bind_class(tag, "<B1-Motion>", self.motion)
        button.bind_class(tag, "<ButtonRelease-1>", self.release)
        add_bindtag(button, tag)

    def press_on_canvas(self, node_id: str, event: tkinter.Event) -> None:
        if node_id != "window":
            self._begin(event, moving=node_id)

    def _begin(self, event: tkinter.Event, widget_type: Optional[str] = None,
               moving: Optional[str] = None) -> None:
        self._start = (event.x_root, event.y_root)
        self._dragging = False
        self._widget_type = widget_type
        self._moving = moving
        self._target = None

    # ------------------------------------------------------------ Ziehen

    def motion(self, event: tkinter.Event) -> Optional[str]:
        if self._start is None:
            return None
        dx = abs(event.x_root - self._start[0])
        dy = abs(event.y_root - self._start[1])
        if not self._dragging and max(dx, dy) < DRAG_THRESHOLD:
            return None
        self._dragging = True
        self._target = drop_target(self.canvas, event.x_root, event.y_root, self._moving)
        self._show_marker()
        return "break"

    def release(self, event: tkinter.Event) -> Optional[str]:
        if self._start is None:
            return None
        dragging, target = self._dragging, self._target
        widget_type, moving = self._widget_type, self._moving
        self._start = None
        self._dragging = False
        self._hide_marker()
        if not dragging:
            return None  # normaler Klick: Palette-Button fügt wie gewohnt ein
        if target is not None:
            self.drop(target, widget_type=widget_type, moving=moving)
        return "break"

    def drop(self, target: DropTarget, widget_type: Optional[str] = None,
             moving: Optional[str] = None) -> None:
        if widget_type is not None:
            command = AddWidget(target.container_id, widget_type, target.row, target.column)
            if self.session.execute(command):
                self.session.select(command.node_id)
        elif moving is not None:
            node = self.session.project.find(moving)
            parent = self.session.project.parent_of(moving)
            unchanged = (parent.id == target.container_id
                         and (node.layout.row, node.layout.column) == (target.row, target.column))
            if not unchanged:
                self.session.execute(
                    MoveWidget(moving, target.container_id, target.row, target.column))

    # ------------------------------------------------------------ Markierung

    def _show_marker(self) -> None:
        target = self._target
        if target is None:
            self._hide_marker()
            return
        project = self.session.project
        container = project.find(target.container_id)
        view = self.canvas.view_of(target.container_id)
        rows, columns = len(container.grid.rows), len(container.grid.columns)
        if target.column < columns:
            x, _, width, _ = view.grid_bbox(target.column, 0)
        else:
            x0, _, w0, _ = view.grid_bbox(columns - 1, 0)
            x, width = x0 + w0, EMPTY_LINE_MIN
        if target.row < rows:
            _, y, _, height = view.grid_bbox(0, target.row)
        else:
            _, y0, _, h0 = view.grid_bbox(0, rows - 1)
            y, height = y0 + h0, EMPTY_LINE_MIN
        top, bottom, left, right = self._marker
        top.place(in_=view, x=x, y=y, width=width, height=3)
        bottom.place(in_=view, x=x, y=y + height - 3, width=width, height=3)
        left.place(in_=view, x=x, y=y, width=3, height=height)
        right.place(in_=view, x=x + width - 3, y=y, width=3, height=height)
        for bar in self._marker:
            bar.lift()

    def _hide_marker(self) -> None:
        for bar in self._marker:
            bar.place_forget()
