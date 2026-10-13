# CTk Builder – Plan 1: Kern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das GUI-unabhängige Fundament: Projektmodell, Widget-Beschreibungen, Befehle mit Undo/Redo, Projektdateien und Code-Generator inkl. Export – vollständig getestet.

**Architecture:** Ein Baum aus Datenklassen (`model`) wird ausschließlich über Befehle (`commands`) geändert; jeder Befehl merkt sich Schnappschüsse für exaktes Undo. `project_io` speichert als JSON, `codegen` erzeugt aus dem Modell reinen Python-Quelltext, `exporter` schreibt ihn sicher auf die Platte.

**Tech Stack:** Python 3.12+, customtkinter 6.x (nur für Standardwerte/reservierte Namen), pytest

---

## Umgebung

- Arbeitsverzeichnis ist die Wurzel des Repos `tkinter-gui-builder`.
- Alle Befehle nutzen das Virtualenv `.venv` (siehe Plan 1, Task 1).
- **macOS:** Tests laufen direkt; Oberflächentests öffnen kurz echte Fenster.
- **Linux ohne Display (z. B. Claude Code im Browser/Cloud):** Oberflächentests mit
  `xvfb-run -a .venv/bin/pytest …` ausführen. Ohne Display werden sie übersprungen –
  das zählt **nicht** als bestanden; dann `xvfb` installieren (`sudo apt-get install -y xvfb python3-tk`).
- Spezifikation: `docs/superpowers/specs/2026-10-13-ctk-gui-builder-design.md`.

## Dateistruktur nach diesem Plan

```
ctk_builder/
  __init__.py
  model.py         # Datenklassen: Project, WindowNode, WidgetNode, Layout, GridConfig, LineConfig
  widget_specs.py  # Widget-Typen, Eigenschaften, Standardwerte, parse_value()
  names.py         # Prüfung von Python-Bezeichnern (Widget-, Handler-, Gruppennamen)
  commands.py      # Befehle + CommandStack (Undo/Redo, „ungespeichert“)
  project_io.py    # *.ctkb.json speichern/laden
  codegen.py       # Modell -> <modul>_ui.py / <modul>.py Quelltext
  exporter.py      # Dateien schreiben, Logik-Datei nie überschreiben
tests/
  conftest.py      # Beispielprojekt „kontakt“, Display-Erkennung
  snapshots/       # Referenzausgaben des Code-Generators
  test_*.py
```

**Wichtige Hinweise zu CustomTkinter 6:** Die Standardwerte in `widget_specs.py` entsprechen
customtkinter 6.0 (z. B. `CTkLabel(fg_color=None)`). `tests/test_widget_specs.py` prüft das
automatisch gegen die installierte Version. Schlägt dieser Test nach einem Update fehl,
die Standardwerte in `SPECS` anpassen.

---

### Task 1: Projekt-Setup

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `README.md`, `ctk_builder/__init__.py`

- [x] **Step 1: Python mit Tk 8.6+ bereitstellen**

macOS:
```bash
brew install python@3.12 python-tk@3.12
python3.12 -c "import tkinter; print(tkinter.TkVersion)"
```
Linux:
```bash
sudo apt-get install -y python3-venv python3-tk xvfb
python3 -c "import tkinter; print(tkinter.TkVersion)"
```
Expected: `8.6` oder höher (z. B. `9.0`). **Nicht** das macOS-System-Python (`/usr/bin/python3`, Tk 8.5) verwenden.

- [x] **Step 2: `requirements.txt` anlegen**

Datei `requirements.txt`:

```text
customtkinter>=6.0,<7
```

- [x] **Step 3: `requirements-dev.txt` anlegen**

Datei `requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8
```

- [x] **Step 4: `pyproject.toml` anlegen**

Datei `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [x] **Step 5: `README.md` anlegen**

Datei `README.md`:

````markdown
# CTk Builder

Drag & Drop GUI-Builder für [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter):
GUI im `grid()`-Layout zusammenklicken und sauberen Python-Code exportieren.

## Einrichten

Python 3.12+ mit Tk 8.6 oder neuer wird benötigt (das macOS-System-Python 3.9 mit Tk 8.5 reicht nicht).

```bash
# macOS (Homebrew)
brew install python@3.12 python-tk@3.12
python3.12 -m venv .venv

# Linux (Debian/Ubuntu)
sudo apt-get install -y python3-venv python3-tk xvfb
python3 -m venv .venv

.venv/bin/pip install -r requirements-dev.txt
```

## Starten

```bash
.venv/bin/python -m ctk_builder
```

## Tests

```bash
.venv/bin/pytest            # macOS / Linux mit Desktop
xvfb-run -a .venv/bin/pytest  # Linux ohne Display (z. B. Cloud/CI)
```

Ohne Display werden die Oberflächentests übersprungen.

## Dokumentation

- Design: `docs/superpowers/specs/2026-10-13-ctk-gui-builder-design.md`
- Pläne: `docs/superpowers/plans/`
````

- [x] **Step 6: Paket und Virtualenv anlegen**

```bash
mkdir -p ctk_builder tests/snapshots
touch ctk_builder/__init__.py
python3.12 -m venv .venv        # Linux: python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -c "import customtkinter; print(customtkinter.__version__)"
```
Expected: eine Version `6.x`.

- [x] **Step 7: Leeren Testlauf prüfen**

Run: `.venv/bin/pytest`

Expected: `no tests ran` (Exit-Code 5) – pytest ist eingerichtet.

- [x] **Step 8: Commit**

```bash
git add requirements.txt requirements-dev.txt pyproject.toml README.md ctk_builder/__init__.py
git commit -m "chore: Projekt-Setup mit customtkinter und pytest"
```


### Task 2: Projektmodell

Datenklassen für Fenster, Widgets, Grid-Konfiguration und Layout sowie Hilfsfunktionen für Zellbelegung. **Regel:** `model.py` importiert kein Tkinter.

**Files:**
- Create: `ctk_builder/model.py`
- Test: `tests/test_model.py`

- [x] **Step 1: Failing Test schreiben**

Datei `tests/test_model.py`:

```python
from ctk_builder.model import (
    GridConfig, Layout, LineConfig, Project, WidgetNode, fits, next_free_cell, occupant,
)


def make_widget(id_, name, row=0, column=0, rowspan=1, columnspan=1, grid=None):
    return WidgetNode(
        id=id_, type="CTkLabel", name=name,
        layout=Layout(row=row, column=column, rowspan=rowspan, columnspan=columnspan),
        grid=grid,
    )


def test_new_project_has_window_with_one_cell():
    project = Project()
    assert project.window.id == "window"
    assert len(project.window.grid.rows) == 1
    assert len(project.window.grid.columns) == 1
    assert project.window.children == []


def test_layout_cells_covers_span():
    layout = Layout(row=1, column=2, rowspan=2, columnspan=2)
    assert layout.cells() == {(1, 2), (1, 3), (2, 2), (2, 3)}


def test_line_config_default():
    assert LineConfig().is_default()
    assert not LineConfig(weight=1).is_default()


def test_occupant_and_fits():
    project = Project()
    window = project.window
    window.grid = GridConfig(rows=[LineConfig()] * 2, columns=[LineConfig()] * 2)
    window.children.append(make_widget("a", "label_1", columnspan=2))
    assert occupant(window, 0, 1).id == "a"
    assert occupant(window, 1, 0) is None
    assert fits(window, Layout(row=1, column=0))
    assert not fits(window, Layout(row=0, column=1))
    assert fits(window, Layout(row=0, column=1), ignore=frozenset({"a"}))
    assert not fits(window, Layout(row=1, column=1, columnspan=2))  # außerhalb


def test_next_free_cell_scans_rows_then_appends():
    project = Project()
    window = project.window
    assert next_free_cell(window) == (0, 0)
    window.children.append(make_widget("a", "label_1"))
    assert next_free_cell(window) == (1, 0)


