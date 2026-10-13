# CTk Builder – Plan 3: Interaktive Arbeitsfläche Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rasterlinien, Zeilen-/Spaltenköpfe mit Kontextmenü, Drag & Drop aus der Palette und zum Verschieben sowie Pfeiltasten.

**Architecture:** Zwei neue Module hängen sich in die Hooks der Arbeitsfläche aus Plan 2 ein: `GridOverlay` zeichnet nach jedem Rendern dünne Linien und die Köpfe des aktiven Containers; `DragController` wertet Maus-Events von Palette und Arbeitsfläche aus und führt `AddWidget`/`MoveWidget` aus. Das Hauptfenster verdrahtet beides.

**Tech Stack:** Python 3.12+, customtkinter 6.x, tkinter, pytest

---

## Umgebung

- Arbeitsverzeichnis ist die Wurzel des Repos `tkinter-gui-builder`.
- Alle Befehle nutzen das Virtualenv `.venv` (siehe Plan 1, Task 1).
- **macOS:** Tests laufen direkt; Oberflächentests öffnen kurz echte Fenster.
- **Linux ohne Display (z. B. Claude Code im Browser/Cloud):** Oberflächentests mit
  `xvfb-run -a .venv/bin/pytest …` ausführen. Ohne Display werden sie übersprungen –
  das zählt **nicht** als bestanden; dann `xvfb` installieren (`sudo apt-get install -y xvfb python3-tk`).
- Spezifikation: `docs/superpowers/specs/2026-10-13-ctk-gui-builder-design.md`.

**Voraussetzung:** Plan 2 ist umgesetzt (`.venv/bin/pytest` → 134 passed).

## Dateistruktur nach diesem Plan

```
ctk_builder/ui/
  grid_overlay.py   # neu: Rasterlinien + Zeilen-/Spaltenköpfe
  drag_drop.py      # neu: Drop-Ziel-Berechnung + DragController
  main_window.py    # geändert: Overlay/Drag verdrahten, Pfeiltasten
```

**Technische Eckpunkte:**
- Zellen werden über `grid_bbox(column, row)` vermessen; vorher `update_idletasks()`.
- `grid_location(x, y)` liefert für Punkte rechts/unter dem Raster die Anzahl der Spalten/Zeilen –
  das ist genau der Index „neue Spalte/Zeile anhängen“, den `AddWidget`/`MoveWidget` verstehen.
- Während die Maustaste gedrückt ist, gehen Motion/Release an das Widget, auf dem gedrückt wurde
  (implizites Grab). Deshalb hängt der DragController seine Handler an dieselben Bindtags.
- `CTkButton` löst seinen Befehl bei `<ButtonRelease-1>` aus. Gibt der Palette-Handler beim Ziehen
  `"break"` zurück, wird nicht zusätzlich eingefügt; bei einem Klick ohne Bewegung (< 5 px) läuft
  der normale Button-Befehl.
- Köpfe werden nur für den **aktiven Container** gezeigt (ausgewählter Container bzw. Eltern-Container
  des ausgewählten Widgets), damit verschachtelte Frames übersichtlich bleiben.

---

### Task 1: Raster und Zeilen-/Spaltenköpfe

Linien sind 1-px-`tkinter.Frame`s, die per `place(in_=container_view)` über das Raster jedes Containers gelegt werden. Köpfe sind `tkinter.Label`s auf der Arbeitsfläche oberhalb bzw. links vom aktiven Container: Klick wählt die Zeile/Spalte (Eigenschaften-Panel zeigt `weight`/`minsize`/`uniform`), Rechtsklick öffnet ein Menü (davor/danach einfügen, löschen), `+` hängt eine Zeile/Spalte an.

**Files:**
- Create: `ctk_builder/ui/grid_overlay.py`
- Test: `tests/test_ui_grid_overlay.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_ui_grid_overlay.py`:

