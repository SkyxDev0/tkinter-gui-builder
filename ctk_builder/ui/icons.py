"""Vektor-Icons und Widget-Vorschauen auf tkinter.Canvas.

Ohne Bilddateien und ohne Pillow; die Linien bleiben auf jedem Bildschirm scharf.
Alle Icons sind in einem 24er-Raster entworfen und werden auf size skaliert.
"""

from __future__ import annotations

import tkinter

from ctk_builder.ui import theme

ICONS = ("widgets", "tree", "undo", "redo", "copy", "trash", "grid", "play")


def round_rect(canvas: tkinter.Canvas, x1: float, y1: float, x2: float, y2: float,
               r: float, **options) -> int:
    """Rechteck mit runden Ecken (geglättetes Polygon)."""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
              x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
              x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
              x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **options)


def draw_icon(canvas: tkinter.Canvas, name: str, cx: float, cy: float, size: float,
              color: str, bg: str) -> None:
    """Zeichnet Icon name zentriert auf (cx, cy)."""
    s = size / 24
    left, top = cx - size / 2, cy - size / 2

    def p(*coords: float) -> list[float]:
        return [left + c * s if i % 2 == 0 else top + c * s for i, c in enumerate(coords)]

    width = max(1.5, 1.8 * s)
    stroke = dict(fill=color, width=width, capstyle="round", joinstyle="round")
    outline = dict(fill="", outline=color, width=width)

    if name == "widgets":
        for x, y in ((3.5, 3.5), (13.5, 3.5), (3.5, 13.5), (13.5, 13.5)):
            round_rect(canvas, *p(x, y, x + 7, y + 7), 2 * s, **outline)
    elif name == "tree":
        round_rect(canvas, *p(3, 3, 14, 8), 2 * s, **outline)
        round_rect(canvas, *p(10, 10.5, 21, 15), 2 * s, **outline)
        round_rect(canvas, *p(10, 17, 21, 21.5), 2 * s, **outline)
        canvas.create_line(p(6, 8, 6, 19.2, 10, 19.2), **stroke)
        canvas.create_line(p(6, 12.8, 10, 12.8), **stroke)
    elif name in ("undo", "redo"):
        flip = (lambda x: 24 - x) if name == "redo" else (lambda x: x)
        canvas.create_line(p(flip(19), 18, flip(19), 13, flip(16), 9, flip(6), 9),
                           smooth=True, **stroke)
        canvas.create_line(p(flip(10), 5, flip(6), 9, flip(10), 13), **stroke)
    elif name == "copy":
        round_rect(canvas, *p(8.5, 3.5, 20.5, 15.5), 2.5 * s, **outline)
        round_rect(canvas, *p(3.5, 8.5, 15.5, 20.5), 2.5 * s, fill=bg, outline=color,
                   width=width)
    elif name == "trash":
        canvas.create_line(p(4, 6.5, 20, 6.5), **stroke)
        canvas.create_line(p(9.5, 6.5, 9.5, 4, 14.5, 4, 14.5, 6.5), **stroke)
        canvas.create_polygon(p(6, 6.5, 7, 20, 17, 20, 18, 6.5), fill="", outline=color,
                              width=width, joinstyle="round")
        canvas.create_line(p(10, 10, 10, 16.5), **stroke)
        canvas.create_line(p(14, 10, 14, 16.5), **stroke)
    elif name == "grid":
        round_rect(canvas, *p(4, 4, 20, 20), 2.5 * s, **outline)
        for c in (9.33, 14.67):
            canvas.create_line(p(c, 4, c, 20), **stroke)
            canvas.create_line(p(4, c, 20, c), **stroke)
    elif name == "play":
        canvas.create_polygon(p(8, 5, 19, 12, 8, 19), fill=color, outline=color,
                              width=width, joinstyle="round")
    else:
        raise ValueError(f"Unbekanntes Icon {name!r}")


def draw_preview(canvas: tkinter.Canvas, widget_type: str, cx: float, cy: float) -> None:
    """Kleine Vorschau eines Widget-Typs (72 × 44) für die Palette."""
    accent = theme.pick(theme.ACCENT)
    gray = theme.pick(("#d5d9e0", "#3f3f46"))
    edge = theme.pick(("#c4cad3", "#52525b"))
    field = theme.pick(theme.INPUT)
    white = "#ffffff"
    left, top = cx - 36, cy - 22

    def p(*coords: float) -> list[float]:
        return [left + c if i % 2 == 0 else top + c for i, c in enumerate(coords)]

    def bar(x1: float, x2: float, y: float, color: str = gray, width: float = 3) -> None:
        canvas.create_line(p(x1, y, x2, y), fill=color, width=width, capstyle="round")

    if widget_type == "CTkLabel":
        canvas.create_text(cx, cy, text="Aa", fill=theme.pick(theme.TEXT),
                           font=theme.tk_font(20, "bold"))
    elif widget_type == "CTkButton":
        round_rect(canvas, *p(12, 12, 60, 32), 8, fill=accent, outline="")
        bar(26, 46, 22, white)
    elif widget_type == "CTkEntry":
        round_rect(canvas, *p(8, 12, 64, 32), 7, fill=field, outline=edge, width=1.5)
        canvas.create_line(p(16, 16, 16, 28), fill=accent, width=2)
        bar(22, 44, 22)
    elif widget_type == "CTkTextbox":
        round_rect(canvas, *p(12, 4, 60, 40), 7, fill=field, outline=edge, width=1.5)
        for y, x2 in ((13, 51), (22, 45), (31, 49)):
            bar(20, x2, y)
    elif widget_type == "CTkCheckBox":
        round_rect(canvas, *p(12, 13, 30, 31), 5, fill=accent, outline="")
        canvas.create_line(p(16.5, 22, 20, 25.5, 26, 18), fill=white, width=2.5,
                           capstyle="round", joinstyle="round")
        bar(36, 60, 22)
    elif widget_type == "CTkSwitch":
        round_rect(canvas, *p(10, 13, 40, 31), 9, fill=accent, outline="")
        canvas.create_oval(p(25, 15, 39, 29), fill=white, outline="")
        bar(46, 62, 22)
    elif widget_type == "CTkRadioButton":
        canvas.create_oval(p(12, 13, 30, 31), fill=field, outline=accent, width=2.5)
        canvas.create_oval(p(17, 18, 25, 26), fill=accent, outline="")
        bar(36, 60, 22)
    elif widget_type == "CTkFrame":
        round_rect(canvas, *p(10, 5, 62, 39), 7, fill=field, outline=edge, width=1.5)
        round_rect(canvas, *p(16, 11, 34, 21), 3, fill=gray, outline="")
        round_rect(canvas, *p(38, 11, 56, 21), 3, fill=gray, outline="")
        round_rect(canvas, *p(16, 25, 56, 33), 3, fill=gray, outline="")
    else:
        raise ValueError(f"Keine Vorschau für {widget_type!r}")