def test_find_parent_descendant_and_iteration_order():
    project = Project()
    frame = make_widget("f", "frame_1", grid=GridConfig())
    inner = make_widget("i", "label_2")
    frame.children.append(inner)
    project.window.children += [frame, make_widget("b", "label_1", row=1)]

    assert [w.id for w in project.iter_widgets()] == ["f", "i", "b"]
    assert project.find("i") is inner
    assert project.find("window") is project.window
    assert project.find("nope") is None
    assert project.parent_of("i") is frame
    assert project.parent_of("f") is project.window
    assert project.is_descendant("i", "f")
    assert project.is_descendant("f", "f")
    assert not project.is_descendant("f", "i")


def test_unique_name():
    project = Project()
    project.window.children.append(make_widget("a", "label_1"))
    assert project.unique_name("label") == "label_2"
    assert project.unique_name("button") == "button_1"


def test_subscribe_and_unsubscribe():
    project = Project()
    calls = []
    unsubscribe = project.subscribe(lambda: calls.append(1))
    project.notify()
    unsubscribe()
    project.notify()
    assert calls == [1]
```

- [x] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_model.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.model'`

- [x] **Step 3: Implementierung schreiben**

Datei `ctk_builder/model.py`:

```python
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


@dataclass
class Layout:
    """Grid-Platzierung eines Widgets in seinem Container."""

    row: int = 0
    column: int = 0
    rowspan: int = 1
    columnspan: int = 1
    sticky: str = ""
    padx: int = 0
    pady: int = 0

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

    @property
    def is_container(self) -> bool:
        return self.grid is not None


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

    @property
    def is_container(self) -> bool:
        return True


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


class Project:
    """Hält den Fensterbaum und benachrichtigt Beobachter über Änderungen."""

    def __init__(self, window: Optional[WindowNode] = None):
        self.window = window if window is not None else WindowNode()
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
```

- [x] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_model.py -v`

Expected: 8 passed

- [x] **Step 5: Commit**

```bash
git add ctk_builder/model.py tests/test_model.py
git commit -m "feat: Projektmodell mit Grid-Belegung"
```


### Task 3: Widget-Beschreibungen

Eine Tabelle `SPECS` mit allen V1-Widgets (Label, Button, Entry, Textbox, CheckBox, Switch, RadioButton, Frame), ihren Eigenschaften und Standardwerten sowie `parse_value()` für Eingaben aus dem Eigenschaften-Panel. `default` ist immer der echte CTk-Standardwert – gleiche Werte werden später nicht exportiert. `initial` sind die Werte für neu eingefügte Widgets.

**Files:**
- Create: `ctk_builder/widget_specs.py`
- Test: `tests/test_widget_specs.py`

- [x] **Step 1: Failing Test schreiben**

Datei `tests/test_widget_specs.py`:

```python
import inspect

import customtkinter as ctk
import pytest

from ctk_builder.widget_specs import (
    CHOICE, COLOR, GROUP, HANDLER, INT, OPT_INT, OPT_STR, STR, SPECS, PropSpec,
    format_value, parse_value,
)

# Diese Eigenschaften werden von codegen besonders übersetzt
SPECIAL = {"font_size", "variable_group", "value"}


def test_all_v1_widgets_present():
    assert set(SPECS) == {
        "CTkLabel", "CTkButton", "CTkEntry", "CTkTextbox",
        "CTkCheckBox", "CTkSwitch", "CTkRadioButton", "CTkFrame",
    }
    assert [t for t, s in SPECS.items() if s.is_container] == ["CTkFrame"]


@pytest.mark.parametrize("widget_type", sorted(SPECS))
def test_defaults_match_customtkinter(widget_type):
    """Standardwerte müssen den echten CTk-Standardwerten entsprechen."""
    params = inspect.signature(getattr(ctk, widget_type).__init__).parameters
    for prop in SPECS[widget_type].props:
        if prop.name in SPECIAL:
            continue
        if prop.name in params:
            assert params[prop.name].default == prop.default, prop.name
        else:
            # wird über **kwargs an das tkinter-Widget durchgereicht
            assert "kwargs" in params, prop.name


def test_initial_values_are_known_props():
    for spec in SPECS.values():
        for key in spec.initial:
            spec.prop(key)


@pytest.mark.parametrize("kind,raw,expected", [
    (STR, " Hallo ", " Hallo "),
    (STR, "", ""),
    (OPT_STR, "", None),
    (OPT_STR, "x", "x"),
    (INT, "12", 12),
    (OPT_INT, "", None),
    (OPT_INT, " 3 ", 3),
    (COLOR, "", None),
    (COLOR, "#fff", "#fff"),
    (COLOR, "#1f6aa5", "#1f6aa5"),
    (COLOR, "transparent", "transparent"),
    (COLOR, "red", "red"),
    (HANDLER, "", None),
    (HANDLER, "on_save", "on_save"),
    (GROUP, "auswahl", "auswahl"),
])
def test_parse_value_valid(kind, raw, expected):
    assert parse_value(PropSpec("p", kind, None), raw) == expected


@pytest.mark.parametrize("kind,raw", [
    (INT, ""),
    (INT, "-1"),
    (INT, "1.5"),
    (OPT_INT, "abc"),
    (COLOR, "#12345"),
    (COLOR, "#ggg"),
    (HANDLER, "on save"),
    (GROUP, "1x"),
])
def test_parse_value_invalid(kind, raw):
    with pytest.raises(ValueError):
        parse_value(PropSpec("p", kind, None), raw)


def test_parse_choice():
    prop = PropSpec("state", CHOICE, "normal", ("normal", "disabled"))
    assert parse_value(prop, "disabled") == "disabled"
    with pytest.raises(ValueError):
        parse_value(prop, "kaputt")


def test_color_check_callback_can_reject_names():
    prop = PropSpec("c", COLOR, None)
    with pytest.raises(ValueError):
        parse_value(prop, "notacolor", color_check=lambda name: False)


def test_format_value():
    assert format_value(None) == ""
    assert format_value(12) == "12"
    assert format_value("x") == "x"
```

- [x] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_widget_specs.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.widget_specs'`

- [x] **Step 3: Implementierung schreiben**

Datei `ctk_builder/widget_specs.py`:

```python
"""Beschreibung aller Widget-Typen, die der Builder kennt."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Editor-Arten für das Eigenschaften-Panel
STR = "str"            # beliebiger Text
OPT_STR = "opt_str"    # Text, leer = nicht gesetzt (None)
INT = "int"            # Ganzzahl >= 0
OPT_INT = "opt_int"    # Ganzzahl >= 0, leer = nicht gesetzt (None)
COLOR = "color"        # Farbe, leer = nicht gesetzt (None)
CHOICE = "choice"      # Auswahl aus choices
HANDLER = "handler"    # Methodenname, leer = kein Handler
GROUP = "group"        # Name einer RadioButton-Gruppe, leer = keine Gruppe


@dataclass(frozen=True)
class PropSpec:
    name: str
    kind: str
    default: Any  # CTk-Standardwert; gleiche Werte werden nicht exportiert
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class WidgetSpec:
    type: str                      # CTk-Klassenname, z. B. "CTkButton"
    prefix: str                    # Präfix für Standardnamen, z. B. "button"
    props: tuple[PropSpec, ...]
    initial: dict[str, Any] = field(default_factory=dict)  # Werte für neue Widgets
    is_container: bool = False

    def prop(self, name: str) -> PropSpec:
        for p in self.props:
            if p.name == name:
                return p
        raise KeyError(f"{self.type} hat keine Eigenschaft {name!r}")


STATE = PropSpec("state", CHOICE, "normal", ("normal", "disabled"))
FONT_SIZE = PropSpec("font_size", OPT_INT, None)
TEXT_COLOR = PropSpec("text_color", COLOR, None)
FG_COLOR = PropSpec("fg_color", COLOR, None)
CORNER_RADIUS = PropSpec("corner_radius", OPT_INT, None)
COMMAND = PropSpec("command", HANDLER, None)

SPECS: dict[str, WidgetSpec] = {
    spec.type: spec
    for spec in (
        WidgetSpec("CTkLabel", "label", (
            PropSpec("text", STR, "CTkLabel"),
            PropSpec("width", INT, 0),
            PropSpec("height", INT, 28),
            FONT_SIZE,
            TEXT_COLOR,
            FG_COLOR,
            PropSpec("anchor", CHOICE, "center",
                     ("center", "n", "ne", "e", "se", "s", "sw", "w", "nw")),
            CORNER_RADIUS,
        ), initial={"text": "Label"}),
        WidgetSpec("CTkButton", "button", (
            PropSpec("text", STR, "CTkButton"),
            PropSpec("width", INT, 140),
            PropSpec("height", INT, 28),
            FONT_SIZE,
            FG_COLOR,
            PropSpec("hover_color", COLOR, None),
            TEXT_COLOR,
            CORNER_RADIUS,
            STATE,
            COMMAND,
        ), initial={"text": "Button"}),
        WidgetSpec("CTkEntry", "entry", (
            PropSpec("placeholder_text", OPT_STR, None),
            PropSpec("width", INT, 140),
            PropSpec("height", INT, 28),
            FONT_SIZE,
            FG_COLOR,
            TEXT_COLOR,
            CORNER_RADIUS,
            STATE,
        )),
        WidgetSpec("CTkTextbox", "textbox", (
            PropSpec("width", INT, 200),
            PropSpec("height", INT, 200),
            FONT_SIZE,
            FG_COLOR,
            TEXT_COLOR,
            CORNER_RADIUS,
            PropSpec("wrap", CHOICE, "char", ("char", "word", "none")),
            STATE,
        ), initial={"height": 100}),
        WidgetSpec("CTkCheckBox", "checkbox", (
            PropSpec("text", STR, "CTkCheckBox"),
            FONT_SIZE,
            TEXT_COLOR,
            FG_COLOR,
            STATE,
            COMMAND,
        ), initial={"text": "CheckBox"}),
        WidgetSpec("CTkSwitch", "switch", (
            PropSpec("text", STR, "CTkSwitch"),
            FONT_SIZE,
            TEXT_COLOR,
            PropSpec("progress_color", COLOR, None),
            STATE,
            COMMAND,
        ), initial={"text": "Switch"}),
        WidgetSpec("CTkRadioButton", "radio", (
            PropSpec("text", STR, "CTkRadioButton"),
            PropSpec("variable_group", GROUP, None),
            PropSpec("value", OPT_STR, None),
            FONT_SIZE,
            TEXT_COLOR,
            FG_COLOR,
            STATE,
            COMMAND,
        ), initial={"text": "Option"}),
        WidgetSpec("CTkFrame", "frame", (
            PropSpec("width", INT, 200),
            PropSpec("height", INT, 200),
            FG_COLOR,
            CORNER_RADIUS,
            PropSpec("border_width", OPT_INT, None),
            PropSpec("border_color", COLOR, None),
        ), is_container=True),
    )
}

_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_COLOR_NAME = re.compile(r"[A-Za-z][A-Za-z0-9 ]*")


def parse_value(prop: PropSpec, raw: str,
                color_check: Optional[Callable[[str], bool]] = None) -> Any:
    """Wandelt eine Eingabe aus dem Eigenschaften-Panel in einen Modellwert.

    Wirft ValueError mit verständlicher Meldung bei ungültiger Eingabe.
    color_check kann Farbnamen zusätzlich prüfen (z. B. über Tk).
    """
    text = raw.strip()
    if prop.kind == STR:
        return raw
    if prop.kind == OPT_STR:
        return raw if raw != "" else None
    if prop.kind in (INT, OPT_INT):
        if text == "" and prop.kind == OPT_INT:
            return None
        if not text.isdigit():
            raise ValueError(f"{prop.name}: ganze Zahl >= 0 erwartet")
        return int(text)
    if prop.kind == COLOR:
        if text == "":
            return None
        if text == "transparent" or _HEX_COLOR.fullmatch(text):
            return text
        if _COLOR_NAME.fullmatch(text) and (color_check is None or color_check(text)):
            return text
        raise ValueError(f"{prop.name}: Farbe als #rrggbb oder Farbname erwartet")
    if prop.kind == CHOICE:
        if text not in prop.choices:
            raise ValueError(f"{prop.name}: einer von {', '.join(prop.choices)} erwartet")
        return text
    if prop.kind in (HANDLER, GROUP):
        if text == "":
            return None
        if not text.isidentifier():
            raise ValueError(f"{prop.name}: gültiger Python-Name erwartet")
        return text
    raise ValueError(f"Unbekannte Eigenschafts-Art {prop.kind!r}")


def format_value(value: Any) -> str:
    """Gegenstück zu parse_value: Modellwert als Text fürs Eingabefeld."""
    return "" if value is None else str(value)
```

- [x] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_widget_specs.py -v`

Expected: 36 passed

- [x] **Step 5: Commit**

```bash
git add ctk_builder/widget_specs.py tests/test_widget_specs.py
git commit -m "feat: Widget-Beschreibungen und Eingabeprüfung"
```


### Task 4: Namensprüfung

Widget-Namen werden zu `self.<name>`, Handler zu Methoden, RadioButton-Gruppen zu `self.<gruppe>`. Sie müssen gültige Python-Namen sein, dürfen keine Attribute von `ctk.CTk` überschreiben und sich nicht überschneiden. Handler und Gruppen dürfen mehrfach verwendet werden (mehrere Buttons, ein Handler), Widget-Namen nicht.

**Files:**
- Create: `ctk_builder/names.py`
- Test: `tests/test_names.py`

- [x] **Step 1: Failing Test schreiben**

Datei `tests/test_names.py`:

```python
import pytest

from ctk_builder import names
from ctk_builder.model import Layout, Project, WidgetNode


@pytest.fixture
def project():
    p = Project()
    p.window.children.append(WidgetNode(
        id="b", type="CTkButton", name="button_1",
        props={"command": "on_save"}, layout=Layout(),
    ))
    return p


@pytest.mark.parametrize("value", ["1abc", "mit leer", "class", "title", "_privat"])
def test_invalid_identifiers(project, value):
    with pytest.raises(ValueError):
        names.check_identifier(project, names.WIDGET, value)


def test_widget_name_must_be_unique(project):
    with pytest.raises(ValueError):
        names.check_identifier(project, names.WIDGET, "button_1")
    # der eigene Name ist erlaubt
    names.check_identifier(project, names.WIDGET, "button_1", node_id="b")


def test_handler_may_be_shared_but_not_clash_with_widget(project):
    names.check_identifier(project, names.HANDLER, "on_save")
    with pytest.raises(ValueError):
        names.check_identifier(project, names.HANDLER, "button_1")
    with pytest.raises(ValueError):
        names.check_identifier(project, names.WIDGET, "on_save")


def test_own_name_is_not_a_valid_handler(project):
    with pytest.raises(ValueError):
        names.check_identifier(project, names.HANDLER, "button_1", node_id="b")
```

- [x] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_names.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.names'`

- [x] **Step 3: Implementierung schreiben**

Datei `ctk_builder/names.py`:

```python
"""Prüfung von Bezeichnern, die im generierten Code zu Attributen werden."""

from __future__ import annotations

import keyword
from functools import lru_cache
from typing import Optional

from ctk_builder.model import Project

WIDGET = "widget"    # Widget-Name -> self.<name>
HANDLER = "handler"  # command-Handler -> def <name>(self)
GROUP = "group"      # RadioButton-Gruppe -> self.<name> = StringVar()


@lru_cache(maxsize=1)
def reserved_names() -> frozenset[str]:
    """Attribute von ctk.CTk, die ein generierter Name nicht überschreiben darf."""
    import customtkinter as ctk

    return frozenset(dir(ctk.CTk))


def used_identifiers(project: Project, exclude_node: Optional[str] = None,
                     exclude_kind: Optional[str] = None) -> dict[str, set[str]]:
    """Alle verwendeten Bezeichner je Art.

    Der Bezeichner der Art exclude_kind von Knoten exclude_node wird ausgelassen
    (das ist der Wert, der gerade geändert wird).
    """
    used: dict[str, set[str]] = {WIDGET: set(), HANDLER: set(), GROUP: set()}
    for widget in project.iter_widgets():
        values = {
            WIDGET: widget.name,
            HANDLER: widget.props.get("command"),
            GROUP: widget.props.get("variable_group"),
        }
        for kind, value in values.items():
            if value and not (widget.id == exclude_node and kind == exclude_kind):
                used[kind].add(value)
    return used


def check_identifier(project: Project, kind: str, value: str,
                     node_id: Optional[str] = None) -> None:
    """Wirft ValueError, wenn value als Bezeichner der Art kind nicht erlaubt ist.

    Handler und Gruppen dürfen mehrfach vorkommen (mehrere Buttons, ein Handler),
    Widget-Namen nicht. Über Arten hinweg darf es keine Überschneidung geben.
    """
    if not value.isidentifier():
        raise ValueError(f"„{value}“ ist kein gültiger Python-Name")
    if keyword.iskeyword(value):
        raise ValueError(f"„{value}“ ist ein Python-Schlüsselwort")
    if value.startswith("_") or value in reserved_names():
        raise ValueError(f"„{value}“ ist für CustomTkinter reserviert")
    used = used_identifiers(project, exclude_node=node_id, exclude_kind=kind)
    for other_kind, names in used.items():
        if value not in names:
            continue
        if other_kind == kind and kind != WIDGET:
            continue
        raise ValueError(f"„{value}“ wird schon verwendet")
```

- [x] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_names.py -v`

Expected: 8 passed

- [x] **Step 5: Commit**

```bash
git add ctk_builder/names.py tests/test_names.py
git commit -m "feat: Prüfung generierter Bezeichner"
```


### Task 5: Befehle und Undo/Redo

Jede Modelländerung ist ein `Command`. Die Basisklasse speichert vor und nach `apply()` eine Kopie des Fensterbaums (`deepcopy`); Undo/Redo stellen diese Kopien wieder her, und ein Fehler in `apply()` rollt automatisch zurück. **Konsequenz für alle Ansichten:** Nie Knoten-Objekte über eine Änderung hinweg merken, nur IDs, und nach jeder Änderung mit `project.find(id)` neu nachschlagen. `CommandStack` verwaltet Undo/Redo, benachrichtigt Beobachter und weiß, ob es ungespeicherte Änderungen gibt.

**Files:**
- Create: `ctk_builder/commands.py`
- Test: `tests/test_commands.py`

- [x] **Step 1: Failing Test schreiben**

Datei `tests/test_commands.py`:

```python
import copy

import pytest

from ctk_builder.commands import (
    AddWidget, CommandError, CommandStack, DuplicateWidget, InsertLine, MoveWidget,
    RemoveLine, RemoveWidget, RenameWidget, SetLayout, SetLineConfig, SetProperty,
    SetWindowProperty,
)
from ctk_builder.model import LineConfig, Project


@pytest.fixture
def stack():
    return CommandStack(Project())


def add(stack, widget_type="CTkLabel", parent="window", row=None, column=None):
    cmd = AddWidget(parent, widget_type, row, column)
    stack.execute(cmd)
    return stack.project.find(cmd.node_id)


def snapshot(stack):
    return copy.deepcopy(stack.project.window)


def assert_undo_restores(stack, command):
    """Führt command aus, macht es rückgängig, prüft Gleichheit, macht Redo."""
    before = snapshot(stack)
    stack.execute(command)
    after = snapshot(stack)
    stack.undo()
    assert stack.project.window == before
    stack.redo()
    assert stack.project.window == after


def test_add_widget_uses_initial_props_and_unique_name(stack):
    label = add(stack)
    assert label.name == "label_1"
    assert label.props == {"text": "Label"}
    assert (label.layout.row, label.layout.column) == (0, 0)
    assert add(stack).name == "label_2"


def test_add_widget_without_cell_takes_next_free_and_grows(stack):
    add(stack)
    second = add(stack)
    assert (second.layout.row, second.layout.column) == (1, 0)
    assert len(stack.project.window.grid.rows) == 2


def test_add_on_edge_appends_column(stack):
    add(stack, row=0, column=0)
    add(stack, row=0, column=1)
    assert len(stack.project.window.grid.columns) == 2


def test_add_rejects_occupied_and_far_away_cells(stack):
    add(stack, row=0, column=0)
    before = snapshot(stack)
    with pytest.raises(CommandError):
        stack.execute(AddWidget("window", "CTkLabel", 0, 0))
    with pytest.raises(CommandError):
        stack.execute(AddWidget("window", "CTkLabel", 5, 0))
    assert stack.project.window == before
    assert not stack.can_redo


def test_add_frame_creates_grid_and_children_go_inside(stack):
    frame = add(stack, "CTkFrame")
    assert frame.grid is not None
    button = add(stack, "CTkButton", parent=frame.id)
    assert stack.project.parent_of(button.id).id == frame.id


def test_add_into_non_container_fails(stack):
    label = add(stack)
    with pytest.raises(CommandError):
        stack.execute(AddWidget(label.id, "CTkLabel"))


def test_add_undo_redo(stack):
    assert_undo_restores(stack, AddWidget("window", "CTkButton", 0, 0))


def test_redo_keeps_node_id(stack):
    cmd = AddWidget("window", "CTkButton", 0, 0)
    stack.execute(cmd)
    stack.undo()
    stack.redo()
    assert stack.project.find(cmd.node_id) is not None


def test_remove_widget(stack):
    label = add(stack)
    assert_undo_restores(stack, RemoveWidget(label.id))
    assert stack.project.find(label.id) is None


def test_move_to_empty_cell(stack):
    label = add(stack, row=0, column=0)
    assert_undo_restores(stack, MoveWidget(label.id, "window", 0, 1))
    moved = stack.project.find(label.id)
    assert (moved.layout.row, moved.layout.column) == (0, 1)


def test_move_onto_occupied_cell_swaps(stack):
    a = add(stack, row=0, column=0)
    b = add(stack, row=0, column=1)
    stack.execute(MoveWidget(a.id, "window", 0, 1))
    a, b = stack.project.find(a.id), stack.project.find(b.id)
    assert (a.layout.row, a.layout.column) == (0, 1)
    assert (b.layout.row, b.layout.column) == (0, 0)


def test_move_into_and_out_of_frame(stack):
    frame = add(stack, "CTkFrame", row=0, column=0)
    label = add(stack, row=1, column=0)
    stack.execute(MoveWidget(label.id, frame.id, 0, 0))
    assert stack.project.parent_of(label.id).id == frame.id
    stack.execute(MoveWidget(label.id, "window", 1, 0))
    assert stack.project.parent_of(label.id).id == "window"


def test_move_frame_into_itself_fails(stack):
    outer = add(stack, "CTkFrame")
    inner = add(stack, "CTkFrame", parent=outer.id)
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(outer.id, outer.id, 0, 0))
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(outer.id, inner.id, 0, 0))


def test_swap_with_spanning_widget_that_does_not_fit_fails(stack):
    a = add(stack, row=0, column=0)
    b = add(stack, row=0, column=1)
    add(stack, row=1, column=0)
    stack.execute(SetLayout(b.id, rowspan=2))  # b belegt (0,1) und (1,1)
    before = snapshot(stack)
    with pytest.raises(CommandError):
        stack.execute(MoveWidget(a.id, "window", 0, 1))  # b müsste nach (0,0) mit rowspan 2
    assert stack.project.window == before


def test_duplicate_widget_copies_subtree_with_new_names(stack):
    frame = add(stack, "CTkFrame")
    add(stack, "CTkButton", parent=frame.id)
    cmd = DuplicateWidget(frame.id)
    stack.execute(cmd)
    clone = stack.project.find(cmd.new_node_id)
    assert clone.name == "frame_2"
    assert clone.children[0].name == "button_2"
    assert clone.id != frame.id
    assert clone.children[0].id != frame.children[0].id
    assert (clone.layout.row, clone.layout.column) == (1, 0)
    names = [w.name for w in stack.project.iter_widgets()]
    assert len(names) == len(set(names))


def test_rename(stack):
    label = add(stack)
    add(stack)
    stack.execute(RenameWidget(label.id, "label_title"))
    assert stack.project.find(label.id).name == "label_title"
    with pytest.raises(CommandError):
        stack.execute(RenameWidget(label.id, "label_2"))
    with pytest.raises(CommandError):
        stack.execute(RenameWidget(label.id, "class"))


