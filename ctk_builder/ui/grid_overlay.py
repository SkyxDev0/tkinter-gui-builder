"""Rasterlinien aller Container und Zeilen-/Spaltenköpfe des aktiven Containers."""

from __future__ import annotations

import tkinter

from ctk_builder.commands import InsertLine, RemoveLine
from ctk_builder.ui import theme
from ctk_builder.ui.canvas import DesignCanvas

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
        self.lines_visible = True
        canvas.after_render.append(self.redraw)
        self.session.subscribe_selection(self.redraw_headers)
        self.redraw()

    def redraw(self) -> None:
        self.canvas.update_idletasks()
        for line in self._lines:
            line.destroy()
        self._lines.clear()
        project = self.session.project
        if self.lines_visible:
            for node in [project.window, *project.iter_widgets()]:
                if node.is_container:
                    self._draw_lines(node.id, len(node.grid.rows), len(node.grid.columns))
        self.redraw_headers()

    def set_lines_visible(self, visible: bool) -> None:
        """Rasterlinien ein- oder ausblenden (Köpfe bleiben)."""
        self.lines_visible = visible
        self.redraw()

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
        line = tkinter.Frame(self.canvas.surface, bg=theme.pick(theme.GRID_LINE))
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
        anchor_x, anchor_y = self.canvas.header_anchor(container_id)
        selected = session.selected_line

        for axis in ("column", "row"):
            lines = container.grid.lines(axis)
            edges = line_edges(view, axis, len(lines))
            for index, (start, size) in enumerate(edges):
                active = selected == (container_id, axis, index)
                # Zeilenköpfe sind schmal: dort nur der Index
                text = f"{index} ⚖{lines[index].weight}" if axis == "column" else str(index)
                header = self._header(text, active)
                header.bind("<Button-1>", lambda e, a=axis, i=index:
                            session.select_line(container_id, a, i))
                header.bind("<Button-2>", lambda e, a=axis, i=index:
                            self._context_menu(e, container_id, a, i))
                header.bind("<Button-3>", lambda e, a=axis, i=index:
                            self._context_menu(e, container_id, a, i))
                if axis == "column":
                    header.place(x=origin_x + start + 1, y=anchor_y - HEADER_SIZE - 2,
                                 width=max(size - 2, 1), height=HEADER_SIZE - 2)
                else:
                    header.place(x=anchor_x - HEADER_SIZE - 2, y=origin_y + start + 1,
                                 width=HEADER_SIZE - 2, height=max(size - 2, 1))
            end = edges[-1][0] + edges[-1][1]
            plus = self._header("+", False, plus=True)
            plus.bind("<Button-1>", lambda e, a=axis, n=len(lines):
                      session.execute(InsertLine(container_id, a, n)))
            if axis == "column":
                plus.place(x=origin_x + end + 2, y=anchor_y - HEADER_SIZE - 2,
                           width=HEADER_SIZE, height=HEADER_SIZE - 2)
            else:
                plus.place(x=anchor_x - HEADER_SIZE - 2, y=origin_y + end + 2,
                           width=HEADER_SIZE - 2, height=HEADER_SIZE)

    def _header(self, text: str, active: bool, plus: bool = False) -> tkinter.Label:
        if active:
            bg, fg = theme.ACCENT, ("#ffffff", "#ffffff")
        elif plus:
            bg, fg = theme.ACCENT_SOFT, theme.ACCENT_TEXT
        else:
            bg, fg = theme.HEADER_BG, theme.MUTED
        header = tkinter.Label(
            self.canvas, text=text, font=theme.tk_font(10, "bold" if plus else "normal"),
            bg=theme.pick(bg), fg=theme.pick(fg), cursor="hand2",
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
