# CTk Builder – Plan 2: Oberfläche Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine benutzbare Desktop-App: Palette, Strukturbaum, Eigenschaften-Panel, Arbeitsfläche mit echten CTk-Widgets (Klick = Auswahl), Speichern/Öffnen, Export und „▶ Ausführen“.

**Architecture:** `Session` bündelt Projekt, Befehlsverlauf, Auswahl und Dateipfad; alle Panels beobachten die Session und ändern das Modell nur über Befehle. Die Arbeitsfläche rendert das Modell bei jeder Änderung neu und fängt Klicks über ein vorangestelltes Bindtag ab. Interaktives Raster und Drag & Drop folgen in Plan 3 (Hooks sind schon da).

**Tech Stack:** Python 3.12+, customtkinter 6.x, tkinter/ttk, pytest

---

## Umgebung

- Arbeitsverzeichnis ist die Wurzel des Repos `tkinter-gui-builder`.
- Alle Befehle nutzen das Virtualenv `.venv` (siehe Plan 1, Task 1).
- **macOS:** Tests laufen direkt; Oberflächentests öffnen kurz echte Fenster.
- **Linux ohne Display (z. B. Claude Code im Browser/Cloud):** Oberflächentests mit
  `xvfb-run -a .venv/bin/pytest …` ausführen. Ohne Display werden sie übersprungen –
  das zählt **nicht** als bestanden; dann `xvfb` installieren (`sudo apt-get install -y xvfb python3-tk`).
- Spezifikation: `docs/superpowers/specs/2026-10-13-ctk-gui-builder-design.md`.

**Voraussetzung:** Plan 1 ist umgesetzt (`.venv/bin/pytest` → 107 passed).

## Dateistruktur nach diesem Plan

```
ctk_builder/
  __main__.py          # python -m ctk_builder
  session.py           # Projekt + Verlauf + Auswahl + Dateipfad, Beobachter
  runner.py            # exportiertes Programm als Unterprozess starten
  settings.py          # ~/.ctk_builder.json (Python-Interpreter)
  ui/
    __init__.py
    palette.py         # Widget-Knöpfe (Klick = in nächste freie Zelle einfügen)
    structure_tree.py  # ttk.Treeview im CTk-Look
    properties.py      # Eigenschaften für Widget / Fenster / Zeile-Spalte
    canvas.py          # Arbeitsfläche mit echten Widgets
    output_console.py  # Ausgabe des gestarteten Programms
    main_window.py     # setzt alles zusammen, Menüs, Tastenkürzel
```

**Bekannte Einschränkungen (gewollt, V1):**
- Die Vorschau nutzt Appearance-Mode und Farbthema des Builders, nicht die des
  entworfenen Fensters (beides ist in CustomTkinter global). „▶ Ausführen“ zeigt das echte Ergebnis.
- Tastatur-Events in Tests gehen nur an das fokussierte Widget; `type_into()` in `conftest.py` fokussiert daher zuerst.
- `CTkScrollableFrame` hat ein internes Attribut `_label` – eigene Hilfsmethoden in Unterklassen
  nie `_label` nennen (daher `_field_label` in `properties.py`).

---

### Task 1: Session

Gemeinsamer Zustand aller Panels. `subscribe()` meldet Modelländerungen (inkl. Speichern, Neu, Öffnen), `subscribe_selection()` Auswahländerungen. Verschwindet der ausgewählte Knoten (z. B. nach Undo), springt die Auswahl auf das Fenster. `execute()` fängt `CommandError` ab und meldet ihn über `on_status`.

**Files:**
- Create: `ctk_builder/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_session.py`:

```python
import pytest

from conftest import build_kontakt
from ctk_builder.commands import AddWidget, RemoveWidget
from ctk_builder.project_io import ProjectFileError
from ctk_builder.session import Session


@pytest.fixture
def session():
    return Session()


def test_execute_success_and_failure(session):
    messages = []
    session.on_status = messages.append
    assert session.execute(AddWidget("window", "CTkLabel", 0, 0))
    assert not session.execute(AddWidget("window", "CTkLabel", 0, 0))
    assert messages == ["Zelle ist schon belegt"]


def test_model_listeners_called(session):
    calls = []
    session.subscribe(lambda: calls.append("model"))
    session.subscribe_selection(lambda: calls.append("selection"))
    session.execute(AddWidget("window", "CTkLabel"))
    assert calls == ["model"]
    session.select("window")
    assert calls == ["model", "selection"]


def test_selection_resets_when_node_disappears(session):
    command = AddWidget("window", "CTkLabel")
    session.execute(command)
    session.select(command.node_id)
    calls = []
    session.subscribe_selection(lambda: calls.append(1))
    session.execute(RemoveWidget(command.node_id))
    assert session.selected_id == "window"
    assert calls == [1]


def test_line_selection(session):
    session.select_line("window", "column", 0)
    assert session.selected_id == "window"
    assert session.selected_line == ("window", "column", 0)
    session.select("window")
    assert session.selected_line is None


def test_target_container(session):
    frame = AddWidget("window", "CTkFrame")
    session.execute(frame)
    label = AddWidget(frame.node_id, "CTkLabel")
    session.execute(label)
    assert session.target_container_id() == "window"
    session.select(frame.node_id)
    assert session.target_container_id() == frame.node_id
    session.select(label.node_id)
    assert session.target_container_id() == frame.node_id


def test_save_open_new(tmp_path, session):
    session.replace_project(build_kontakt(), None)
    assert not session.dirty
    session.execute(AddWidget("window", "CTkLabel"))
    assert session.dirty
    with pytest.raises(ValueError):
        session.save()
    path = tmp_path / "k.ctkb.json"
    session.save(path)
    assert not session.dirty
    assert session.path == path

    calls = []
    session.subscribe(lambda: calls.append(1))
    session.new()
    assert session.path is None
    assert session.project.window.children == []
    session.open(path)
    assert session.path == path
    assert len(list(session.project.iter_widgets())) == 10
    assert len(calls) == 2
    # Nach dem Öffnen hängen Beobachter am neuen Projekt
    session.execute(AddWidget("window", "CTkLabel"))
    assert len(calls) == 3


def test_open_broken_file_keeps_project(tmp_path, session):
    path = tmp_path / "kaputt.ctkb.json"
    path.write_text("{", encoding="utf-8")
    session.execute(AddWidget("window", "CTkLabel"))
    with pytest.raises(ProjectFileError):
        session.open(path)
    assert len(list(session.project.iter_widgets())) == 1
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_session.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.session'`