```python
import pytest

from conftest import node_named
from ctk_builder.ui.grid_overlay import GridOverlay


@pytest.fixture
def overlay(canvas):
    grid_overlay = GridOverlay(canvas)
    canvas.update()  # Köpfe müssen sichtbar sein, bevor sie Klicks bekommen
    return grid_overlay


def test_draws_lines_for_every_container(overlay):
    # Fenster 4x2: 3 senkrechte + 5 waagerechte, Frame 1x2: 3 + 2
    assert len(overlay._lines) == 13


def test_headers_follow_active_container(overlay):
    # Fenster aktiv: 2 Spalten + 4 Zeilen + 2 Plus-Köpfe
    assert len(overlay._headers) == 8
    frame = node_named(overlay.session, "frame_buttons")
    overlay.session.select(frame.id)
    assert len(overlay._headers) == 2 + 1 + 2


def test_header_click_selects_line_and_plus_adds_column(overlay):
    session = overlay.session
    overlay._headers[0].event_generate("<Button-1>")
    assert session.selected_line == ("window", "column", 0)
    overlay.canvas.update()  # Köpfe wurden neu erzeugt und müssen erst sichtbar werden
    plus = next(h for h in overlay._headers if h.cget("text") == "+")
    plus.event_generate("<Button-1>")
    assert len(session.project.window.grid.columns) == 3
    assert len(overlay._lines) == 14  # eine senkrechte Linie mehr
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_grid_overlay.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.ui.grid_overlay'`

- [ ] **Step 3: Implementierung schreiben**

Datei `ctk_builder/ui/grid_overlay.py`:

```python
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
```

- [ ] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_grid_overlay.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ctk_builder/ui/grid_overlay.py tests/test_ui_grid_overlay.py
git commit -m "feat: Rasterlinien und Zeilen-/Spaltenköpfe"
```


### Task 2: Drag & Drop

`drop_target()` bestimmt aus einer Bildschirmposition Container und Zelle: Über einem Nicht-Container zählt dessen Eltern-Container; beim Verschieben wird das gezogene Widget samt Inhalt übersprungen (ein Frame kann nicht in sich selbst fallen). Der `DragController` zeigt während des Ziehens einen grünen Rahmen um die Zielzelle und führt beim Loslassen `AddWidget` (aus der Palette) bzw. `MoveWidget` (Tausch bei belegter Zelle) aus.

**Files:**
- Create: `ctk_builder/ui/drag_drop.py`
- Test: `tests/test_ui_drag_drop.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_ui_drag_drop.py`:

```python
import pytest

from conftest import node_named
from ctk_builder.ui.drag_drop import DragController, DropTarget, drop_target
from ctk_builder.ui.palette import Palette


@pytest.fixture
def drag(canvas):
    palette = Palette(canvas.master, canvas.session)
    palette.pack(side="left", before=canvas)
    canvas.update()
    return DragController(canvas, palette)


def below_grid(canvas):
    """Bildschirmposition knapp unter der letzten Zeile des Fensters."""
    surface = canvas.surface
    _, y, _, height = surface.grid_bbox(0, 3)
    return surface.winfo_rootx() + 10, surface.winfo_rooty() + y + height + 10


def drag_events(widget, to_x, to_y):
    widget.event_generate("<Button-1>", x=3, y=3,
                          rootx=widget.winfo_rootx() + 3, rooty=widget.winfo_rooty() + 3)
    widget.event_generate("<B1-Motion>", x=3, y=3, rootx=to_x, rooty=to_y)
    widget.event_generate("<ButtonRelease-1>", x=3, y=3, rootx=to_x, rooty=to_y)
    widget.update()


def test_drop_target_on_widget_and_beyond_grid(canvas):
    session = canvas.session
    save = node_named(session, "button_save")
    view = canvas.views[save.id]
    target = drop_target(canvas, view.winfo_rootx() + 5, view.winfo_rooty() + 5)
    assert target == DropTarget(node_named(session, "frame_buttons").id, 0, 1)
    assert drop_target(canvas, *below_grid(canvas)) == DropTarget("window", 4, 0)


def test_drop_target_skips_dragged_frame(canvas):
    frame = node_named(canvas.session, "frame_buttons")
    view = canvas.views[frame.id]
    target = drop_target(canvas, view.winfo_rootx() + 5, view.winfo_rooty() + 5,
                         moving=frame.id)
    assert target.container_id == "window"


def test_drag_from_palette_adds_at_drop_cell(drag):
    session = drag.session
    inner = drag.palette.buttons["CTkButton"].winfo_children()[0]
    drag_events(inner, *below_grid(drag.canvas))
    added = session.project.find(session.selected_id)
    assert added.type == "CTkButton"
    assert (added.layout.row, added.layout.column) == (4, 0)


def test_drag_widget_onto_other_swaps(drag):
    session = drag.session
    name = node_named(session, "label_name")
    mail = node_named(session, "label_mail")
    source = drag.canvas.views[name.id].winfo_children()[0]
    target = drag.canvas.views[mail.id]
    drag_events(source, target.winfo_rootx() + 3, target.winfo_rooty() + 3)
    assert session.project.find(name.id).layout.row == 1
    assert session.project.find(mail.id).layout.row == 0


