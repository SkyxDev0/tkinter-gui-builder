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
