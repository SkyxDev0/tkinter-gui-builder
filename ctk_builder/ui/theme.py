"""Farben und Schriften des Builders.

Farben sind (hell, dunkel)-Tupel: CTk-Widgets wechseln damit selbst. Reine
Tk-Widgets (Canvas, Label, Treeview) bekommen über pick() den Wert für den
aktuellen Modus.
"""

from __future__ import annotations

import sys

import customtkinter as ctk

Color = tuple[str, str]

BG: Color = ("#f3f4f6", "#121214")            # Fensterhintergrund
CARD: Color = ("#ffffff", "#1c1c1f")          # Panels und Karten
HOVER: Color = ("#f1f3f5", "#27272b")         # Hover auf Karten
BORDER: Color = ("#e5e7eb", "#2c2c31")
TEXT: Color = ("#111827", "#f4f4f5")
MUTED: Color = ("#6b7280", "#a1a1aa")
ACCENT: Color = ("#2563eb", "#3b82f6")
ACCENT_HOVER: Color = ("#1d4ed8", "#2563eb")
ACCENT_SOFT: Color = ("#e0eaff", "#1e2b4a")   # ausgewählte Einträge
ACCENT_TEXT: Color = ("#1d4ed8", "#93b4ff")
DANGER: Color = ("#dc2626", "#f87171")
DANGER_SOFT: Color = ("#fee2e2", "#3b1c1c")
INPUT: Color = ("#ffffff", "#141416")
PRIMARY: Color = ("#111827", "#f4f4f5")       # dunkler Hauptknopf (Ausführen)
PRIMARY_HOVER: Color = ("#374151", "#d4d4d8")
PRIMARY_TEXT: Color = ("#ffffff", "#111827")
CANVAS_BG: Color = ("#eceef2", "#0d0d0f")     # Arbeitsfläche
CANVAS_GRID: Color = ("#e0e3e8", "#18181b")
CHROME: Color = ("#ffffff", "#1c1c1f")        # Rahmen des entworfenen Fensters
CONSOLE_BG: Color = ("#f8fafc", "#141416")
HEADER_BG: Color = ("#e2e5ea", "#26262b")     # Zeilen-/Spaltenköpfe
GRID_LINE: Color = ("#c5cad3", "#3a3a40")
SELECT = "#f97316"                            # Auswahlrahmen (orange)
DROP = "#22c55e"                              # Drop-Ziel (grün)
GUIDE = "#ec4899"                             # Hilfslinien beim freien Verschieben (pink)

RADIUS = 12
MONO_FAMILY = {"darwin": "Menlo", "win32": "Consolas"}.get(sys.platform, "DejaVu Sans Mono")


def pick(color: Color | str) -> str:
    """Farbwert für den aktuellen Modus (für reine Tk-Widgets)."""
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(size=size, weight=weight)


def tk_font(size: int = 13, weight: str = "normal") -> tuple[str, int, str]:
    """Schrift als Tupel für reine Tk-/ttk-Widgets und Canvas-Texte.

    Ein CTkFont-Objekt wäre ein benannter Tk-Font, der beim Aufräumen des
    Python-Objekts gelöscht wird – ttk-Stile fallen dann auf die Standardschrift
    zurück. Negative Größe = Pixel, wie bei CTkFont.
    """
    return (ctk.ThemeManager.theme["CTkFont"]["family"], -size, weight)


def mono(size: int = 12) -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FAMILY, size=size)


def card(master, **kwargs) -> ctk.CTkFrame:
    """Weiße Karte mit dünnem Rand und runden Ecken."""
    options = dict(fg_color=CARD, corner_radius=RADIUS, border_width=1, border_color=BORDER)
    options.update(kwargs)
    return ctk.CTkFrame(master, **options)


def secondary_button(master, **kwargs) -> ctk.CTkButton:
    options = dict(fg_color=CARD, hover_color=HOVER, text_color=TEXT, border_width=1,
                   border_color=BORDER, corner_radius=8, height=34, font=font(13))
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def primary_button(master, **kwargs) -> ctk.CTkButton:
    options = dict(fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color=PRIMARY_TEXT,
                   corner_radius=8, height=34, font=font(13, "bold"))
    options.update(kwargs)
    return ctk.CTkButton(master, **options)