- [ ] **Step 3: Implementierung schreiben**

Datei `ctk_builder/session.py`:

```python
"""Gemeinsamer Zustand aller Panels: Projekt, Verlauf, Auswahl, Dateipfad."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from ctk_builder import project_io
from ctk_builder.commands import Command, CommandError, CommandStack
from ctk_builder.model import Project

Line = tuple[str, str, int]  # (container_id, "row"/"column", index)


class Session:
    def __init__(self) -> None:
        self.stack = CommandStack(Project())
        self.path: Optional[Path] = None
        self.selected_id: str = "window"
        self.selected_line: Optional[Line] = None
        self._listeners: list[Callable[[], None]] = []
        self._selection_listeners: list[Callable[[], None]] = []
        self.on_status: Callable[[str], None] = lambda message: None
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
        return (container is not None and container.is_container
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

    def execute(self, command: Command) -> bool:
        """Führt aus; bei CommandError Meldung in der Statusleiste, Rückgabe False."""
        try:
            self.stack.execute(command)
        except CommandError as exc:
            self.on_status(str(exc))
            return False
        return True

    def undo(self) -> None:
        self.stack.undo()

    def redo(self) -> None:
        self.stack.redo()

    # ------------------------------------------------------------ Dateien

    def replace_project(self, project: Project, path: Optional[Path]) -> None:
        self._unsubscribe()
        self.stack.reset(project)
        self._unsubscribe = project.subscribe(self._changed)
        self.path = path
        self.selected_id = "window"
        self.selected_line = None
        self._changed()
        self._notify_selection()

    def new(self) -> None:
        self.replace_project(Project(), None)

    def open(self, path: Path) -> None:
        """Wirft project_io.ProjectFileError bei kaputter Datei."""
        self.replace_project(project_io.load(path), Path(path))

    def save(self, path: Optional[Path] = None) -> None:
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("Kein Speicherort gewählt")
        project_io.save(self.project, self.path)
        self.stack.mark_saved()
        self._changed()

    @property
    def dirty(self) -> bool:
        return self.stack.dirty
```

- [ ] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_session.py -v`

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ctk_builder/session.py tests/test_session.py
git commit -m "feat: Session mit Auswahl und Dateiverwaltung"
```


### Task 2: Prozess-Runner und Einstellungen

**Files:**
- Create: `ctk_builder/runner.py`
- Create: `ctk_builder/settings.py`
- Test: `tests/test_runner_settings.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_runner_settings.py`:

```python
import sys
import time

from ctk_builder.runner import ProcessRunner
from ctk_builder.settings import Settings


def collect(runner: ProcessRunner, until: str, timeout: float = 10.0) -> str:
    text = ""
    deadline = time.monotonic() + timeout
    while until not in text and time.monotonic() < deadline:
        text += runner.drain()
        time.sleep(0.05)
    return text


def test_runner_captures_output_and_exit_code(tmp_path):
    script = tmp_path / "hallo.py"
    script.write_text("import sys\nprint('hallo')\nsys.exit(3)\n", encoding="utf-8")
    runner = ProcessRunner()
    runner.start(sys.executable, script)
    text = collect(runner, "beendet")
    assert "hallo" in text
    assert "Code 3" in text
    assert not runner.running


def test_runner_stop(tmp_path):
    script = tmp_path / "endlos.py"
    script.write_text("import time\nprint('start', flush=True)\ntime.sleep(60)\n",
                      encoding="utf-8")
    runner = ProcessRunner()
    runner.start(sys.executable, script)
    collect(runner, "start")
    assert runner.running
    runner.stop()
    assert not runner.running


def test_settings_default_and_persist(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(path)
    assert settings.interpreter == sys.executable
    settings.interpreter = "/usr/bin/python3"
    assert Settings(path).interpreter == "/usr/bin/python3"


def test_settings_broken_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("kaputt", encoding="utf-8")
    assert Settings(path).interpreter == sys.executable
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_runner_settings.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.runner'`

- [ ] **Step 3: Runner implementieren**

Ein Hintergrund-Thread liest stdout/stderr zeilenweise in eine Queue; die Oberfläche holt sie per `drain()` ab (Tkinter darf nur im Hauptthread angefasst werden).

Datei `ctk_builder/runner.py`:

```python
"""Startet das exportierte Programm als eigenen Prozess und sammelt die Ausgabe."""

from __future__ import annotations

import queue
import subprocess
import threading
from pathlib import Path
from typing import Optional


class ProcessRunner:
    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None
        self.output: "queue.Queue[str]" = queue.Queue()

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, interpreter: str, script: Path) -> None:
        """Beendet einen noch laufenden Prozess und startet script neu."""
        self.stop()
        script = Path(script)
        self.process = subprocess.Popen(
            [interpreter, "-u", script.name],
            cwd=script.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        threading.Thread(target=self._pump, args=(self.process,), daemon=True).start()

    def _pump(self, process: subprocess.Popen) -> None:
        for line in process.stdout:
            self.output.put(line)
        code = process.wait()
        self.output.put(f"[Prozess beendet mit Code {code}]\n")

    def stop(self) -> None:
        if self.running:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def drain(self) -> str:
        """Holt alle bisher gesammelten Ausgabezeilen ab."""
        lines = []
        while True:
            try:
                lines.append(self.output.get_nowait())
            except queue.Empty:
                return "".join(lines)
```

