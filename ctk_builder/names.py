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
