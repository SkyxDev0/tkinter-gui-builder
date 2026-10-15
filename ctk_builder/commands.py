"""Alle Modelländerungen als Befehle mit Undo/Redo.

Jeder Befehl merkt sich den Fensterbaum vor und nach der Ausführung
(Schnappschuss per deepcopy). Damit stellt Undo den Zustand garantiert exakt
wieder her. Ansichten dürfen sich deshalb nie Knoten-Objekte merken, sondern
nur IDs, und müssen nach jeder Änderung über project.find() neu nachschlagen.
"""

from __future__ import annotations

import copy
from dataclasses import fields
from typing import Any, Optional

from ctk_builder import geometry, names
from ctk_builder.model import (
    GRID, MANAGERS, PLACE, GridConfig, LineConfig, Layout, Node, Project, WidgetNode,
    WindowNode, fits, new_id, next_free_cell, occupant,
)
from ctk_builder.widget_specs import GROUP, HANDLER, SPECS

DUPLICATE_OFFSET = 16  # Versatz einer Kopie im freien Modus


class CommandError(Exception):
    """Befehl ist nicht ausführbar. Das Modell bleibt unverändert."""


class Command:
    description = "Änderung"

    def __init__(self) -> None:
        self._before: Optional[WindowNode] = None
        self._after: Optional[WindowNode] = None

    def apply(self, project: Project) -> None:
        """Ändert project.window. Bei Fehler CommandError werfen."""
        raise NotImplementedError

    def do(self, project: Project) -> None:
        if self._after is not None:  # Redo
            project.window = copy.deepcopy(self._after)
            return
        self._before = copy.deepcopy(project.window)
        try:
            self.apply(project)
        except Exception:
            project.window = self._before
            self._before = None
            raise
        self._after = copy.deepcopy(project.window)

    def undo(self, project: Project) -> None:
        project.window = copy.deepcopy(self._before)


class CommandStack:
    def __init__(self, project: Project):
        self.project = project
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._saved_at: Optional[int] = 0  # len(_undo) beim letzten Speichern

    def execute(self, command: Command) -> None:
        command.do(self.project)
        if self._saved_at is not None and self._saved_at > len(self._undo):
            self._saved_at = None  # gespeicherter Zustand ist nicht mehr erreichbar
        self._undo.append(command)
        self._redo.clear()
        self.project.notify()

    def undo(self) -> None:
        if not self._undo:
            return
        command = self._undo.pop()
        command.undo(self.project)
        self._redo.append(command)
        self.project.notify()

    def redo(self) -> None:
        if not self._redo:
            return
        command = self._redo.pop()
        command.do(self.project)
        self._undo.append(command)
        self.project.notify()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def dirty(self) -> bool:
        return self._saved_at != len(self._undo)

    def mark_saved(self) -> None:
        self._saved_at = len(self._undo)

    def reset(self, project: Project) -> None:
        """Neues oder geladenes Projekt: Verlauf leeren."""
        self.project = project
        self._undo.clear()
        self._redo.clear()
        self._saved_at = 0


# ---------------------------------------------------------------- Hilfen

def _container(project: Project, node_id: str) -> Node:
    node = project.find(node_id)
    if node is None or not node.is_container:
        raise CommandError("Ziel ist kein Container")
    return node


def _grid_container(project: Project, node_id: str) -> Node:
    node = _container(project, node_id)
    if node.is_free:
        raise CommandError("Zeilen und Spalten gibt es nur bei der Anordnung „Raster“")
    return node


def _widget(project: Project, node_id: str) -> WidgetNode:
    node = project.find(node_id)
    if not isinstance(node, WidgetNode):
        raise CommandError("Widget nicht gefunden")
    return node


def _keep_size(frame: WidgetNode, rect: geometry.Rect) -> None:
    """Gemessene Größe eines Frames als width/height übernehmen."""
    frame.props["width"], frame.props["height"] = rect.width, rect.height


def _check_position(x: int, y: int) -> None:
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in (x, y)):
        raise CommandError("Position muss aus ganzen Zahlen >= 0 bestehen")


