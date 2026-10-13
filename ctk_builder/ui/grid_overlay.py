"""Rasterlinien aller Container und Zeilen-/Spaltenköpfe des aktiven Containers."""

from __future__ import annotations

import tkinter

from ctk_builder.commands import InsertLine, RemoveLine
from ctk_builder.ui.canvas import DesignCanvas

LINE_COLOR = "#6b6b6b"
HEADER_BG = "#3a3a3a"
HEADER_ACTIVE_BG = "#1f6aa5"
HEADER_FG = "#dce4ee"
HEADER_SIZE = 18


def line_edges(view: tkinter.Misc, axis: str, count: int) -> list[tuple[int, int]]:
    """(Anfang, Größe) jeder Zeile/Spalte in Koordinaten von view."""
    edges = []
    for index in range(count):
        if axis == "row":
            _, start, _, size = view.grid_bbox(0, index)
        else:
            start, _, size, _ = view.grid_bbox(index, 0)
        edges.append((start, size))
    return edges


class GridOverlay:
    def __init__(self, canvas: DesignCanvas):
        self.canvas = canvas
        self.session = canvas.session
        self._lines: list[tkinter.Frame] = []
        self._headers: list[tkinter.Widget] = []
        canvas.after_render.append(self.redraw)
        self.session.subscribe_selection(self.redraw_headers)
        self.redraw()

    def redraw(self) -> None:
        self.canvas.update_idletasks()
        for line in self._lines:
            line.destroy()
        self._lines.clear()
        project = self.session.project
        for node in [project.window, *project.iter_widgets()]:
            if node.is_container:
                self._draw_lines(node.id, len(node.grid.rows), len(node.grid.columns))
        self.redraw_headers()

    def _draw_lines(self, node_id: str, rows: int, columns: int) -> None:
        view = self.canvas.view_of(node_id)
        row_edges = line_edges(view, "row", rows)
        column_edges = line_edges(view, "column", columns)
        top = row_edges[0][0]
        bottom = row_edges[-1][0] + row_edges[-1][1]
        left = column_edges[0][0]
        right = column_edges[-1][0] + column_edges[-1][1]
        for start, size in column_edges + [(right, 0)]:
            self._line(view, x=start, y=top, width=1, height=bottom - top)
        for start, size in row_edges + [(bottom, 0)]:
            self._line(view, x=left, y=start, width=right - left, height=1)

    def _line(self, view: tkinter.Misc, **place: int) -> None:
        line = tkinter.Frame(self.canvas.surface, bg=LINE_COLOR)
        line.place(in_=view, **place)
        line.lift()
        self._lines.append(line)

    # ------------------------------------------------------------ Köpfe

    def redraw_headers(self) -> None:
        for header in self._headers:
            header.destroy()
        self._headers.clear()
        session = self.session
        container_id = session.target_container_id()
        container = session.project.find(container_id)
        if container is None or container_id not in (["window"] + list(self.canvas.views)):
            return
        self.canvas.update_idletasks()
        view = self.canvas.view_of(container_id)
        origin_x = view.winfo_rootx() - self.canvas.winfo_rootx()
        origin_y = view.winfo_rooty() - self.canvas.winfo_rooty()
        selected = session.selected_line

        for axis in ("column", "row"):
            lines = container.grid.lines(axis)
            edges = line_edges(view, axis, len(lines))
            for index, (start, size) in enumerate(edges):
                active = selected == (container_id, axis, index)
                text = f"{index} ⚖{lines[index].weight}"
                header = self._header(text, active)
                header.bind("<Button-1>", lambda e, a=axis, i=index:
                            session.select_line(container_id, a, i))
                header.bind("<Button-2>", lambda e, a=axis, i=index:
                            self._context_menu(e, container_id, a, i))
                header.bind("<Button-3>", lambda e, a=axis, i=index:
                            self._context_menu(e, container_id, a, i))
                if axis == "column":
                    header.place(x=origin_x + start, y=origin_y - HEADER_SIZE,
                                 width=max(size, 1), height=HEADER_SIZE - 2)
                else:
                    header.place(x=origin_x - HEADER_SIZE, y=origin_y + start,
                                 width=HEADER_SIZE - 2, height=max(size, 1))
            end = edges[-1][0] + edges[-1][1]
            plus = self._header("+", False)
            plus.bind("<Button-1>", lambda e, a=axis, n=len(lines):
                      session.execute(InsertLine(container_id, a, n)))
            if axis == "column":
                plus.place(x=origin_x + end + 2, y=origin_y - HEADER_SIZE,
                           width=HEADER_SIZE, height=HEADER_SIZE - 2)
            else:
                plus.place(x=origin_x - HEADER_SIZE, y=origin_y + end + 2,
                           width=HEADER_SIZE - 2, height=HEADER_SIZE)

    def _header(self, text: str, active: bool) -> tkinter.Label:
        header = tkinter.Label(
            self.canvas, text=text, font=("TkDefaultFont", 9),
            bg=HEADER_ACTIVE_BG if active else HEADER_BG, fg=HEADER_FG,
        )
        self._headers.append(header)
        return header

    def _context_menu(self, event: tkinter.Event, container_id: str,
                      axis: str, index: int) -> None:
        name = "Zeile" if axis == "row" else "Spalte"
        execute = self.session.execute
        menu = tkinter.Menu(self.canvas, tearoff=False)
        menu.add_command(label=f"{name} davor einfügen",
                         command=lambda: execute(InsertLine(container_id, axis, index)))
        menu.add_command(label=f"{name} danach einfügen",
                         command=lambda: execute(InsertLine(container_id, axis, index + 1)))
        menu.add_separator()
        menu.add_command(label=f"{name} löschen",
                         command=lambda: execute(RemoveLine(container_id, axis, index)))
        menu.tk_popup(event.x_root, event.y_root)
