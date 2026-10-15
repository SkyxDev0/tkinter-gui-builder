"""Gemeinsamer Zustand aller Panels: Projekt, Verlauf, Auswahl, Dateipfad."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from ctk_builder import project_io
from ctk_builder.commands import Command, CommandError, CommandStack
from ctk_builder.model import Project, new_project

Line = tuple[str, str, int]  # (container_id, "row"/"column", index)


class Session:
    def __init__(self) -> None:
        self.stack = CommandStack(new_project())
        self.path: Optional[Path] = None
        self.selected_id: str = "window"
        self.selected_line: Optional[Line] = None
        self._listeners: list[Callable[[], None]] = []
        self._selection_listeners: list[Callable[[], None]] = []
        self.on_status: Callable[[str], None] = lambda message: None
        # Gerenderte Geometrie eines Containers und seiner Kinder; die Arbeitsfläche
        # trägt sich hier ein. Ohne Arbeitsfläche: leer (Befehle schätzen dann).
        self.measurer: Callable[[str], dict] = lambda container_id: {}
        # Gemessene Größe eines neuen Widgets dieses Typs; ohne Arbeitsfläche: None
        self.probe_size: Callable[[str], Optional[tuple[int, int]]] = lambda widget_type: None
        # Vor jeder Modelländerung (Befehl, Undo/Redo, Neu/Öffnen): z. B. eine noch
        # nicht gespeicherte Pfeiltasten-Bewegung erst übernehmen
        self.before_change: list[Callable[[], None]] = []
        self._unsubscribe = self.project.subscribe(self._changed)

    # ------------------------------------------------------------ Beobachter

    @property
    def project(self) -> Project:
        return self.stack.project

    def subscribe(self, callback: Callable[[], None]) -> None:
        """callback wird nach jeder Modelländerung, Speichern und Neu/Öffnen aufgerufen."""
        self._listeners.append(callback)

    def subscribe_selection(self, callback: Callable[[], None]) -> None:
        """callback wird aufgerufen, wenn sich die Auswahl ändert."""
        self._selection_listeners.append(callback)

    def _changed(self) -> None:
        selection_reset = False
        if self.project.find(self.selected_id) is None:
            self.selected_id = "window"
            self.selected_line = None
            selection_reset = True
        elif self.selected_line is not None and not self._line_exists(self.selected_line):
            self.selected_line = None
            selection_reset = True
        for callback in list(self._listeners):
            callback()
        if selection_reset:
            self._notify_selection()

    def _notify_selection(self) -> None:
        for callback in list(self._selection_listeners):
            callback()

    def _line_exists(self, line: Line) -> bool:
        container = self.project.find(line[0])
        return (container is not None and container.is_container and not container.is_free
                and line[2] < len(container.grid.lines(line[1])))

    # ------------------------------------------------------------ Auswahl

    def select(self, node_id: str) -> None:
        self.selected_id = node_id
        self.selected_line = None
        self._notify_selection()

    def select_line(self, container_id: str, axis: str, index: int) -> None:
        self.selected_id = container_id
        self.selected_line = (container_id, axis, index)
        self._notify_selection()

    def target_container_id(self) -> str:
        """Container für neue Widgets: der ausgewählte oder dessen Eltern-Container."""
        node = self.project.find(self.selected_id)
        if node is not None and node.is_container:
            return node.id
        parent = self.project.parent_of(self.selected_id)
        return parent.id if parent is not None else "window"

    # ------------------------------------------------------------ Befehle

    def measure(self, container_id: str) -> dict:
        """Gemessene Geometrie für einen Befehl – nach offenen Änderungen (z. B. einer
        Pfeiltasten-Bewegung), damit der Befehl den aktuellen Stand sieht."""
        self._before_change()
        return self.measurer(container_id)

    def _before_change(self) -> None:
        for callback in list(self.before_change):
            callback()

    def execute(self, command: Command) -> bool:
        """Führt aus; bei CommandError Meldung in der Statusleiste, Rückgabe False."""
        self._before_change()
        try:
            self.stack.execute(command)
        except CommandError as exc:
            self.on_status(str(exc))
            return False
        return True

    def undo(self) -> None:
        self._before_change()
        self.stack.undo()

    def redo(self) -> None:
        self._before_change()
        self.stack.redo()

    # ------------------------------------------------------------ Dateien

    def replace_project(self, project: Project, path: Optional[Path]) -> None:
        self._before_change()
        self._unsubscribe()
        self.stack.reset(project)
        self._unsubscribe = project.subscribe(self._changed)
        self.path = path
        self.selected_id = "window"
        self.selected_line = None
        self._changed()
        self._notify_selection()

    def new(self) -> None:
        self.replace_project(new_project(), None)

    def open(self, path: Path) -> None:
        """Wirft project_io.ProjectFileError bei kaputter Datei."""
        self.replace_project(project_io.load(path), Path(path))

    def save(self, path: Optional[Path] = None) -> None:
        """Speichert; den Pfad übernimmt die Session erst, wenn das Schreiben klappt."""
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("Kein Speicherort gewählt")
        self._before_change()
        project_io.save(self.project, target)
        self.path = target
        self.stack.mark_saved()
        self._changed()

    @property
    def dirty(self) -> bool:
        return self.stack.dirty