- [ ] **Step 4: Einstellungen implementieren**

Datei `ctk_builder/settings.py`:

```python
"""Builder-Einstellungen (z. B. Python-Interpreter) in ~/.ctk_builder.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path.home() / ".ctk_builder.json"


class Settings:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError):
            pass  # fehlende oder kaputte Einstellungen -> Standardwerte

    @property
    def interpreter(self) -> str:
        return self.data.get("interpreter") or sys.executable

    @interpreter.setter
    def interpreter(self, value: str) -> None:
        self.data["interpreter"] = value
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 5: Tests ausführen**

Run: `.venv/bin/pytest tests/test_runner_settings.py -v`

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add ctk_builder/runner.py ctk_builder/settings.py tests/test_runner_settings.py
git commit -m "feat: Prozess-Runner und Builder-Einstellungen"
```


### Task 3: UI-Test-Hilfen und Palette

**Files:**
- Modify: `tests/conftest.py` (am Ende anhängen)
- Create: `ctk_builder/ui/__init__.py` (leer)
- Create: `ctk_builder/ui/palette.py`
- Test: `tests/test_ui_palette.py`

- [ ] **Step 1: Test-Hilfen an `tests/conftest.py` anhängen**

Die Fixtures `app` und `canvas` importieren Module, die erst in späteren Tasks entstehen – das ist in Ordnung, weil die Importe innerhalb der Fixtures stehen. `click()` erzeugt zuerst `<Enter>`, weil `CTkButton` den Befehl nur auslöst, wenn die Maus „drin“ ist.

An das Ende von `tests/conftest.py` anhängen:

```python
@pytest.fixture
def root():
    """Ein CTk-Hauptfenster für Panel-Tests."""
    if not has_display():
        pytest.skip("kein Display verfügbar")
    import customtkinter as ctk

    window = ctk.CTk()
    yield window
    window.destroy()


@pytest.fixture
def app(tmp_path):
    """Komplettes Builder-Fenster mit dem Kontakt-Beispielprojekt."""
    if not has_display():
        pytest.skip("kein Display verfügbar")
    from ctk_builder.session import Session
    from ctk_builder.settings import Settings
    from ctk_builder.ui.main_window import MainWindow

    session = Session()
    session.replace_project(build_kontakt(), None)
    window = MainWindow(session, Settings(tmp_path / "settings.json"))
    window.update()
    yield window
    window.runner.stop()
    window.destroy()


@pytest.fixture
def canvas(root):
    """Arbeitsfläche allein, mit dem Kontakt-Beispielprojekt."""
    from ctk_builder.session import Session
    from ctk_builder.ui.canvas import DesignCanvas

    session = Session()
    session.replace_project(build_kontakt(), None)
    root.geometry("800x600")
    design = DesignCanvas(root, session)
    design.pack(fill="both", expand=True)
    root.update()
    return design


def node_named(session, name):
    return next(w for w in session.project.iter_widgets() if w.name == name)


def click(widget, x=3, y=3):
    """Simuliert einen Mausklick (Enter, Drücken, Loslassen) auf ein Tk-Widget."""
    root_x, root_y = widget.winfo_rootx() + x, widget.winfo_rooty() + y
    widget.event_generate("<Enter>", x=x, y=y)
    widget.event_generate("<Button-1>", x=x, y=y, rootx=root_x, rooty=root_y)
    widget.event_generate("<ButtonRelease-1>", x=x, y=y, rootx=root_x, rooty=root_y)
    widget.update()


def type_into(entry, text):
    """Ersetzt den Inhalt eines CTkEntry und bestätigt mit Enter.

    CTkEntry leitet bind() an das innere tkinter.Entry (_entry) weiter, und
    Tastaturereignisse gehen an das Widget mit Fokus – daher erst fokussieren.
    """
    entry.delete(0, "end")
    entry.insert(0, text)
    entry._entry.focus_force()
    entry.update()
    entry._entry.event_generate("<Return>")
    entry.update()
```

- [ ] **Step 2: Failing Test schreiben**

Datei `tests/test_ui_palette.py`:

```python
from conftest import click
from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui.palette import Palette
from ctk_builder.widget_specs import SPECS


def test_palette_click_adds_and_selects(root):
    session = Session()
    palette = Palette(root, session)
    palette.pack()
    root.update()
    assert set(palette.buttons) == set(SPECS)
    click(palette.buttons["CTkButton"].winfo_children()[0])
    widgets = list(session.project.iter_widgets())
    assert [w.name for w in widgets] == ["button_1"]
    assert session.selected_id == widgets[0].id


def test_palette_adds_into_selected_frame(root):
    session = Session()
    palette = Palette(root, session)
    frame = AddWidget("window", "CTkFrame")
    session.execute(frame)
    session.select(frame.node_id)
    palette.add("CTkLabel")
    assert session.project.find(frame.node_id).children[0].name == "label_1"
```

- [ ] **Step 3: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_palette.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.ui'`

- [ ] **Step 4: Paket anlegen**

```bash
touch ctk_builder/ui/__init__.py
```

- [ ] **Step 5: Palette implementieren**

Abweichung von der Spezifikation: Ein **einfacher Klick** (statt Doppelklick) fügt ein. In Plan 3 wird Ziehen ergänzt; ein Klick ohne Bewegung bleibt Einfügen.

Datei `ctk_builder/ui/palette.py`:

```python
"""Widget-Palette: ein Knopf pro Widget-Typ."""

from __future__ import annotations

import customtkinter as ctk

from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.widget_specs import SPECS


class Palette(ctk.CTkFrame):
    def __init__(self, master, session: Session):
        super().__init__(master)
        self.session = session
        ctk.CTkLabel(self, text="Widgets", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4))
        self.buttons: dict[str, ctk.CTkButton] = {}
        for widget_type in SPECS:
            button = ctk.CTkButton(
                self, text=widget_type.removeprefix("CTk"), height=26, anchor="w",
                command=lambda t=widget_type: self.add(t),
            )
            button.pack(fill="x", padx=8, pady=2)
            self.buttons[widget_type] = button

    def add(self, widget_type: str) -> None:
        """Fügt in die nächste freie Zelle des Ziel-Containers ein und wählt aus."""
        command = AddWidget(self.session.target_container_id(), widget_type)
        if self.session.execute(command):
            self.session.select(command.node_id)
```

- [ ] **Step 6: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_palette.py -v`

Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py ctk_builder/ui/__init__.py ctk_builder/ui/palette.py tests/test_ui_palette.py
git commit -m "feat: Widget-Palette"
```


### Task 4: Strukturbaum

CustomTkinter hat kein Baum-Widget, daher `ttk.Treeview` mit eigenem Style. Die Baum-IDs (`iid`) sind die Knoten-IDs. `<<TreeviewSelect>>` wird von Tk verzögert ausgelöst – deshalb vergleicht `_on_select` mit der aktuellen Auswahl, statt sich nur auf `_updating` zu verlassen.

**Files:**
- Create: `ctk_builder/ui/structure_tree.py`
- Test: `tests/test_ui_tree.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_ui_tree.py`:

```python
from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui.structure_tree import StructureTree


def test_tree_mirrors_model_and_selection(root):
    session = Session()
    tree = StructureTree(root, session)
    tree.pack()
    frame = AddWidget("window", "CTkFrame")
    session.execute(frame)
    label = AddWidget(frame.node_id, "CTkLabel")
    session.execute(label)
    assert tree.tree.get_children("window") == (frame.node_id,)
    assert tree.tree.get_children(frame.node_id) == (label.node_id,)
    assert "label_1" in tree.tree.item(label.node_id, "text")

    session.select(label.node_id)
    assert tree.tree.selection() == (label.node_id,)

    tree.tree.selection_set(frame.node_id)
    root.update()  # <<TreeviewSelect>> wird verzögert ausgelöst
    assert session.selected_id == frame.node_id
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_tree.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.ui.structure_tree'`

- [ ] **Step 3: Implementierung schreiben**

Datei `ctk_builder/ui/structure_tree.py`:

```python
"""Strukturbaum aller Widgets (ttk.Treeview im CTk-Look)."""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

from ctk_builder.model import Node
from ctk_builder.session import Session

DARK = {"bg": "#2b2b2b", "fg": "#dce4ee", "sel": "#1f6aa5"}
LIGHT = {"bg": "#f2f2f2", "fg": "#1a1a1a", "sel": "#3a7ebf"}


def node_label(node: Node) -> str:
    if node.id == "window":
        return f"Fenster ({node.title})"
    return f"{node.name}  ·  {node.type.removeprefix('CTk')}"


class StructureTree(ctk.CTkFrame):
    def __init__(self, master, session: Session):
        super().__init__(master)
        self.session = session
        self._updating = False
        ctk.CTkLabel(self, text="Struktur", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4))
        self._style()
        self.tree = ttk.Treeview(self, show="tree", selectmode="browse",
                                 style="Builder.Treeview")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        session.subscribe(self.refresh)
        session.subscribe_selection(self._show_selection)
        self.refresh()

    def _style(self) -> None:
        colors = DARK if ctk.get_appearance_mode() == "Dark" else LIGHT
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Builder.Treeview", background=colors["bg"],
                        fieldbackground=colors["bg"], foreground=colors["fg"],
                        borderwidth=0, rowheight=24)
        style.map("Builder.Treeview",
                  background=[("selected", colors["sel"])],
                  foreground=[("selected", "#ffffff")])

    def refresh(self) -> None:
        self._updating = True
        try:
            self.tree.delete(*self.tree.get_children())
            window = self.session.project.window
            self.tree.insert("", "end", iid=window.id, text=node_label(window), open=True)

            def insert(parent: Node) -> None:
                for child in parent.children:
                    self.tree.insert(parent.id, "end", iid=child.id,
                                     text=node_label(child), open=True)
                    insert(child)

            insert(window)
        finally:
            self._updating = False
        self._show_selection()

    def _show_selection(self) -> None:
        node_id = self.session.selected_id
        if not self.tree.exists(node_id) or self.tree.selection() == (node_id,):
            return
        self._updating = True
        try:
            self.tree.selection_set(node_id)
            self.tree.see(node_id)
        finally:
            self._updating = False

    def _on_select(self, _event=None) -> None:
        if self._updating:
            return
        selection = self.tree.selection()
        if selection and selection[0] != self.session.selected_id:
            self.session.select(selection[0])
```

- [ ] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_tree.py -v`

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add ctk_builder/ui/structure_tree.py tests/test_ui_tree.py
git commit -m "feat: Strukturbaum"
```


### Task 5: Eigenschaften-Panel

Wird bei jeder Modell- oder Auswahländerung komplett neu aufgebaut. Eingabefelder übernehmen bei Enter oder Fokusverlust; ungültige Eingaben färben den Rahmen rot, zeigen die Meldung in der Statusleiste und ändern das Modell nicht. Farbnamen werden zusätzlich über `winfo_rgb` gegen Tk geprüft.

**Files:**
- Create: `ctk_builder/ui/properties.py`
- Test: `tests/test_ui_properties.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_ui_properties.py`:

```python
from conftest import type_into
from ctk_builder.commands import AddWidget
from ctk_builder.session import Session
from ctk_builder.ui.properties import ERROR_BORDER, PropertiesPanel


def test_properties_widget_fields(root):
    session = Session()
    panel = PropertiesPanel(root, session)
    panel.pack()
    button = AddWidget("window", "CTkButton")
    session.execute(button)
    session.select(button.node_id)
    assert panel.fields["name"].get() == "button_1"
    assert panel.fields["text"].get() == "Button"
    assert panel.fields["state"].get() == "normal"
    assert "sticky_n" in panel.fields

    type_into(panel.fields["text"], "Speichern")
    assert session.project.find(button.node_id).props["text"] == "Speichern"


def test_properties_invalid_value_marks_field(root):
    session = Session()
    messages = []
    session.on_status = messages.append
    panel = PropertiesPanel(root, session)
    panel.pack()
    button = AddWidget("window", "CTkButton")
    session.execute(button)
    session.select(button.node_id)
    entry = panel.fields["width"]
    type_into(entry, "breit")
    assert entry.cget("border_color") == ERROR_BORDER
    assert messages
    assert "width" not in session.project.find(button.node_id).props


def test_properties_layout_and_sticky(root):
    session = Session()
    panel = PropertiesPanel(root, session)
    panel.pack()
    label = AddWidget("window", "CTkLabel")
    session.execute(label)
    session.select(label.node_id)
    type_into(panel.fields["padx"], "6")
    panel.fields["sticky_e"].toggle()
    layout = session.project.find(label.node_id).layout
    assert layout.padx == 6
    assert layout.sticky == "e"


def test_properties_window_and_line(root):
    session = Session()
    panel = PropertiesPanel(root, session)
    panel.pack()
    assert panel.fields["title"].get() == "App"
    panel.fields["appearance_mode"].set("dark")
    panel.fields["appearance_mode"]._command("dark")  # Auswahl wie per Maus
    assert session.project.window.appearance_mode == "dark"

    session.select_line("window", "column", 0)
    type_into(panel.fields["weight"], "2")
    assert session.project.window.grid.columns[0].weight == 2
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_properties.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.ui.properties'`

- [ ] **Step 3: Implementierung schreiben**

Datei `ctk_builder/ui/properties.py`:

```python
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
from ctk_builder.widget_specs import CHOICE, SPECS, format_value, parse_value

ERROR_BORDER = "#d9534f"


class PropertiesPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, session: Session):
        super().__init__(master, label_text="Eigenschaften")
        self.session = session
        self.grid_columnconfigure(1, weight=1)
        self.fields: dict[str, ctk.CTkBaseClass] = {}  # für Tests: Feldname -> Widget
        self._rebuilding = False
        self._row = 0
        session.subscribe(self.rebuild)
        session.subscribe_selection(self.rebuild)
        self.rebuild()

    # ------------------------------------------------------------ Aufbau

    def rebuild(self) -> None:
        self._rebuilding = True
        try:
            for child in self.winfo_children():
                child.destroy()
            self.fields.clear()
            self._row = 0
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

    def _heading(self, text: str) -> None:
        ctk.CTkLabel(self, text=text, font=ctk.CTkFont(weight="bold")).grid(
            row=self._row, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self._row += 1

    def _field_label(self, text: str) -> None:
        ctk.CTkLabel(self, text=text, anchor="w").grid(
            row=self._row, column=0, sticky="w", padx=(0, 8), pady=2)

    def _entry(self, key: str, label: str, value: str,
               commit: Callable[[str], Optional[Command]]) -> ctk.CTkEntry:
        """Eingabefeld; commit wandelt Text in Befehl (ValueError = ungültig)."""
        self._field_label(label)
        entry = ctk.CTkEntry(self)
        entry.insert(0, value)
        entry.grid(row=self._row, column=1, sticky="ew", pady=2)
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
                make: Callable[[str], Command]) -> ctk.CTkOptionMenu:
        self._field_label(label)
        menu = ctk.CTkOptionMenu(
            self, values=list(choices),
            command=lambda chosen: self.session.execute(make(chosen)),
        )
        menu.set(value)
        menu.grid(row=self._row, column=1, sticky="ew", pady=2)
        self.fields[key] = menu
        self._row += 1
        return menu

    def _check(self, key: str, label: str, value: bool,
               make: Callable[[bool], Command]) -> ctk.CTkCheckBox:
        variable = tkinter.BooleanVar(self, value=value)
        box = ctk.CTkCheckBox(
            self, text=label, variable=variable,
            command=lambda: self.session.execute(make(variable.get())),
        )
        box.grid(row=self._row, column=0, columnspan=2, sticky="w", pady=2)
        self.fields[key] = box
        self._row += 1
        return box

    # ------------------------------------------------------------ Widget

    def _build_widget(self, node: WidgetNode) -> None:
        spec = SPECS[node.type]
        self._heading(node.type)
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
        self._heading("Layout")
        layout = node.layout
        for key in ("row", "column", "rowspan", "columnspan", "padx", "pady"):
            self._entry(key, key, str(getattr(layout, key)),
                        lambda text, k=key: SetLayout(node.id, **{k: _int(k, text)}))
        self._field_label("sticky")
        boxes = ctk.CTkFrame(self, fg_color="transparent")
        boxes.grid(row=self._row, column=1, sticky="w", pady=2)
        for i, side in enumerate("nsew"):
            variable = tkinter.BooleanVar(self, value=side in layout.sticky)

            def toggle(side=side, variable=variable) -> None:
                sticky = layout.sticky.replace(side, "")
                if variable.get():
                    sticky += side
                self.session.execute(SetLayout(node.id, sticky=sticky))

            box = ctk.CTkCheckBox(boxes, text=side.upper(), width=48,
                                  variable=variable, command=toggle)
            box.grid(row=0, column=i)
            self.fields[f"sticky_{side}"] = box
        self._row += 1

    # ------------------------------------------------------------ Fenster

    def _build_window(self, window: WindowNode) -> None:
        self._heading("Fenster")
        self._entry("class_name", "Klassenname", window.class_name,
                    lambda text: SetWindowProperty("class_name", text.strip()))
        self._entry("title", "Titel", window.title,
                    lambda text: SetWindowProperty("title", text))
        for key, label in (("width", "Breite"), ("height", "Höhe")):
            self._entry(key, label, str(getattr(window, key)),
                        lambda text, k=key: SetWindowProperty(k, _int(k, text)))
        self._check("resizable", "Größe veränderbar", window.resizable,
                    lambda value: SetWindowProperty("resizable", value))
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
        owner = "Fenster" if container_id == "window" else container.name
        self._heading(f"{'Zeile' if axis == 'row' else 'Spalte'} {index} · {owner}")

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
```