def test_small_movement_is_a_click(drag):
    session = drag.session
    name = node_named(session, "label_name")
    source = drag.canvas.views[name.id].winfo_children()[0]
    drag_events(source, source.winfo_rootx() + 4, source.winfo_rooty() + 4)
    assert session.selected_id == name.id
    assert session.project.find(name.id).layout.row == 0
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_drag_drop.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.ui.drag_drop'`

- [ ] **Step 3: Implementierung schreiben**

Datei `ctk_builder/ui/drag_drop.py`:

```python
"""Drag & Drop: Widgets aus der Palette ziehen und auf der Arbeitsfläche verschieben."""

from __future__ import annotations

import tkinter
from dataclasses import dataclass
from typing import Optional

from ctk_builder.commands import AddWidget, MoveWidget
from ctk_builder.ui.canvas import EMPTY_LINE_MIN, DesignCanvas
from ctk_builder.ui.palette import Palette

DRAG_THRESHOLD = 5  # Pixel, ab denen aus einem Klick ein Ziehen wird
TARGET_COLOR = "#2fa572"


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

        def add_tag(widget: tkinter.Misc) -> None:
            widget.bindtags((tag, *widget.bindtags()))
            for child in widget.winfo_children():
                add_tag(child)

        add_tag(button)

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
```

- [ ] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_drag_drop.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ctk_builder/ui/drag_drop.py tests/test_ui_drag_drop.py
git commit -m "feat: Drag & Drop aus der Palette und auf der Arbeitsfläche"
```


### Task 3: Im Hauptfenster verdrahten und Pfeiltasten

**Files:**
- Modify: `ctk_builder/ui/main_window.py`
- Test: `tests/test_ui_main_window.py` (Tests anhängen)

- [ ] **Step 1: Failing Tests an `tests/test_ui_main_window.py` anhängen**

```python
def test_arrow_keys_move_selected_widget(app):
    session = app.session
    switch = AddWidget("window", "CTkSwitch", 4, 0)
    session.execute(switch)
    session.select(switch.node_id)
    app.nudge(0, 1)
    assert session.project.find(switch.node_id).layout.column == 1
    app.nudge(0, -5)  # außerhalb: nichts passiert
    assert session.project.find(switch.node_id).layout.column == 1


def test_overlay_and_drag_are_wired(app):
    assert app.grid_overlay.canvas is app.canvas
    assert app.canvas.on_press == app.drag.press_on_canvas
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_main_window.py -v`

Expected: 2 failed mit `AttributeError: 'MainWindow' object has no attribute 'nudge'` bzw. `'grid_overlay'`

- [ ] **Step 3: Import von `MoveWidget`**

In `ctk_builder/ui/main_window.py` ersetzen:

```python
from ctk_builder.commands import DuplicateWidget, RemoveWidget
```

durch:

```python
from ctk_builder.commands import DuplicateWidget, MoveWidget, RemoveWidget
```

- [ ] **Step 4: Importe der neuen Module**

In `ctk_builder/ui/main_window.py` ersetzen:

```python
from ctk_builder.ui.canvas import DesignCanvas
```

durch:

```python
from ctk_builder.ui.canvas import DesignCanvas
from ctk_builder.ui.drag_drop import DragController
from ctk_builder.ui.grid_overlay import GridOverlay
```

- [ ] **Step 5: Overlay und DragController nach der Arbeitsfläche erzeugen**

In `ctk_builder/ui/main_window.py` ersetzen:

```python
        self.canvas = DesignCanvas(self, self.session)
        self.canvas.grid(row=0, column=1, sticky="nsew", pady=8)
```

durch:

```python
        self.canvas = DesignCanvas(self, self.session)
        self.canvas.grid(row=0, column=1, sticky="nsew", pady=8)
        self.grid_overlay = GridOverlay(self.canvas)
        self.drag = DragController(self.canvas, self.palette)
```

- [ ] **Step 6: Pfeiltasten in `_bind_keys` binden**

In `ctk_builder/ui/main_window.py` ersetzen:

```python
        for widget in (self.canvas, self.tree.tree):
            widget.bind("<Delete>", lambda e: self.delete_selected())
            widget.bind("<BackSpace>", lambda e: self.delete_selected())