def test_set_property_and_reset_to_default(stack):
    button = add(stack, "CTkButton")
    assert_undo_restores(stack, SetProperty(button.id, "text", "Speichern"))
    stack.execute(SetProperty(button.id, "command", "on_save"))
    assert stack.project.find(button.id).props["command"] == "on_save"
    stack.execute(SetProperty(button.id, "command", None))
    assert "command" not in stack.project.find(button.id).props


def test_set_property_checks_handler_names(stack):
    button = add(stack, "CTkButton")
    with pytest.raises(CommandError):
        stack.execute(SetProperty(button.id, "command", button.name))
    with pytest.raises(KeyError):
        stack.execute(SetProperty(button.id, "gibtsnicht", 1))


def test_set_layout(stack):
    label = add(stack, row=0, column=0)
    add(stack, row=0, column=1)
    stack.execute(SetLayout(label.id, sticky="wens", padx=4))
    assert stack.project.find(label.id).layout.sticky == "nsew"
    with pytest.raises(CommandError):
        stack.execute(SetLayout(label.id, columnspan=2))  # überdeckt Nachbarn
    with pytest.raises(CommandError):
        stack.execute(SetLayout(label.id, sticky="x"))
    with pytest.raises(CommandError):
        stack.execute(SetLayout(label.id, padx=-1))
    with pytest.raises(ValueError):
        SetLayout(label.id, farbe="rot")


def test_set_window_property(stack):
    assert_undo_restores(stack, SetWindowProperty("title", "Kontakt"))
    stack.execute(SetWindowProperty("width", 640))
    assert stack.project.window.width == 640
    for key, value in [("width", 0), ("class_name", "1x"),
                       ("appearance_mode", "pink"), ("color_theme", "red")]:
        with pytest.raises(CommandError):
            stack.execute(SetWindowProperty(key, value))


def test_insert_line_shifts_and_extends_spans(stack):
    a = add(stack, row=0, column=0)
    stack.execute(InsertLine("window", "row", 1))
    stack.execute(SetLayout(a.id, rowspan=2))  # a belegt Zeilen 0 und 1
    b = add(stack, row=2, column=0)
    assert_undo_restores(stack, InsertLine("window", "row", 1))
    a, b = stack.project.find(a.id), stack.project.find(b.id)
    assert a.layout.rowspan == 3
    assert b.layout.row == 3
    assert len(stack.project.window.grid.rows) == 4


def test_remove_line(stack):
    add(stack, row=0, column=0)
    stack.execute(InsertLine("window", "column", 1))
    stack.execute(InsertLine("window", "column", 2))
    label = add(stack, row=0, column=2)
    assert_undo_restores(stack, RemoveLine("window", "column", 1))
    assert stack.project.find(label.id).layout.column == 1
    with pytest.raises(CommandError):
        stack.execute(RemoveLine("window", "column", 1))  # nicht leer


def test_remove_last_line_fails(stack):
    with pytest.raises(CommandError):
        stack.execute(RemoveLine("window", "row", 0))


def test_set_line_config(stack):
    assert_undo_restores(stack, SetLineConfig("window", "column", 0, 1, 0, ""))
    assert stack.project.window.grid.columns[0] == LineConfig(weight=1)
    with pytest.raises(CommandError):
        stack.execute(SetLineConfig("window", "column", 3, 1, 0, ""))
    with pytest.raises(CommandError):
        stack.execute(SetLineConfig("window", "column", 0, -1, 0, ""))


def test_dirty_tracking(stack):
    assert not stack.dirty
    add(stack)
    assert stack.dirty
    stack.mark_saved()
    assert not stack.dirty
    stack.undo()
    assert stack.dirty
    stack.redo()
    assert not stack.dirty
    stack.undo()
    add(stack)  # neuer Zweig: gespeicherter Zustand nicht mehr erreichbar
    assert stack.dirty


def test_execute_notifies(stack):
    calls = []
    stack.project.subscribe(lambda: calls.append(1))
    add(stack)
    stack.undo()
    stack.redo()
    assert calls == [1, 1, 1]
```

- [x] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_commands.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.commands'`

- [x] **Step 3: Implementierung schreiben**

Datei `ctk_builder/commands.py`:

```python
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
```

- [x] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_commands.py -v`

Expected: 26 passed

- [x] **Step 5: Commit**

```bash
git add ctk_builder/commands.py tests/test_commands.py
git commit -m "feat: Befehle mit Undo/Redo für alle Modelländerungen"
```


### Task 6: Beispielprojekt und Projektdateien

Ein gemeinsames Beispielprojekt „kontakt“ (für diesen und alle folgenden Tests) und das
Speichern/Laden als `*.ctkb.json` mit `format_version`. Speichern ist atomar
(temporäre Datei + `os.replace`); beim Laden wird alles geprüft und jeder Fehler als
`ProjectFileError` mit verständlicher Meldung gemeldet.

**Files:**
- Create: `tests/conftest.py`
- Create: `ctk_builder/project_io.py`
- Test: `tests/test_project_io.py`

- [x] **Step 1: Gemeinsame Test-Hilfen anlegen**

`has_display()` darf **nicht** mit `tkinter.Tk()` testen: Ein zerstörtes `tk.Tk` gefolgt von `ctk.CTk` bringt Tk auf macOS zum Absturz (SIGTRAP).

Datei `tests/conftest.py`:

```python
import os
import sys

import pytest

from ctk_builder.commands import (
    AddWidget, CommandStack, InsertLine, RenameWidget, SetLayout, SetLineConfig,
    SetProperty, SetWindowProperty,
)
from ctk_builder.model import Project


def build_kontakt() -> Project:
    """Beispielprojekt: Formular mit Name, E-Mail, Newsletter-Auswahl und Buttons."""
    stack = CommandStack(Project())

    def add(widget_type, parent="window", row=None, column=None, name=None, **props):
        cmd = AddWidget(parent, widget_type, row, column)
        stack.execute(cmd)
        if name:
            stack.execute(RenameWidget(cmd.node_id, name))
        for key, value in props.items():
            stack.execute(SetProperty(cmd.node_id, key, value))
        return cmd.node_id

    stack.execute(SetWindowProperty("class_name", "Kontakt"))
    stack.execute(SetWindowProperty("title", "Kontakt"))
    stack.execute(SetWindowProperty("width", 420))
    stack.execute(SetWindowProperty("height", 260))
    stack.execute(SetWindowProperty("resizable", False))
    stack.execute(SetWindowProperty("appearance_mode", "dark"))

    name_label = add("CTkLabel", row=0, column=0, name="label_name", text="Name:")
    stack.execute(SetLayout(name_label, sticky="w", padx=8, pady=4))
    entry = add("CTkEntry", row=0, column=1, name="entry_name", placeholder_text="Max Muster")
    stack.execute(SetLayout(entry, sticky="ew", padx=8, pady=4))
    add("CTkLabel", row=1, column=0, name="label_mail", text="E-Mail:")
    add("CTkEntry", row=1, column=1, name="entry_mail")
    stack.execute(SetLineConfig("window", "column", 1, 1, 0, ""))

    add("CTkRadioButton", row=2, column=0, name="radio_ja", text="Newsletter",
        variable_group="newsletter", value="ja")
    add("CTkRadioButton", row=2, column=1, name="radio_nein", text="Kein Newsletter",
        variable_group="newsletter", value="nein")

    buttons = add("CTkFrame", row=3, column=0, name="frame_buttons", fg_color="transparent")
    stack.execute(SetLayout(buttons, columnspan=2, sticky="e"))
    stack.execute(InsertLine(buttons, "column", 1))
    add("CTkButton", parent=buttons, row=0, column=0, name="button_cancel",
        text="Abbrechen", command="on_cancel", fg_color="#555555")
    save = add("CTkButton", parent=buttons, row=0, column=1, name="button_save",
               text="Speichern", command="on_save", font_size=14)
    stack.execute(SetLayout(save, padx=4))
    return stack.project