def _place(container: Node, node: WidgetNode, x: Optional[int], y: Optional[int],
           rects: Optional[geometry.Rects] = None, anchor: Optional[str] = None,
           size: Optional[tuple[int, int]] = None) -> None:
    """Setzt die freie Position. Eine übergebene Position gilt, wie sie ist (die
    Arbeitsfläche hat sie mit echten Größen begrenzt). Ohne Angabe: unter anchor
    bzw. dem untersten Kind, mit gemessenen Größen (rects, size), sonst geschätzt."""
    if x is None or y is None:
        if size is None:
            size = (rects[node.id].width, rects[node.id].height) \
                if rects and node.id in rects else geometry.size_hint(node)
        x, y = geometry.spot_below(container, size, anchor, frozenset({node.id}), rects)
    _check_position(x, y)
    node.layout.x, node.layout.y = x, y


def _grow_to(container: Node, row: int, column: int) -> None:
    """Hängt Zeilen/Spalten an, damit (row, column) existiert (max. eine je Achse)."""
    grid = container.grid
    if row < 0 or column < 0 or row > len(grid.rows) or column > len(grid.columns):
        raise CommandError("Zelle liegt außerhalb des Grids")
    if row == len(grid.rows):
        grid.rows.append(LineConfig())
    if column == len(grid.columns):
        grid.columns.append(LineConfig())


def _copy_with_new_ids(project: Project, node: WidgetNode,
                       taken: set[str]) -> WidgetNode:
    clone = copy.deepcopy(node)

    def renew(n: WidgetNode) -> None:
        n.id = new_id()
        prefix = SPECS[n.type].prefix
        i = 1
        while f"{prefix}_{i}" in taken:
            i += 1
        n.name = f"{prefix}_{i}"
        taken.add(n.name)
        for child in n.children:
            renew(child)

    renew(clone)
    return clone


# ---------------------------------------------------------------- Befehle

class AddWidget(Command):
    description = "Widget hinzufügen"

    def __init__(self, parent_id: str, widget_type: str,
                 row: Optional[int] = None, column: Optional[int] = None,
                 x: Optional[int] = None, y: Optional[int] = None,
                 rects: Optional[geometry.Rects] = None, anchor: Optional[str] = None,
                 size: Optional[tuple[int, int]] = None):
        """row/column gelten in Raster-Containern, x/y in freien Containern.
        Ohne Angabe: nächste freie Zelle bzw. unter dem Widget anchor (sonst unter
        dem untersten Kind). rects: gemessene Geometrie der Geschwister; size:
        gemessene Größe des neuen Widgets."""
        super().__init__()
        self.parent_id = parent_id
        self.widget_type = widget_type
        self.row = row
        self.column = column
        self.x = x
        self.y = y
        self.rects = dict(rects or {})
        self.anchor = anchor
        self.size = size
        self.node_id = new_id()  # bleibt bei Redo gleich, damit Auswahl passt

    def apply(self, project: Project) -> None:
        spec = SPECS[self.widget_type]
        parent = _container(project, self.parent_id)
        node = WidgetNode(
            id=self.node_id,
            type=spec.type,
            name=project.unique_name(spec.prefix),
            props=dict(spec.initial),
            grid=GridConfig() if spec.is_container else None,
            # neue Frames ordnen wie ihr Eltern-Container an
            manager=parent.manager if spec.is_container else None,
        )
        if parent.is_free:
            _place(parent, node, self.x, self.y, self.rects, self.anchor, self.size)
        else:
            if self.row is None or self.column is None:
                row, column = next_free_cell(parent)
            else:
                row, column = self.row, self.column
            _grow_to(parent, row, column)
            if occupant(parent, row, column) is not None:
                raise CommandError("Zelle ist schon belegt")
            node.layout = Layout(row=row, column=column)
        parent.children.append(node)


