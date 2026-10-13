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