- [ ] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_properties.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add ctk_builder/ui/properties.py tests/test_ui_properties.py
git commit -m "feat: Eigenschaften-Panel für Widget, Fenster und Zeilen/Spalten"
```


### Task 6: Arbeitsfläche

Rendert das entworfene Fenster als `CTkFrame` (`surface`, feste Größe) mit echten CTk-Widgets im echten `grid()`. Klicks werden abgefangen: Jedes interne Tk-Teil-Widget bekommt `design-<id>` als **ersten** Bindtag; dessen Handler wählt aus und liefert `"break"`, sodass CTk-eigene Handler (Button-Befehl, Eingabefokus) nie laufen. Leere Zeilen/Spalten bekommen nur im Builder `minsize=40`. Die Hooks `after_render`, `on_press`, `on_motion`, `on_release` und `node_at()` werden in Plan 3 genutzt.

**Files:**
- Create: `ctk_builder/ui/canvas.py`
- Test: `tests/test_ui_canvas.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_ui_canvas.py`:

```python
from conftest import click, node_named
from ctk_builder.commands import AddWidget
from ctk_builder.ui.canvas import widget_kwargs


def test_widget_kwargs_skip_defaults_and_code_only_props(canvas):
    button = node_named(canvas.session, "button_save")
    kwargs = widget_kwargs(button)
    assert kwargs["text"] == "Speichern"
    assert "command" not in kwargs
    assert "font" in kwargs
    radio = node_named(canvas.session, "radio_ja")
    assert "variable_group" not in widget_kwargs(radio)
    assert "value" not in widget_kwargs(radio)


def test_canvas_renders_every_widget(canvas):
    session = canvas.session
    assert set(canvas.views) == {w.id for w in session.project.iter_widgets()}
    entry = canvas.views[node_named(session, "entry_name").id]
    assert entry.grid_info()["column"] == 1
    assert int(canvas.surface.cget("width")) == 420


def test_click_selects_without_triggering_widget(canvas):
    session = canvas.session
    button = node_named(session, "button_save")
    click(canvas.views[button.id].winfo_children()[0])
    assert session.selected_id == button.id
    assert canvas._outline[0].winfo_ismapped()
    click(canvas.surface, x=410, y=250)  # leere Fläche unten rechts
    assert session.selected_id == "window"


def test_canvas_follows_model_changes(canvas):
    session = canvas.session
    command = AddWidget("window", "CTkSwitch")
    session.execute(command)
    canvas.update()
    assert command.node_id in canvas.views
    session.undo()
    canvas.update()
    assert command.node_id not in canvas.views


def test_node_at(canvas):
    session = canvas.session
    save = node_named(session, "button_save")
    view = canvas.views[save.id]
    assert canvas.node_at(view.winfo_rootx() + 5, view.winfo_rooty() + 5) == save.id
    surface = canvas.surface
    assert canvas.node_at(surface.winfo_rootx() + 410, surface.winfo_rooty() + 250) == "window"
    assert canvas.node_at(surface.winfo_rootx() - 10, surface.winfo_rooty() - 10) is None
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_canvas.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.ui.canvas'`

- [ ] **Step 3: Implementierung schreiben**

Datei `ctk_builder/ui/canvas.py`:

```python
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
        for view in self.views.values():
            view.destroy()
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
        for child in view.winfo_children():
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
```

- [ ] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_canvas.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ctk_builder/ui/canvas.py tests/test_ui_canvas.py
git commit -m "feat: Arbeitsfläche mit echten CTk-Widgets"
```


### Task 7: Ausgabe-Panel, Hauptfenster und Start

**Files:**
- Create: `ctk_builder/ui/output_console.py`
- Create: `ctk_builder/ui/main_window.py`
- Create: `ctk_builder/__main__.py`
- Test: `tests/test_ui_main_window.py`

- [ ] **Step 1: Failing Test schreiben**

Datei `tests/test_ui_main_window.py`:

```python
"""Hauptfenster: Titel, Löschen/Duplizieren, Speichern, Export, Ausführen."""

import time

from conftest import node_named
from ctk_builder.commands import AddWidget


def test_title_shows_dirty_state(app):
    assert app.title() == "Unbenannt – CTk Builder"
    app.session.execute(AddWidget("window", "CTkLabel"))
    assert app.title() == "Unbenannt • – CTk Builder"


def test_delete_and_duplicate_selected(app):
    session = app.session
    label = node_named(session, "label_mail")
    session.select(label.id)
    app.duplicate_selected()
    assert session.project.find(session.selected_id).name == "label_1"
    app.delete_selected()
    assert session.selected_id == "window"
    app.delete_selected()  # Fenster kann nicht gelöscht werden
    assert session.project.window is not None


def test_save_export_and_run(app, tmp_path, monkeypatch):
    path = tmp_path / "kontakt.ctkb.json"
    app.session.path = path
    result = app.export()
    assert path.exists()
    assert result.ui_path.exists()
    assert result.logic_created
    assert app.title() == "kontakt.ctkb.json – CTk Builder"

    # Ausführen mit einem Skript, das sofort endet, statt der echten GUI
    result.logic_path.write_text("print('läuft')\n", encoding="utf-8")
    app.run()
    deadline = time.monotonic() + 10
    while "beendet" not in app.console.text.get("1.0", "end") and time.monotonic() < deadline:
        app.update()
        time.sleep(0.05)
    output = app.console.text.get("1.0", "end")
    assert "läuft" in output
    assert "Code 0" in output