```

durch:

```python
        for widget in (self.canvas, self.tree.tree):
            widget.bind("<Delete>", lambda e: self.delete_selected())
            widget.bind("<BackSpace>", lambda e: self.delete_selected())
        for key, (d_row, d_column) in {"Up": (-1, 0), "Down": (1, 0),
                                       "Left": (0, -1), "Right": (0, 1)}.items():
            self.canvas.bind(f"<{key}>", lambda e, r=d_row, c=d_column: self.nudge(r, c))
```

- [ ] **Step 7: Methode `nudge` vor `duplicate_selected` einfügen**

In `ctk_builder/ui/main_window.py` ersetzen:

```python
    def duplicate_selected(self) -> None:
```

durch:

```python
    def nudge(self, d_row: int, d_column: int) -> None:
        """Verschiebt das ausgewählte Widget um eine Zelle (Pfeiltasten)."""
        node = self.session.project.find(self.session.selected_id)
        if node is None or node.id == "window":
            return
        row, column = node.layout.row + d_row, node.layout.column + d_column
        if row < 0 or column < 0:
            return
        parent = self.session.project.parent_of(node.id)
        self.session.execute(MoveWidget(node.id, parent.id, row, column))

    def duplicate_selected(self) -> None:
```

- [ ] **Step 8: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_main_window.py -v`

Expected: 6 passed

- [ ] **Step 9: Commit**

```bash
git add ctk_builder/ui/main_window.py tests/test_ui_main_window.py
git commit -m "feat: Raster, Drag & Drop und Pfeiltasten im Hauptfenster"
```


### Task 4: Abschluss Plan 3

- [ ] **Step 1: Komplette Testsuite**

Run: `.venv/bin/pytest -v` (Linux ohne Display: `xvfb-run -a .venv/bin/pytest -v`)

Expected: `144 passed`

- [ ] **Step 2: Manueller Drag-&-Drop-Test (nur mit Desktop)**

Drag & Drop mit echter Maus lässt sich nicht vollständig automatisiert testen. Run: `.venv/bin/python -m ctk_builder`

1. „Button“ aus der Palette auf die Arbeitsfläche ziehen: grüner Rahmen folgt der Zelle unter der Maus; Loslassen fügt dort ein.
2. Unter die letzte Zeile ziehen: neue Zeile entsteht. Rechts neben die letzte Spalte: neue Spalte.
3. Ein Widget auf ein anderes ziehen: beide tauschen die Plätze.
4. „Frame“ einfügen, auswählen, ein Label hineinziehen: Label landet im Frame (Strukturbaum zeigt es eingerückt).
5. Den Frame auf eine Zelle in sich selbst ziehen: nichts passiert (Ziel ist der Eltern-Container).
6. Spaltenkopf anklicken: Eigenschaften zeigen `weight`; auf `1` setzen – die Spalte dehnt sich.
7. Rechtsklick auf einen Zeilenkopf → „Zeile davor einfügen“; „Zeile löschen“ auf einer belegten Zeile zeigt eine Meldung in der Statusleiste.
8. Widget auswählen, Arbeitsfläche hat Fokus, Pfeiltasten verschieben es zellenweise.
9. Ein Palette-Klick ohne Ziehen fügt weiterhin in die nächste freie Zelle ein.

Gefundene Probleme als eigene Tasks nachtragen und mit Test-first beheben.

- [ ] **Step 3: Pushen**

```bash
git push
```


### Task 5: Klicks und Tasten auf CTkFrame-Flächen (nachgetragen)

Gefunden beim manuellen Test aus Task 4 (Schritte 5, 6 und 8), durchgespielt mit echten
Mausereignissen (`xdotool` unter Xvfb). Zwei Eigenheiten von `CTkFrame`, die Tests mit
`event_generate` direkt auf dem Frame nicht bemerken:

- `CTkFrame.winfo_children()` verbirgt das interne `_canvas`. Es bekam daher kein
  `design-…`-Bindtag: Ein Klick auf eine leere Stelle der Arbeitsfläche oder eines Frames
  wählte nichts aus, und ein Frame ließ sich an seiner freien Fläche nicht greifen.
- `CTkFrame.bind()` bindet an das interne `_canvas`, den Fokus holt sich aber `DesignCanvas`
  selbst (`_pressed` → `focus_set()`). Pfeiltasten und Entf/Rücktaste wirkten auf der
  Arbeitsfläche deshalb nie.

**Files:**
- Modify: `ctk_builder/ui/canvas.py`, `ctk_builder/ui/main_window.py`
- Test: `tests/test_ui_canvas.py`, `tests/test_ui_main_window.py` (Tests anhängen)