class RemoveWidget(Command):
    description = "Widget löschen"

    def __init__(self, node_id: str):
        super().__init__()
        self.node_id = node_id

    def apply(self, project: Project) -> None:
        _widget(project, self.node_id)
        parent = project.parent_of(self.node_id)
        parent.children = [c for c in parent.children if c.id != self.node_id]


class MoveWidget(Command):
    """Verschiebt ein Widget in eine Zelle (belegte Zelle -> Tausch) bzw. in einem
    freien Container an die Position x, y."""

    description = "Widget verschieben"

    def __init__(self, node_id: str, parent_id: str,
                 row: Optional[int] = None, column: Optional[int] = None,
                 x: Optional[int] = None, y: Optional[int] = None,
                 rects: Optional[geometry.Rects] = None):
        """rects: gemessene Geometrie (z. B. des verschobenen Frames)."""
        super().__init__()
        self.node_id = node_id
        self.parent_id = parent_id
        self.row = row
        self.column = column
        self.x = x
        self.y = y
        self.rects = dict(rects or {})

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        target = _container(project, self.parent_id)
        if project.is_descendant(self.parent_id, self.node_id):
            raise CommandError("Ein Frame kann nicht in sich selbst verschoben werden")
        source = project.parent_of(self.node_id)
        if target.is_free:
            index = source.children.index(node)
            source.children.remove(node)
            if node.is_container and source.is_grid and node.id in self.rects:
                _keep_size(node, self.rects[node.id])  # sonst springt er auf width/height
            _place(target, node, self.x, self.y, self.rects)
            if target is source:  # im selben Container bleibt die Stapelreihenfolge
                target.children.insert(index, node)
            else:
                target.children.append(node)
            return
        if self.row is None or self.column is None:
            raise CommandError("Zielzelle fehlt")
        _grow_to(target, self.row, self.column)
        other = occupant(target, self.row, self.column, frozenset({node.id}))
        old_layout = copy.copy(node.layout)
        source.children.remove(node)

        if other is not None:
            if source.is_free:
                raise CommandError("Zelle ist belegt")  # kein Tausch zwischen Frei und Raster
            if project.is_descendant(source.id, other.id):
                raise CommandError("Tausch nicht möglich: Ziel enthält die Quelle")
            target.children.remove(other)
            other.layout.row, other.layout.column = old_layout.row, old_layout.column
            if not fits(source, other.layout):
                raise CommandError("Tausch nicht möglich: Widgets passen nicht")
            source.children.append(other)

        node.layout.row, node.layout.column = self.row, self.column
        if not fits(target, node.layout):
            raise CommandError("Widget passt dort nicht hin")
        target.children.append(node)


class DuplicateWidget(Command):
    description = "Widget duplizieren"

    def __init__(self, node_id: str, rects: Optional[geometry.Rects] = None):
        """rects: gemessene Geometrie des Eltern-Containers und seiner Kinder."""
        super().__init__()
        self.node_id = node_id
        self.rects = dict(rects or {})
        self.new_node_id: Optional[str] = None

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        parent = project.parent_of(self.node_id)
        taken = {w.name for w in project.iter_widgets()}
        clone = _copy_with_new_ids(project, node, taken)
        if parent.is_free:
            rect = geometry.rect_of(node, self.rects)
            size = (rect.width, rect.height)
            origin = (node.layout.x, node.layout.y)
            for offset in (DUPLICATE_OFFSET, -DUPLICATE_OFFSET):
                x, y = geometry.clamp(parent, origin[0] + offset, origin[1] + offset, *size,
                                      rects=self.rects)
                if (x, y) != origin:
                    break  # am Rand nicht genau auf das Original legen
            else:
                x, y = geometry.free_spot(parent, size, rects=self.rects)
            clone.layout.x, clone.layout.y = x, y
        else:
            row, column = next_free_cell(parent)
            _grow_to(parent, row, column)
            clone.layout.row, clone.layout.column = row, column
            clone.layout.rowspan = clone.layout.columnspan = 1
        parent.children.append(clone)
        if self.new_node_id is None:
            self.new_node_id = clone.id


