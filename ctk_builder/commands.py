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

from ctk_builder import names
from ctk_builder.model import (
    GridConfig, LineConfig, Layout, Node, Project, WidgetNode, WindowNode,
    fits, new_id, next_free_cell, occupant,
)
from ctk_builder.widget_specs import GROUP, HANDLER, SPECS


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


def _widget(project: Project, node_id: str) -> WidgetNode:
    node = project.find(node_id)
    if not isinstance(node, WidgetNode):
        raise CommandError("Widget nicht gefunden")
    return node


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
                 row: Optional[int] = None, column: Optional[int] = None):
        super().__init__()
        self.parent_id = parent_id
        self.widget_type = widget_type
        self.row = row
        self.column = column
        self.node_id = new_id()  # bleibt bei Redo gleich, damit Auswahl passt

    def apply(self, project: Project) -> None:
        spec = SPECS[self.widget_type]
        parent = _container(project, self.parent_id)
        if self.row is None or self.column is None:
            row, column = next_free_cell(parent)
        else:
            row, column = self.row, self.column
        _grow_to(parent, row, column)
        if occupant(parent, row, column) is not None:
            raise CommandError("Zelle ist schon belegt")
        node = WidgetNode(
            id=self.node_id,
            type=spec.type,
            name=project.unique_name(spec.prefix),
            props=dict(spec.initial),
            layout=Layout(row=row, column=column),
            grid=GridConfig() if spec.is_container else None,
        )
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
    """Verschiebt ein Widget in eine Zelle; belegte Zelle -> Tausch."""

    description = "Widget verschieben"

    def __init__(self, node_id: str, parent_id: str, row: int, column: int):
        super().__init__()
        self.node_id = node_id
        self.parent_id = parent_id
        self.row = row
        self.column = column

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        target = _container(project, self.parent_id)
        if project.is_descendant(self.parent_id, self.node_id):
            raise CommandError("Ein Frame kann nicht in sich selbst verschoben werden")
        source = project.parent_of(self.node_id)
        _grow_to(target, self.row, self.column)
        other = occupant(target, self.row, self.column, frozenset({node.id}))
        old_layout = copy.copy(node.layout)
        source.children.remove(node)

        if other is not None:
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

    def __init__(self, node_id: str):
        super().__init__()
        self.node_id = node_id
        self.new_node_id: Optional[str] = None

    def apply(self, project: Project) -> None:
        node = _widget(project, self.node_id)
        parent = project.parent_of(self.node_id)
        taken = {w.name for w in project.iter_widgets()}
        clone = _copy_with_new_ids(project, node, taken)
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
        if not fits(parent, layout, frozenset({node.id})):
            raise CommandError("Layout überdeckt ein anderes Widget oder liegt außerhalb")
        node.layout = layout


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
        container = _container(project, self.container_id)
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
        container = _container(project, self.container_id)
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
        container = _container(project, self.container_id)
        lines = container.grid.lines(self.axis)
        if not 0 <= self.index < len(lines):
            raise CommandError("Position außerhalb des Grids")
        if self.config.weight < 0 or self.config.minsize < 0:
            raise CommandError("weight/minsize dürfen nicht negativ sein")
        if self.config.uniform and not self.config.uniform.isidentifier():
            raise CommandError("uniform muss ein einfacher Name sein")
        lines[self.index] = copy.copy(self.config)