- [x] **Step 1: Failing Tests anhängen**

An `tests/test_ui_canvas.py` anhängen (klickt wie die echte Maus das Widget, das oben liegt):

```python
def click_screen(canvas, x_root, y_root):
    """Klickt das Tk-Widget, das an der Bildschirmposition oben liegt – wie die echte Maus."""
    target = canvas.winfo_containing(x_root, y_root)
    click(target, x_root - target.winfo_rootx(), y_root - target.winfo_rooty())


def test_click_on_empty_area_of_frames_selects_them(canvas):
    """CTkFrame verbirgt sein internes Canvas in winfo_children(); Klicks darauf zählen trotzdem."""
    session = canvas.session
    command = AddWidget("window", "CTkFrame", 4, 0)
    session.execute(command)
    canvas.update()
    view = canvas.views[command.node_id]
    click_screen(canvas, view.winfo_rootx() + 20, view.winfo_rooty() + 20)
    assert session.selected_id == command.node_id
    surface = canvas.surface
    click_screen(canvas, surface.winfo_rootx() + 410, surface.winfo_rooty() + 250)
    assert session.selected_id == "window"
```

An `tests/test_ui_main_window.py` anhängen (Import oben: `from conftest import click, node_named`):

```python
def test_keys_reach_canvas_after_click(app):
    """Nach einem Klick hat die Arbeitsfläche den Fokus; Pfeiltasten und Entf wirken dort."""
    session = app.session
    switch = AddWidget("window", "CTkSwitch", 4, 0)
    session.execute(switch)
    app.update()
    app.focus_force()
    click(app.canvas.views[switch.node_id].winfo_children()[0])
    assert app.focus_get() is app.canvas
    app.canvas.event_generate("<Right>")
    assert session.project.find(switch.node_id).layout.column == 1
    app.canvas.event_generate("<Delete>")
    assert session.project.find(switch.node_id) is None
```

- [x] **Step 2: Tests ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_canvas.py tests/test_ui_main_window.py -v`

Expected: 2 failed (Auswahl bleibt `window` bzw. Spalte bleibt 0)

- [x] **Step 3: Internes Canvas mit taggen**

In `ctk_builder/ui/canvas.py` (`_tag_tree`) ersetzen:

```python
        for child in view.winfo_children():
```

durch:

```python
        # tkinter.Misc.winfo_children: CTkFrame verbirgt sein internes Canvas in
        # winfo_children(), Klicks auf leere Frame-Flächen landen aber genau dort
        for child in tkinter.Misc.winfo_children(view):
```

- [x] **Step 4: Tasten an das fokussierte Widget binden**

In `ctk_builder/ui/main_window.py` (`_bind_keys`) ersetzen:

```python
        for widget in (self.canvas, self.tree.tree):
            widget.bind("<Delete>", lambda e: self.delete_selected())
            widget.bind("<BackSpace>", lambda e: self.delete_selected())
        for key, (d_row, d_column) in {"Up": (-1, 0), "Down": (1, 0),
                                       "Left": (0, -1), "Right": (0, 1)}.items():
            self.canvas.bind(f"<{key}>", lambda e, r=d_row, c=d_column: self.nudge(r, c))
```

durch:

```python
        # tkinter.Misc.bind: CTkFrame.bind() bindet an sein internes Canvas,
        # den Fokus hat aber die Arbeitsfläche selbst (DesignCanvas._pressed)
        for widget in (self.canvas, self.tree.tree):
            tkinter.Misc.bind(widget, "<Delete>", lambda e: self.delete_selected())
            tkinter.Misc.bind(widget, "<BackSpace>", lambda e: self.delete_selected())
        for key, (d_row, d_column) in {"Up": (-1, 0), "Down": (1, 0),
                                       "Left": (0, -1), "Right": (0, 1)}.items():
            tkinter.Misc.bind(self.canvas, f"<{key}>",
                              lambda e, r=d_row, c=d_column: self.nudge(r, c))
```

- [x] **Step 5: Komplette Testsuite**

Run: `xvfb-run -a .venv/bin/pytest -q`

Expected: `146 passed`

- [x] **Step 6: Commit**

```bash
git add ctk_builder/ui/canvas.py ctk_builder/ui/main_window.py tests/test_ui_canvas.py tests/test_ui_main_window.py docs/superpowers/plans/2026-10-13-ctk-builder-3-arbeitsflaeche.md
git commit -m "fix: Klicks und Tasten auf CTkFrame-Flächen der Arbeitsfläche"
```