class RenameWidget(Command):
    description = "Umbenennen"

    def __init__(self, node_id: str, name: str):
        super().__init__()
        self.node_id = node_id
        self.name = name

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        try:
            names.check_identifier(project, names.WIDGET, self.name, node.id)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        node.name = self.name


class SetProperty(Command):
    """Setzt eine Widget-Eigenschaft; value None = Standardwert."""

    description = "Eigenschaft ändern"

    def __init__(self, node_id: str, key: str, value: Any):
        super().__init__()
        self.node_id = node_id
        self.key = key
        self.value = value

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        prop = SPECS[node.type].prop(self.key)
        if self.value is not None and prop.kind in (HANDLER, GROUP):
            kind = names.HANDLER if prop.kind == HANDLER else names.GROUP
            try:
                names.check_identifier(project, kind, self.value, node.id)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        if self.value is None:
            node.props.pop(self.key, None)
        else:
            node.props[self.key] = self.value


_LAYOUT_FIELDS = {f.name for f in fields(Layout)}


class SetLayout(Command):
    description = "Layout ändern"

    def __init__(self, node_id: str, **changes: Any):
        super().__init__()
        unknown = set(changes) - _LAYOUT_FIELDS
        if unknown:
            raise ValueError(f"Unbekannte Layout-Felder: {unknown}")
        self.node_id = node_id
        self.changes = changes

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        parent = project.parent_of(self.node_id)
        layout = copy.copy(node.layout)
        for key, value in self.changes.items():
            setattr(layout, key, value)
        if layout.rowspan < 1 or layout.columnspan < 1:
            raise CommandError("rowspan/columnspan muss mindestens 1 sein")
        if layout.padx < 0 or layout.pady < 0:
            raise CommandError("Abstand darf nicht negativ sein")
        if set(layout.sticky) - set("nsew") or len(set(layout.sticky)) != len(layout.sticky):
            raise CommandError("sticky darf nur n, s, e, w enthalten")
        layout.sticky = "".join(ch for ch in "nsew" if ch in layout.sticky)
        if "x" in self.changes or "y" in self.changes:
            _check_position(layout.x, layout.y)
        if not parent.is_free and not fits(parent, layout, frozenset({node.id})):
            raise CommandError("Layout überdeckt ein anderes Widget oder liegt außerhalb")
        node.layout = layout


class SetGeometry(Command):
    """Position und Größe auf einmal (Anfasser im freien Modus)."""

    description = "Größe ändern"

    def __init__(self, node_id: str, x: int, y: int, width: int, height: int):
        super().__init__()
        self.node_id = node_id
        self.x, self.y, self.width, self.height = x, y, width, height

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        spec = SPECS[node.type]
        if not all(any(p.name == key for p in spec.props) for key in ("width", "height")):
            raise CommandError(f"{node.type} hat keine einstellbare Größe")
        if not project.parent_of(node.id).is_free:
            raise CommandError("Größe per Anfasser nur bei der Anordnung „Frei“")
        _check_position(self.x, self.y)
        for value in (self.width, self.height):
            if not isinstance(value, int) or value < 1:
                raise CommandError("Größe muss eine positive ganze Zahl sein")
        node.layout.x, node.layout.y = self.x, self.y
        node.props["width"], node.props["height"] = self.width, self.height