@pytest.fixture
def kontakt() -> Project:
    return build_kontakt()


def has_display() -> bool:
    """Ohne Fenster-Test: unter Linux ohne DISPLAY gibt es keins.

    Achtung: Nicht mit tkinter.Tk() testen – ein zerstörtes tk.Tk gefolgt von
    ctk.CTk bringt Tk auf macOS zum Absturz.
    """
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


requires_display = pytest.mark.skipif(not has_display(), reason="kein Display verfügbar")
```

- [x] **Step 2: Failing Test schreiben**

Datei `tests/test_project_io.py`:

```python
import json

import pytest

from ctk_builder import project_io
from ctk_builder.project_io import FORMAT_VERSION, ProjectFileError


def test_roundtrip(tmp_path, kontakt):
    path = tmp_path / "kontakt.ctkb.json"
    project_io.save(kontakt, path)
    loaded = project_io.load(path)
    assert loaded.window == kontakt.window
    assert not (tmp_path / "kontakt.ctkb.json.tmp").exists()


def test_file_is_readable_json_with_version(tmp_path, kontakt):
    path = tmp_path / "k.ctkb.json"
    project_io.save(kontakt, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format_version"] == FORMAT_VERSION
    assert data["window"]["title"] == "Kontakt"


def write(tmp_path, content):
    path = tmp_path / "x.ctkb.json"
    path.write_text(content, encoding="utf-8")
    return path


def valid_data(kontakt):
    return project_io.to_dict(kontakt)


@pytest.mark.parametrize("content", ["", "{kaputt", "[]", "{}", '{"format_version": 1}'])
def test_broken_files(tmp_path, content):
    with pytest.raises(ProjectFileError):
        project_io.load(write(tmp_path, content))


def test_newer_version_is_rejected(tmp_path, kontakt):
    data = valid_data(kontakt)
    data["format_version"] = FORMAT_VERSION + 1
    with pytest.raises(ProjectFileError, match="neueren"):
        project_io.load(write(tmp_path, json.dumps(data)))


@pytest.mark.parametrize("mutate", [
    lambda w: w["children"][0].__setitem__("type", "CTkGibtsNicht"),
    lambda w: w["children"][0]["props"].__setitem__("unbekannt", 1),
    lambda w: w["children"][0].__setitem__("grid", {"rows": [{}], "columns": [{}]}),
    lambda w: w["children"][0]["layout"].__setitem__("farbe", "rot"),
    lambda w: w["grid"].__setitem__("rows", []),
    lambda w: w.pop("title"),
])
def test_invalid_content(tmp_path, kontakt, mutate):
    data = valid_data(kontakt)
    mutate(data["window"])
    with pytest.raises(ProjectFileError):
        project_io.load(write(tmp_path, json.dumps(data)))


def test_missing_file(tmp_path):
    with pytest.raises(ProjectFileError):
        project_io.load(tmp_path / "fehlt.ctkb.json")
```

- [x] **Step 3: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_project_io.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.project_io'`

- [x] **Step 4: Implementierung schreiben**

Datei `ctk_builder/project_io.py`:

```python
"""Speichern und Laden von Projektdateien (*.ctkb.json)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ctk_builder.model import (
    GridConfig, Layout, LineConfig, Project, WidgetNode, WindowNode,
)
from ctk_builder.widget_specs import SPECS

FORMAT_VERSION = 1
SUFFIX = ".ctkb.json"


class ProjectFileError(Exception):
    """Projektdatei ist beschädigt, unvollständig oder zu neu."""


def to_dict(project: Project) -> dict[str, Any]:
    return {"format_version": FORMAT_VERSION, "window": asdict(project.window)}


def _grid(data: dict) -> GridConfig:
    rows = [LineConfig(**line) for line in data["rows"]]
    columns = [LineConfig(**line) for line in data["columns"]]
    if not rows or not columns:
        raise ProjectFileError("Ein Grid braucht mindestens eine Zeile und Spalte")
    return GridConfig(rows=rows, columns=columns)


def _widget(data: dict) -> WidgetNode:
    if data["type"] not in SPECS:
        raise ProjectFileError(f"Unbekannter Widget-Typ {data['type']!r}")
    spec = SPECS[data["type"]]
    if not isinstance(data["props"], dict):
        raise ProjectFileError("props muss ein Objekt sein")
    for key in data["props"]:
        spec.prop(key)  # KeyError bei unbekannter Eigenschaft
    grid = data.get("grid")
    if spec.is_container != (grid is not None):
        raise ProjectFileError(f"{data['name']}: grid passt nicht zum Typ")
    return WidgetNode(
        id=str(data["id"]),
        type=data["type"],
        name=str(data["name"]),
        props=dict(data["props"]),
        layout=Layout(**data["layout"]),
        grid=_grid(grid) if grid is not None else None,
        children=[_widget(child) for child in data["children"]],
    )


def from_dict(data: Any) -> Project:
    try:
        if not isinstance(data, dict):
            raise ProjectFileError("Keine gültige Projektdatei")
        version = data.get("format_version")
        if not isinstance(version, int):
            raise ProjectFileError("format_version fehlt")
        if version > FORMAT_VERSION:
            raise ProjectFileError(
                f"Die Datei stammt aus einer neueren Builder-Version (Format {version})"
            )
        w = dict(data["window"])
        window = WindowNode(
            id=str(w["id"]),
            class_name=str(w["class_name"]),
            title=str(w["title"]),
            width=int(w["width"]),
            height=int(w["height"]),
            resizable=bool(w["resizable"]),
            appearance_mode=str(w["appearance_mode"]),
            color_theme=str(w["color_theme"]),
            grid=_grid(w["grid"]),
            children=[_widget(child) for child in w["children"]],
        )
    except ProjectFileError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectFileError(f"Projektdatei ist beschädigt: {exc}") from exc
    return Project(window)


def save(project: Project, path: Path) -> None:
    """Speichert atomar: erst temporäre Datei, dann umbenennen."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(to_dict(project), indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def load(path: Path) -> Project:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectFileError(f"Datei kann nicht gelesen werden: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectFileError(f"Keine gültige JSON-Datei: {exc}") from exc
    return from_dict(data)
```

- [x] **Step 5: Tests ausführen**

Run: `.venv/bin/pytest tests/test_project_io.py -v`

Expected: 15 passed

- [x] **Step 6: Commit**

```bash
git add tests/conftest.py ctk_builder/project_io.py tests/test_project_io.py
git commit -m "feat: Projektdateien speichern und laden"
```


### Task 7: Code-Generator

Erzeugt aus dem Modell zwei Quelltexte: `<modul>_ui.py` (Layout, Klasse `<Name>UI`) und
`<modul>.py` (Logik, Klasse `<Name>(<Name>UI)`). Regeln: nur Eigenschaften ungleich dem
CTk-Standardwert, stabile Reihenfolge (Baumreihenfolge), Aufrufe über 88 Zeichen werden
ein Argument pro Zeile umgebrochen, Strings mit doppelten Anführungszeichen.

**Files:**
- Create: `ctk_builder/codegen.py`
- Create: `tests/snapshots/kontakt_ui.py.txt`, `tests/snapshots/kontakt.py.txt`
- Test: `tests/test_codegen.py`

- [x] **Step 1: Failing Test schreiben**

Datei `tests/test_codegen.py`:

```python
import os
import sys
from pathlib import Path

from conftest import build_kontakt, requires_display
from ctk_builder.codegen import HEADER, generate
from ctk_builder.model import Project

SNAPSHOTS = Path(__file__).parent / "snapshots"


def check_snapshot(name: str, actual: str) -> None:
    """Vergleicht mit tests/snapshots/<name>; UPDATE_SNAPSHOTS=1 schreibt neu."""
    path = SNAPSHOTS / name
    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.write_text(actual, encoding="utf-8")
    assert actual == path.read_text(encoding="utf-8")


def test_ui_snapshot(kontakt):
    check_snapshot("kontakt_ui.py.txt", generate(kontakt, "kontakt").ui_source)


def test_logic_snapshot(kontakt):
    check_snapshot("kontakt.py.txt", generate(kontakt, "kontakt").logic_source)


def test_empty_project():
    files = generate(Project(), "leer")
    assert files.ui_source.startswith(HEADER + "\n")
    assert "class AppUI(ctk.CTk):" in files.ui_source
    assert "    pass" in files.logic_source
    compile(files.ui_source, "leer_ui.py", "exec")
    compile(files.logic_source, "leer.py", "exec")


def test_generated_code_compiles(kontakt):
    files = generate(kontakt, "kontakt")
    compile(files.ui_source, "kontakt_ui.py", "exec")
    compile(files.logic_source, "kontakt.py", "exec")


def test_deterministic():
    assert generate(build_kontakt(), "kontakt") == generate(build_kontakt(), "kontakt")


@requires_display
def test_generated_ui_runs(tmp_path, kontakt, monkeypatch):
    """Instanziiert das generierte Fenster wirklich."""
    files = generate(kontakt, "kontakt")
    (tmp_path / "kontakt_ui.py").write_text(files.ui_source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("kontakt_ui", None)
    import kontakt_ui

    app = kontakt_ui.KontaktUI()
    try:
        app.update()
        assert app.entry_name.cget("placeholder_text") == "Max Muster"
        assert app.button_save.grid_info()["column"] == 1
    finally:
        app.destroy()
```

- [x] **Step 2: Referenzausgabe für die UI-Datei anlegen**

Das ist exakt die erwartete Ausgabe für das Beispielprojekt aus `conftest.py`. Bei späteren, gewollten Änderungen am Generator die Snapshots mit `UPDATE_SNAPSHOTS=1 .venv/bin/pytest tests/test_codegen.py` neu schreiben und den Diff prüfen.

Datei `tests/snapshots/kontakt_ui.py.txt`:

```python
# AUTOMATISCH GENERIERT von CTk Builder – nicht von Hand bearbeiten!
# Eigene Logik gehört in kontakt.py.
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class KontaktUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Kontakt")
        self.geometry("420x260")
        self.resizable(False, False)
        self.grid_columnconfigure(1, weight=1)

        self.newsletter = ctk.StringVar(value="")

        self.label_name = ctk.CTkLabel(self, text="Name:")
        self.label_name.grid(row=0, column=0, padx=8, pady=4, sticky="w")

        self.entry_name = ctk.CTkEntry(self, placeholder_text="Max Muster")
        self.entry_name.grid(row=0, column=1, padx=8, pady=4, sticky="ew")

        self.label_mail = ctk.CTkLabel(self, text="E-Mail:")
        self.label_mail.grid(row=1, column=0)

        self.entry_mail = ctk.CTkEntry(self)
        self.entry_mail.grid(row=1, column=1)

        self.radio_ja = ctk.CTkRadioButton(
            self,
            text="Newsletter",
            variable=self.newsletter,
            value="ja",
        )
        self.radio_ja.grid(row=2, column=0)

        self.radio_nein = ctk.CTkRadioButton(
            self,
            text="Kein Newsletter",
            variable=self.newsletter,
            value="nein",
        )
        self.radio_nein.grid(row=2, column=1)

        self.frame_buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_buttons.grid(row=3, column=0, columnspan=2, sticky="e")
        self.button_cancel = ctk.CTkButton(
            self.frame_buttons,
            text="Abbrechen",
            fg_color="#555555",
            command=self.on_cancel,
        )
        self.button_cancel.grid(row=0, column=0)
        self.button_save = ctk.CTkButton(
            self.frame_buttons,
            text="Speichern",
            font=ctk.CTkFont(size=14),
            command=self.on_save,
        )
        self.button_save.grid(row=0, column=1, padx=4)

    def on_cancel(self):
        raise NotImplementedError("on_cancel in kontakt.py implementieren")

    def on_save(self):
        raise NotImplementedError("on_save in kontakt.py implementieren")
```

- [x] **Step 3: Referenzausgabe für die Logik-Datei anlegen**

Datei `tests/snapshots/kontakt.py.txt`:

```python
from kontakt_ui import KontaktUI


class Kontakt(KontaktUI):
    def on_cancel(self):
        pass

    def on_save(self):
        pass


if __name__ == "__main__":
    app = Kontakt()
    app.mainloop()
```

- [x] **Step 4: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_codegen.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.codegen'`

- [x] **Step 5: Implementierung schreiben**

Datei `ctk_builder/codegen.py`:

```python
"""Erzeugt Python-Quelltext aus dem Projektmodell. Keine GUI-Abhängigkeit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ctk_builder.model import LineConfig, Node, Project, WidgetNode
from ctk_builder.widget_specs import GROUP, HANDLER, SPECS

HEADER = "# AUTOMATISCH GENERIERT von CTk Builder – nicht von Hand bearbeiten!"
MAX_LINE = 88


@dataclass(frozen=True)
class GeneratedFiles:
    ui_source: str
    logic_source: str


def _lit(value: Any) -> str:
    """Python-Literal mit doppelten Anführungszeichen für Strings."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def _call(indent: str, head: str, args: list[str]) -> list[str]:
    """head(args...) in eine Zeile, oder ein Argument pro Zeile, wenn zu lang."""
    one_line = f"{indent}{head}({', '.join(args)})"
    if len(one_line) <= MAX_LINE or not args:
        return [one_line]
    lines = [f"{indent}{head}("]
    lines += [f"{indent}    {arg}," for arg in args]
    lines.append(f"{indent})")
    return lines


def _line_config_args(config: LineConfig) -> list[str]:
    args = []
    if config.weight:
        args.append(f"weight={config.weight}")
    if config.minsize:
        args.append(f"minsize={config.minsize}")
    if config.uniform:
        args.append(f"uniform={_lit(config.uniform)}")
    return args


def _grid_config(indent: str, target: str, node: Node) -> list[str]:
    lines = []
    for axis, configs in (("row", node.grid.rows), ("column", node.grid.columns)):
        for index, config in enumerate(configs):
            args = _line_config_args(config)
            if args:
                lines += _call(indent, f"{target}.grid_{axis}configure", [str(index), *args])
    return lines


def _widget_args(widget: WidgetNode, master: str) -> list[str]:
    spec = SPECS[widget.type]
    args = [master]
    for prop in spec.props:
        value = widget.props.get(prop.name, prop.default)
        if prop.kind == GROUP:
            if value is not None:
                args.append(f"variable=self.{value}")
                value_prop = widget.props.get("value") or widget.name
                args.append(f"value={_lit(value_prop)}")
            continue
        if prop.name == "value":
            continue  # wird zusammen mit variable_group ausgegeben
        if value == prop.default:
            continue
        if prop.kind == HANDLER:
            args.append(f"{prop.name}=self.{value}")
        elif prop.name == "font_size":
            args.append(f"font=ctk.CTkFont(size={value})")
        else:
            args.append(f"{prop.name}={_lit(value)}")
    return args


def _grid_args(widget: WidgetNode) -> list[str]:
    layout = widget.layout
    args = [f"row={layout.row}", f"column={layout.column}"]
    if layout.rowspan != 1:
        args.append(f"rowspan={layout.rowspan}")
    if layout.columnspan != 1:
        args.append(f"columnspan={layout.columnspan}")
    if layout.padx:
        args.append(f"padx={layout.padx}")
    if layout.pady:
        args.append(f"pady={layout.pady}")
    if layout.sticky:
        args.append(f"sticky={_lit(layout.sticky)}")
    return args


def _widget_lines(widget: WidgetNode, master: str) -> list[str]:
    indent = " " * 8
    attr = f"self.{widget.name}"
    lines = _call(indent, f"{attr} = ctk.{widget.type}", _widget_args(widget, master))
    lines += _call(indent, f"{attr}.grid", _grid_args(widget))
    if widget.is_container:
        lines += _grid_config(indent, attr, widget)
    for child in widget.children:
        lines += _widget_lines(child, attr)
    return lines


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def handler_names(project: Project) -> list[str]:
    return _ordered_unique([w.props.get("command") for w in project.iter_widgets()])


def group_names(project: Project) -> list[str]:
    return _ordered_unique([w.props.get("variable_group") for w in project.iter_widgets()])


def generate_ui(project: Project, module_name: str) -> str:
    window = project.window
    indent = " " * 8
    out = [
        HEADER,
        f"# Eigene Logik gehört in {module_name}.py.",
        "import customtkinter as ctk",
        "",
        f"ctk.set_appearance_mode({_lit(window.appearance_mode)})",
        f"ctk.set_default_color_theme({_lit(window.color_theme)})",
        "",
        "",
        f"class {window.class_name}UI(ctk.CTk):",
        "    def __init__(self):",
        "        super().__init__()",
        f"        self.title({_lit(window.title)})",
        f"        self.geometry(\"{window.width}x{window.height}\")",
    ]
    if not window.resizable:
        out.append("        self.resizable(False, False)")
    out += _grid_config(indent, "self", window)

    groups = group_names(project)
    if groups:
        out.append("")
        out += [f"{indent}self.{g} = ctk.StringVar(value=\"\")" for g in groups]

    for child in window.children:
        out.append("")
        out += _widget_lines(child, "self")

    for handler in handler_names(project):
        out += [
            "",
            f"    def {handler}(self):",
            f"        raise NotImplementedError(\"{handler} in {module_name}.py implementieren\")",
        ]
    return "\n".join(out) + "\n"


def generate_logic(project: Project, module_name: str) -> str:
    cls = project.window.class_name
    out = [
        f"from {module_name}_ui import {cls}UI",
        "",
        "",
        f"class {cls}({cls}UI):",
    ]
    handlers = handler_names(project)
    if handlers:
        for i, handler in enumerate(handlers):
            if i:
                out.append("")
            out += [f"    def {handler}(self):", "        pass"]
    else:
        out.append("    pass")
    out += [
        "",
        "",
        'if __name__ == "__main__":',
        f"    app = {cls}()",
        "    app.mainloop()",
    ]
    return "\n".join(out) + "\n"


def generate(project: Project, module_name: str) -> GeneratedFiles:
    return GeneratedFiles(
        ui_source=generate_ui(project, module_name),
        logic_source=generate_logic(project, module_name),
    )
```

- [x] **Step 6: Tests ausführen**

Run: `.venv/bin/pytest tests/test_codegen.py -v`

Expected: 6 passed (unter Linux ohne Display: 5 passed, 1 skipped – dann mit `xvfb-run -a` wiederholen)

- [x] **Step 7: Commit**

```bash
git add ctk_builder/codegen.py tests/test_codegen.py tests/snapshots
git commit -m "feat: Code-Generator für UI- und Logik-Datei"
```


### Task 8: Export auf die Platte

Schreibt `<modul>_ui.py` (immer, atomar) und `<modul>.py` (nur wenn noch nicht vorhanden) neben die Projektdatei. Fehlt in einer vorhandenen UI-Datei der Kopfkommentar, wirft `export()` `ExportNeedsConfirmation` – erst mit `force=True` wird überschrieben.

**Files:**
- Create: `ctk_builder/exporter.py`
- Test: `tests/test_exporter.py`

- [x] **Step 1: Failing Test schreiben**

Datei `tests/test_exporter.py`:

```python
import pytest

from ctk_builder.codegen import HEADER
from ctk_builder.exporter import ExportNeedsConfirmation, export, module_name_for


@pytest.mark.parametrize("filename,expected", [
    ("kontakt.ctkb.json", "kontakt"),
    ("Mein Fenster.ctkb.json", "mein_fenster"),
    ("2fa.ctkb.json", "app_2fa"),
    ("class.ctkb.json", "app_class"),
    ("x.json", "x"),
])
def test_module_name_for(filename, expected):
    assert module_name_for(filename) == expected


def test_first_export_creates_both_files(tmp_path, kontakt):
    result = export(kontakt, tmp_path / "kontakt.ctkb.json")
    assert result.ui_path == tmp_path / "kontakt_ui.py"
    assert result.logic_path == tmp_path / "kontakt.py"
    assert result.logic_created
    assert result.ui_path.read_text(encoding="utf-8").startswith(HEADER)


def test_second_export_keeps_logic_file(tmp_path, kontakt):
    path = tmp_path / "kontakt.ctkb.json"
    export(kontakt, path)
    (tmp_path / "kontakt.py").write_text("# meine Logik\n", encoding="utf-8")
    kontakt.window.title = "Geändert"
    result = export(kontakt, path)
    assert not result.logic_created
    assert (tmp_path / "kontakt.py").read_text(encoding="utf-8") == "# meine Logik\n"
    assert '"Geändert"' in (tmp_path / "kontakt_ui.py").read_text(encoding="utf-8")


def test_hand_edited_ui_file_needs_confirmation(tmp_path, kontakt):
    path = tmp_path / "kontakt.ctkb.json"
    (tmp_path / "kontakt_ui.py").write_text("# von Hand\n", encoding="utf-8")
    with pytest.raises(ExportNeedsConfirmation):
        export(kontakt, path)
    assert (tmp_path / "kontakt_ui.py").read_text(encoding="utf-8") == "# von Hand\n"
    export(kontakt, path, force=True)
    assert (tmp_path / "kontakt_ui.py").read_text(encoding="utf-8").startswith(HEADER)
```

- [x] **Step 2: Test ausführen und Fehlschlag prüfen**

Run: `.venv/bin/pytest tests/test_exporter.py -v`

Expected: FAIL mit `ModuleNotFoundError: No module named 'ctk_builder.exporter'`

- [x] **Step 3: Implementierung schreiben**

Datei `ctk_builder/exporter.py`:

```python
"""Schreibt die generierten Dateien neben die Projektdatei."""

from __future__ import annotations

import keyword
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ctk_builder.codegen import HEADER, generate
from ctk_builder.model import Project
from ctk_builder.project_io import SUFFIX


class ExportNeedsConfirmation(Exception):
    """Die UI-Datei wurde vermutlich von Hand bearbeitet."""


@dataclass(frozen=True)
class ExportResult:
    ui_path: Path
    logic_path: Path
    logic_created: bool


def module_name_for(project_path: Path) -> str:
    """kontakt.ctkb.json -> kontakt; macht den Namen zu einem gültigen Modulnamen."""
    name = Path(project_path).name
    if name.endswith(SUFFIX):
        name = name[: -len(SUFFIX)]
    else:
        name = Path(name).stem
    name = re.sub(r"\W", "_", name.lower()) or "app"
    if name[0].isdigit() or keyword.iskeyword(name):
        name = f"app_{name}"
    return name


def export(project: Project, project_path: Path, force: bool = False) -> ExportResult:
    project_path = Path(project_path)
    module = module_name_for(project_path)
    folder = project_path.parent
    ui_path = folder / f"{module}_ui.py"
    logic_path = folder / f"{module}.py"

    if ui_path.exists() and not force:
        first_line = ui_path.read_text(encoding="utf-8").split("\n", 1)[0]
        if first_line != HEADER:
            raise ExportNeedsConfirmation(
                f"{ui_path.name} wurde offenbar von Hand bearbeitet. Trotzdem überschreiben?"
            )

    files = generate(project, module)
    tmp = ui_path.with_name(ui_path.name + ".tmp")
    tmp.write_text(files.ui_source, encoding="utf-8")
    os.replace(tmp, ui_path)

    logic_created = not logic_path.exists()
    if logic_created:
        logic_path.write_text(files.logic_source, encoding="utf-8")
    return ExportResult(ui_path, logic_path, logic_created)
```

- [x] **Step 4: Tests ausführen**

Run: `.venv/bin/pytest tests/test_exporter.py -v`

Expected: 8 passed

- [x] **Step 5: Commit**

```bash
git add ctk_builder/exporter.py tests/test_exporter.py
git commit -m "feat: Export der generierten Dateien"
```


### Task 9: Abschluss Plan 1

- [x] **Step 1: Komplette Testsuite**

Run: `.venv/bin/pytest -v` (Linux ohne Display: `xvfb-run -a .venv/bin/pytest -v`)

Expected: `107 passed`

- [x] **Step 2: Pushen**

```bash
git push
```
