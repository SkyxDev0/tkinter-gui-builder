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