class SetManager(Command):
    """Schaltet einen Container zwischen „Frei“ (place) und „Raster“ (grid) um.

    rects: auf der Arbeitsfläche gemessene Geometrie der Kinder (logische Pixel);
    ohne Messung werden Positionen bzw. Größen geschätzt. Raster -> Frei: Jedes
    Kind bleibt, wo es zu sehen war; per sticky gestreckte Widgets behalten ihre
    gestreckte Größe. Frei -> Raster: Kinder werden zeilenweise auf Zellen verteilt.
    """

    description = "Anordnung ändern"

    def __init__(self, container_id: str, manager: str,
                 rects: Optional[geometry.Rects] = None, recursive: bool = False):
        """recursive: auch alle Frames darin umstellen (ein Rückgängig-Schritt)."""
        super().__init__()
        if manager not in MANAGERS:
            raise ValueError(f"Unbekannte Anordnung {manager!r}")
        self.container_id = container_id
        self.manager = manager
        self.rects = dict(rects or {})
        self.recursive = recursive

    def apply(self, project: Project) -> None:
        container = _container(project, self.container_id)
        targets = [container]
        if self.recursive:
            targets += [w for w in project.iter_widgets()
                        if w.is_container and project.is_descendant(w.id, container.id)]
        targets = [t for t in targets if t.manager != self.manager]
        if not targets:
            raise CommandError("Diese Anordnung ist schon eingestellt")
        for target in targets:  # Messwerte stammen alle aus dem Zustand davor
            if self.manager == PLACE:
                self._to_place(target)
            else:
                self._to_grid(target)
            target.manager = self.manager

    def _to_place(self, container: Node) -> None:
        if isinstance(container, WidgetNode) and container.id in self.rects:
            # Ein Raster-Frame war so groß wie sein Inhalt; frei zählt width/height
            _keep_size(container, self.rects[container.id])
        unmeasured = [c for c in container.children if c.id not in self.rects]
        for child in container.children:
            if child.id in self.rects:
                self._keep_visible_geometry(child, self.rects[child.id])
        pending = {c.id for c in unmeasured}
        for child in unmeasured:  # ohne Messung: erste freie Stelle
            pending.discard(child.id)
            child.layout.x, child.layout.y = geometry.free_spot(
                container, geometry.size_hint(child),
                ignore=frozenset(pending | {child.id}), rects=self.rects)

    @staticmethod
    def _keep_visible_geometry(child: WidgetNode, rect: geometry.Rect) -> None:
        child.layout.x, child.layout.y = max(rect.x, 0), max(rect.y, 0)
        if child.is_container:  # frei platziert ist ein Frame so groß wie width/height
            _keep_size(child, rect)
            return
        props = {p.name for p in SPECS[child.type].props}
        sticky = child.layout.sticky
        if "width" in props and "e" in sticky and "w" in sticky:
            child.props["width"] = rect.width
        if "height" in props and "n" in sticky and "s" in sticky:
            child.props["height"] = rect.height

    def _to_grid(self, container: Node) -> None:
        """Rechnet das Layout neu (exakt zurück nur per Rückgängig)."""
        cells, rows, columns = geometry.grid_cells(container.children, self.rects)
        for child in container.children:
            for key, value in cells[child.id].items():
                setattr(child.layout, key, value)
        grid = container.grid
        # alte Zeilen-/Spalteneinstellungen passen nur, wenn die Anzahl gleich bleibt
        if len(grid.rows) != rows:
            grid.rows = [LineConfig() for _ in range(rows)]
        if len(grid.columns) != columns:
            grid.columns = [LineConfig() for _ in range(columns)]


_WINDOW_KEYS = {"class_name", "title", "width", "height", "resizable",
                "appearance_mode", "color_theme"}
_APPEARANCE_MODES = ("system", "light", "dark")
_COLOR_THEMES = ("blue", "green", "dark-blue")


class SetWindowProperty(Command):
    description = "Fenster ändern"

    def __init__(self, key: str, value: Any):
        super().__init__()
        if key not in _WINDOW_KEYS:
            raise ValueError(f"Unbekannte Fenster-Eigenschaft {key!r}")
        self.key = key
        self.value = value

    def apply(self, project: Project) -> None:
        key, value = self.key, self.value
        if key == "class_name" and not (isinstance(value, str) and value.isidentifier()):
            raise CommandError("Klassenname muss ein gültiger Python-Name sein")
        if key in ("width", "height") and not (isinstance(value, int) and value > 0):
            raise CommandError("Größe muss eine positive ganze Zahl sein")
        if key == "appearance_mode" and value not in _APPEARANCE_MODES:
            raise CommandError("Ungültiger Appearance-Mode")
        if key == "color_theme" and value not in _COLOR_THEMES:
            raise CommandError("Ungültiges Farbthema")
        setattr(project.window, key, value)