def test_confirm_discard_without_changes(app):
    assert app.confirm_discard()
```

- [ ] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_ui_main_window.py -v`

Expected: FAIL (ERROR in Fixture `app`) mit `ModuleNotFoundError: No module named 'ctk_builder.ui.main_window'`

- [ ] **Step 3: Ausgabe-Panel implementieren**

Datei `ctk_builder/ui/output_console.py`:

```python
"""Ausgabe-Panel für das gestartete Programm."""

from __future__ import annotations

import customtkinter as ctk

from ctk_builder.runner import ProcessRunner

POLL_MS = 100


class OutputConsole(ctk.CTkFrame):
    def __init__(self, master, runner: ProcessRunner):
        super().__init__(master)
        self.runner = runner
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(header, text="Ausgabe", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Leeren", width=60, height=22,
                      command=self.clear).pack(side="right")
        ctk.CTkButton(header, text="Stopp", width=60, height=22,
                      command=runner.stop).pack(side="right", padx=4)
        self.text = ctk.CTkTextbox(self, height=110, font=ctk.CTkFont(family="Menlo", size=12))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")
        self.after(POLL_MS, self._poll)

    def write(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _poll(self) -> None:
        text = self.runner.drain()
        if text:
            self.write(text)
        self.after(POLL_MS, self._poll)
```

- [ ] **Step 4: Hauptfenster implementieren**

Die Menüleiste wird direkt über `tkinter.Tk.configure(self, menu=…)` gesetzt, an CTks eigener configure()-Logik vorbei. Tastenkürzel: Cmd (macOS) bzw. Strg.

Datei `ctk_builder/ui/main_window.py`:

```python
"""Hauptfenster: setzt die Panels zusammen, Menüs, Tastenkürzel, Dateien."""

from __future__ import annotations

import sys
import tkinter
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from ctk_builder import exporter
from ctk_builder.commands import DuplicateWidget, RemoveWidget
from ctk_builder.project_io import SUFFIX, ProjectFileError
from ctk_builder.runner import ProcessRunner
from ctk_builder.session import Session
from ctk_builder.settings import Settings
from ctk_builder.ui.canvas import DesignCanvas
from ctk_builder.ui.output_console import OutputConsole
from ctk_builder.ui.palette import Palette
from ctk_builder.ui.properties import PropertiesPanel
from ctk_builder.ui.structure_tree import StructureTree

MOD = "Command" if sys.platform == "darwin" else "Control"
MOD_LABEL = "Cmd" if sys.platform == "darwin" else "Strg"
FILETYPES = [("CTk Builder Projekt", f"*{SUFFIX}")]


class MainWindow(ctk.CTk):
    def __init__(self, session: Optional[Session] = None,
                 settings: Optional[Settings] = None):
        super().__init__()
        self.session = session or Session()
        self.settings = settings or Settings()
        self.runner = ProcessRunner()
        self.geometry("1280x800")
        self.minsize(900, 600)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent", width=220)
        left.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(8, 4), pady=8)
        left.grid_rowconfigure(1, weight=1)
        self.palette = Palette(left, self.session)
        self.palette.grid(row=0, column=0, sticky="ew")
        self.tree = StructureTree(left, self.session)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        self.canvas = DesignCanvas(self, self.session)
        self.canvas.grid(row=0, column=1, sticky="nsew", pady=8)
        self.console = OutputConsole(self, self.runner)
        self.console.grid(row=1, column=1, sticky="ew", pady=(0, 8))

        self.properties = PropertiesPanel(self, self.session)
        self.properties.configure(width=280)
        self.properties.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(4, 8), pady=8)

        self.status = ctk.CTkLabel(self, text="", anchor="w", height=20)
        self.status.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12)
        self.session.on_status = self.show_status
        self.session.subscribe(self.update_title)

        self._build_menu()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.update_title()

    # ------------------------------------------------------------ Rahmen

    def show_status(self, message: str) -> None:
        self.status.configure(text=message)
        self.after(5000, lambda: self.status.winfo_exists()
                   and self.status.cget("text") == message
                   and self.status.configure(text=""))

    def update_title(self) -> None:
        name = self.session.path.name if self.session.path else "Unbenannt"
        dirty = " •" if self.session.dirty else ""
        self.title(f"{name}{dirty} – CTk Builder")

    def _build_menu(self) -> None:
        menubar = tkinter.Menu(self)
        file_menu = tkinter.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Neu", accelerator=f"{MOD_LABEL}+N", command=self.new_project)
        file_menu.add_command(label="Öffnen…", accelerator=f"{MOD_LABEL}+O", command=self.open_project)
        file_menu.add_command(label="Speichern", accelerator=f"{MOD_LABEL}+S", command=self.save)
        file_menu.add_command(label="Speichern unter…", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exportieren", accelerator=f"{MOD_LABEL}+E", command=self.export)
        menubar.add_cascade(label="Datei", menu=file_menu)

        edit_menu = tkinter.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Rückgängig", accelerator=f"{MOD_LABEL}+Z", command=self.session.undo)
        edit_menu.add_command(label="Wiederholen", accelerator=f"{MOD_LABEL}+Shift+Z", command=self.session.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplizieren", accelerator=f"{MOD_LABEL}+D", command=self.duplicate_selected)
        edit_menu.add_command(label="Löschen", accelerator="Entf", command=self.delete_selected)
        menubar.add_cascade(label="Bearbeiten", menu=edit_menu)

        run_menu = tkinter.Menu(menubar, tearoff=False)
        run_menu.add_command(label="Ausführen", accelerator=f"{MOD_LABEL}+R", command=self.run)
        run_menu.add_command(label="Python-Interpreter wählen…", command=self.choose_interpreter)
        menubar.add_cascade(label="Ausführen", menu=run_menu)
        tkinter.Tk.configure(self, menu=menubar)

    def _bind_keys(self) -> None:
        shortcuts = {
            "n": self.new_project, "o": self.open_project, "s": self.save,
            "e": self.export, "r": self.run, "d": self.duplicate_selected,
            "z": self.session.undo, "Z": self.session.redo,
        }
        for key, action in shortcuts.items():
            self.bind_all(f"<{MOD}-{key}>", lambda e, a=action: (a(), "break")[1])
        self.bind_all(f"<{MOD}-Shift-z>", lambda e: (self.session.redo(), "break")[1])
        for widget in (self.canvas, self.tree.tree):
            widget.bind("<Delete>", lambda e: self.delete_selected())
            widget.bind("<BackSpace>", lambda e: self.delete_selected())

    # ------------------------------------------------------------ Bearbeiten

    def delete_selected(self) -> None:
        if self.session.selected_id != "window":
            self.session.execute(RemoveWidget(self.session.selected_id))

    def duplicate_selected(self) -> None:
        if self.session.selected_id == "window":
            return
        command = DuplicateWidget(self.session.selected_id)
        if self.session.execute(command):
            self.session.select(command.new_node_id)

    # ------------------------------------------------------------ Dateien

    def confirm_discard(self) -> bool:
        """True, wenn weitergemacht werden darf (gespeichert oder verworfen)."""
        if not self.session.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Ungespeicherte Änderungen", "Änderungen speichern?", parent=self)
        if answer is None:
            return False
        return self.save() if answer else True

    def new_project(self) -> None:
        if self.confirm_discard():
            self.session.new()

    def open_project(self) -> None:
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, filetypes=FILETYPES)
        if not path:
            return
        try:
            self.session.open(Path(path))
        except ProjectFileError as exc:
            messagebox.showerror("Öffnen fehlgeschlagen", str(exc), parent=self)

    def save(self) -> bool:
        if self.session.path is None:
            return self.save_as()
        self.session.save()
        self.show_status(f"Gespeichert: {self.session.path.name}")
        return True

    def save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self, filetypes=FILETYPES, defaultextension=SUFFIX,
            initialfile=f"{self.session.project.window.class_name.lower()}{SUFFIX}")
        if not path:
            return False
        if not path.endswith(SUFFIX):
            path = path.removesuffix(".json") + SUFFIX
        self.session.save(Path(path))
        self.show_status(f"Gespeichert: {Path(path).name}")
        return True

    def export(self) -> Optional[exporter.ExportResult]:
        if not self.save():
            return None
        try:
            result = exporter.export(self.session.project, self.session.path)
        except exporter.ExportNeedsConfirmation as exc:
            if not messagebox.askyesno("Export", str(exc), parent=self):
                return None
            result = exporter.export(self.session.project, self.session.path, force=True)
        created = f", {result.logic_path.name} angelegt" if result.logic_created else ""
        self.show_status(f"Exportiert: {result.ui_path.name}{created}")
        return result

    def run(self) -> None:
        result = self.export()
        if result is None:
            return
        self.console.write(f"$ {self.settings.interpreter} {result.logic_path.name}\n")
        try:
            self.runner.start(self.settings.interpreter, result.logic_path)
        except OSError as exc:
            self.console.write(f"Start fehlgeschlagen: {exc}\n")

    def choose_interpreter(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Python-Interpreter wählen")
        if path:
            self.settings.interpreter = path
            self.show_status(f"Interpreter: {path}")

    def quit_app(self) -> None:
        if self.confirm_discard():
            self.runner.stop()
            self.destroy()


def main() -> None:
    MainWindow().mainloop()
```

- [ ] **Step 5: Startpunkt anlegen**

Datei `ctk_builder/__main__.py`:

```python
from ctk_builder.ui.main_window import main

main()
```

- [ ] **Step 6: Tests ausführen**

Run: `.venv/bin/pytest tests/test_ui_main_window.py -v`

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add ctk_builder/ui/output_console.py ctk_builder/ui/main_window.py ctk_builder/__main__.py tests/test_ui_main_window.py
git commit -m "feat: Hauptfenster mit Menüs, Export und Ausführen"
```


### Task 8: Abschluss Plan 2

- [ ] **Step 1: Komplette Testsuite**

Run: `.venv/bin/pytest -v` (Linux ohne Display: `xvfb-run -a .venv/bin/pytest -v`)

Expected: `134 passed`

- [ ] **Step 2: Manuell ausprobieren (nur mit Desktop)**

Run: `.venv/bin/python -m ctk_builder`

Prüfen:
1. Palette → „Label“, „Entry“, „Button“ klicken: erscheinen untereinander auf der Arbeitsfläche und im Strukturbaum.
2. Button auf der Arbeitsfläche anklicken: oranger Rahmen, Eigenschaften zeigen `button_1`, der Button löst **nicht** aus.
3. `text` auf „Speichern“, `command` auf `on_save`, Enter: Vorschau aktualisiert sich.
4. `Cmd+Z` / `Cmd+Shift+Z`: Änderungen werden rückgängig gemacht/wiederholt.
5. `Cmd+R`: Speichern-Dialog → z. B. `~/Desktop/test/kontakt.ctkb.json`; das Programm startet als eigenes Fenster, Ausgabe erscheint unten.
6. In `kontakt.py` `on_save` mit `print("gespeichert")` füllen, erneut `Cmd+R`, Button klicken: Ausgabe erscheint; `kontakt.py` bleibt beim Export unverändert.

- [ ] **Step 3: Pushen**

```bash
git push
```
