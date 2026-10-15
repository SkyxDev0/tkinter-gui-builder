"""Projektmodell: reine Datenklassen ohne Tkinter-Abhängigkeit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional, Union


@dataclass
class LineConfig:
    """Konfiguration einer Grid-Zeile oder -Spalte."""

    weight: int = 0
    minsize: int = 0
    uniform: str = ""

    def is_default(self) -> bool:
        return self == LineConfig()


@dataclass
class GridConfig:
    """Zeilen und Spalten eines Containers. Die Anzahl ist len(rows)/len(columns)."""

    rows: list[LineConfig] = field(default_factory=lambda: [LineConfig()])
    columns: list[LineConfig] = field(default_factory=lambda: [LineConfig()])

    def lines(self, axis: str) -> list[LineConfig]:
        if axis == "row":
            return self.rows
        if axis == "column":
            return self.columns
        raise ValueError(f"Unbekannte Achse: {axis!r}")


GRID = "grid"    # Container ordnet seine Kinder im Raster an (grid)
PLACE = "place"  # Container platziert seine Kinder frei (place)
MANAGERS = (PLACE, GRID)


@dataclass
class Layout:
    """Platzierung eines Widgets in seinem Container.

    Raster-Container nutzen row … pady, freie Container x und y (logische Pixel,
    ohne CTk-Skalierung). Die jeweils anderen Felder bleiben erhalten, damit ein
    Wechsel des Modus zurück nichts verliert.
    """

    row: int = 0
    column: int = 0
    rowspan: int = 1
    columnspan: int = 1
    sticky: str = ""
    padx: int = 0
    pady: int = 0
    x: int = 0
    y: int = 0

    def cells(self) -> set[tuple[int, int]]:
        return {
            (r, c)
            for r in range(self.row, self.row + self.rowspan)
            for c in range(self.column, self.column + self.columnspan)
        }


@dataclass
class WidgetNode:
    id: str
    type: str
    name: str
    props: dict[str, Any] = field(default_factory=dict)
    layout: Layout = field(default_factory=Layout)
    grid: Optional[GridConfig] = None  # nur bei Containern gesetzt
    children: list[WidgetNode] = field(default_factory=list)
    manager: Optional[str] = None  # nur bei Containern: PLACE oder GRID

    @property
    def is_container(self) -> bool:
        return self.grid is not None

    @property
    def is_free(self) -> bool:
        """True, wenn der Container seine Kinder frei platziert."""
        return self.is_container and self.manager == PLACE

    @property
    def is_grid(self) -> bool:
        """True, wenn der Container seine Kinder im Raster anordnet."""
        return self.is_container and not self.is_free


@dataclass
class WindowNode:
    id: str = "window"
    class_name: str = "App"
    title: str = "App"
    width: int = 400
    height: int = 300
    resizable: bool = True
    appearance_mode: str = "system"
    color_theme: str = "blue"
    grid: GridConfig = field(default_factory=GridConfig)
    children: list[WidgetNode] = field(default_factory=list)
    manager: str = GRID  # neue Projekte: frei (new_project); Format 1 kannte nur das Raster

    @property
    def is_container(self) -> bool:
        return True

    @property
    def is_free(self) -> bool:
        return self.manager == PLACE

    @property
    def is_grid(self) -> bool:
        return not self.is_free


Node = Union[WindowNode, WidgetNode]


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def occupant(container: Node, row: int, column: int,
             ignore: frozenset[str] = frozenset()) -> Optional[WidgetNode]:
    """Liefert das Kind, das die Zelle (row, column) belegt, oder None."""
    for child in container.children:
        if child.id in ignore:
            continue
        if (row, column) in child.layout.cells():
            return child
    return None


def fits(container: Node, layout: Layout,
         ignore: frozenset[str] = frozenset()) -> bool:
    """True, wenn layout innerhalb des Grids liegt und keine fremde Zelle überdeckt."""
    grid = container.grid
    if layout.row < 0 or layout.column < 0:
        return False
    if layout.row + layout.rowspan > len(grid.rows):
        return False
    if layout.column + layout.columnspan > len(grid.columns):
        return False
    return all(occupant(container, r, c, ignore) is None for r, c in layout.cells())


def next_free_cell(container: Node) -> tuple[int, int]:
    """Erste freie Zelle zeilenweise; ist alles voll, die Zelle unter dem Grid."""
    for r in range(len(container.grid.rows)):
        for c in range(len(container.grid.columns)):
            if occupant(container, r, c) is None:
                return r, c
    return len(container.grid.rows), 0


def new_project() -> "Project":
    """Neues Projekt im Builder: Widgets werden frei platziert."""
    return Project(WindowNode(manager=PLACE))


class Project:
    """Hält den Fensterbaum und benachrichtigt Beobachter über Änderungen."""

    def __init__(self, window: Optional[WindowNode] = None,
                 format_version: Optional[int] = None):
        self.window = window if window is not None else WindowNode()
        self.format_version = format_version  # Format der geladenen Datei, sonst None
        self._listeners: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    def iter_widgets(self) -> Iterator[WidgetNode]:
        """Alle Widgets in Baumreihenfolge (Tiefensuche)."""

        def walk(node: Node) -> Iterator[WidgetNode]:
            for child in node.children:
                yield child
                yield from walk(child)

        return walk(self.window)

    def find(self, node_id: str) -> Optional[Node]:
        if node_id == self.window.id:
            return self.window
        for widget in self.iter_widgets():
            if widget.id == node_id:
                return widget
        return None

    def parent_of(self, node_id: str) -> Optional[Node]:
        for node in [self.window, *self.iter_widgets()]:
            if any(child.id == node_id for child in node.children):
                return node
        return None

    def is_descendant(self, node_id: str, ancestor_id: str) -> bool:
        """True, wenn node_id gleich ancestor_id ist oder darunter liegt."""
        ancestor = self.find(ancestor_id)
        if ancestor is None:
            return False
        if ancestor.id == node_id:
            return True

        def walk(node: Node) -> bool:
            return any(c.id == node_id or walk(c) for c in node.children)

        return walk(ancestor)

    def unique_name(self, prefix: str) -> str:
        used = {w.name for w in self.iter_widgets()}
        n = 1
        while f"{prefix}_{n}" in used:
            n += 1
        return f"{prefix}_{n}"