class InsertLine(Command):
    """Fügt vor index eine Zeile/Spalte ein und verschiebt nachfolgende Widgets."""

    description = "Zeile/Spalte einfügen"

    def __init__(self, container_id: str, axis: str, index: int):
        super().__init__()
        self.container_id = container_id
        self.axis = axis
        self.index = index

    def apply(self, project: Project) -> None:
        container = _grid_container(project, self.container_id)
        lines = container.grid.lines(self.axis)
        if not 0 <= self.index <= len(lines):
            raise CommandError("Position außerhalb des Grids")
        lines.insert(self.index, LineConfig())
        start, span = ("row", "rowspan") if self.axis == "row" else ("column", "columnspan")
        for child in container.children:
            first = getattr(child.layout, start)
            if first >= self.index:
                setattr(child.layout, start, first + 1)
            elif first + getattr(child.layout, span) > self.index:
                setattr(child.layout, span, getattr(child.layout, span) + 1)


class RemoveLine(Command):
    """Entfernt eine leere Zeile/Spalte."""

    description = "Zeile/Spalte löschen"

    def __init__(self, container_id: str, axis: str, index: int):
        super().__init__()
        self.container_id = container_id
        self.axis = axis
        self.index = index

    def apply(self, project: Project) -> None:
        container = _grid_container(project, self.container_id)
        lines = container.grid.lines(self.axis)
        if not 0 <= self.index < len(lines):
            raise CommandError("Position außerhalb des Grids")
        if len(lines) == 1:
            raise CommandError("Die letzte Zeile/Spalte kann nicht gelöscht werden")
        start, span = ("row", "rowspan") if self.axis == "row" else ("column", "columnspan")
        for child in container.children:
            first = getattr(child.layout, start)
            if first <= self.index < first + getattr(child.layout, span):
                raise CommandError("Zeile/Spalte ist nicht leer")
        del lines[self.index]
        for child in container.children:
            first = getattr(child.layout, start)
            if first > self.index:
                setattr(child.layout, start, first - 1)


class SetLineConfig(Command):
    description = "Zeile/Spalte konfigurieren"

    def __init__(self, container_id: str, axis: str, index: int,
                 weight: int, minsize: int, uniform: str):
        super().__init__()
        self.container_id = container_id
        self.axis = axis
        self.index = index
        self.config = LineConfig(weight=weight, minsize=minsize, uniform=uniform)

    def apply(self, project: Project) -> None:
        container = _grid_container(project, self.container_id)
        lines = container.grid.lines(self.axis)
        if not 0 <= self.index < len(lines):
            raise CommandError("Position außerhalb des Grids")
        if self.config.weight < 0 or self.config.minsize < 0:
            raise CommandError("weight/minsize dürfen nicht negativ sein")
        if self.config.uniform and not self.config.uniform.isidentifier():
            raise CommandError("uniform muss ein einfacher Name sein")
        lines[self.index] = copy.copy(self.config)


RESTACK = {
    "front": "Ganz nach vorne", "forward": "Nach vorne",
    "backward": "Nach hinten", "back": "Ganz nach hinten",
}


class Restack(Command):
    """Ändert die Stapelreihenfolge im Container (später = oben).

    Die Reihenfolge ist auch die im exportierten Code und damit die Tab-Reihenfolge.
    """

    def __init__(self, node_id: str, where: str):
        super().__init__()
        if where not in RESTACK:
            raise ValueError(f"Unbekannte Richtung {where!r}")
        self.node_id = node_id
        self.where = where
        self.description = RESTACK[where]

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        siblings = project.parent_of(node.id).children
        index = siblings.index(node)
        new = {"front": len(siblings) - 1, "back": 0,
               "forward": min(index + 1, len(siblings) - 1),
               "backward": max(index - 1, 0)}[self.where]
        if new == index:
            raise CommandError("Liegt schon " + ("ganz oben" if self.where in ("front", "forward")
                                                 else "ganz unten"))
        siblings.insert(new, siblings.pop(index))
