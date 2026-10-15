"""Geometrie für freie Container: Größen, freie Stellen, Umwandlung in ein Raster.

Ohne Tkinter: Die Arbeitsfläche kann echte Messwerte liefern (rects); fehlen sie,
schätzt size_hint() die Größe aus den Eigenschaften.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional

from ctk_builder.model import Node, WidgetNode, WindowNode
from ctk_builder.widget_specs import SPECS

MARGIN = 16       # Abstand neuer Widgets vom Containerrand
GAP = 8           # Abstand zwischen Widgets (freie Stelle, „darunter“)
SCAN_STEP = 8     # Schrittweite der Suche nach einer freien Stelle
CHAR_WIDTH = 6.5  # geschätzte Zeichenbreite bei Schriftgröße 13
DEFAULT_FONT = 13

# Kästchen und Mindestbreite von Widgets ohne width/height-Eigenschaft
_BOXED = {
    "CTkCheckBox": (24, 24),
    "CTkSwitch": (36, 24),
    "CTkRadioButton": (22, 22),
}
_BOXED_MIN_WIDTH = 100


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def overlaps(self, other: Rect, gap: int = 0) -> bool:
        return (self.x < other.right + gap and other.x < self.right + gap
                and self.y < other.bottom + gap and other.y < self.bottom + gap)


Rects = Mapping[str, Rect]  # Knoten-ID -> gemessene Geometrie (logische Pixel)


def to_physical(value: float, scaling: float) -> int:
    """Logisch -> physisch, genau wie CTk (int(v * s))."""
    return int(value * scaling)


def to_logical(pixels: int, scaling: float) -> int:
    """Physisch -> logisch; exakte Umkehrung von to_physical (round() verlöre bei
    125 % jede vierte Position, int() bei 150 % jede zweite)."""
    return math.ceil(pixels / scaling - 1e-9)


def _text_width(node: WidgetNode) -> int:
    spec = SPECS[node.type]
    text = node.props.get("text", spec.prop("text").default) if _has(node, "text") else ""
    size = node.props.get("font_size") or DEFAULT_FONT
    return round(len(str(text)) * CHAR_WIDTH * size / DEFAULT_FONT) + 2


def _has(node: WidgetNode, prop: str) -> bool:
    return any(p.name == prop for p in SPECS[node.type].props)


def _prop(node: WidgetNode, prop: str) -> int:
    return node.props.get(prop, SPECS[node.type].prop(prop).default)


def size_hint(node: WidgetNode) -> tuple[int, int]:
    """Geschätzte Größe in logischen Pixeln (ohne Messung auf der Arbeitsfläche)."""
    if node.type in _BOXED:
        box_width, box_height = _BOXED[node.type]
        width = max(_BOXED_MIN_WIDTH, box_width + 6 + _text_width(node))
        return width, box_height
    width = _prop(node, "width")
    if width == 0:  # CTkLabel: 0 = so breit wie der Text
        width = max(_text_width(node), 20)
    return width, _prop(node, "height")


def rect_of(node: WidgetNode, rects: Optional[Rects] = None) -> Rect:
    """Gemessene Geometrie, sonst Position aus dem Modell und geschätzte Größe."""
    if rects and node.id in rects:
        return rects[node.id]
    width, height = size_hint(node)
    return Rect(node.layout.x, node.layout.y, width, height)


def container_size(node: Node) -> tuple[int, int]:
    """Innenmaße eines freien Containers (Fenster bzw. width/height des Frames)."""
    if isinstance(node, WindowNode):
        return node.width, node.height
    return _prop(node, "width"), _prop(node, "height")


def clamp_to(size: tuple[int, int], x: int, y: int, width: int,
             height: int) -> tuple[int, int]:
    """Hält die Position in einem Container der Größe size: nicht links/oben
    hinaus und, wenn das Widget hineinpasst, auch nicht rechts/unten."""
    container_width, container_height = size
    x = min(x, container_width - width) if width <= container_width else 0
    y = min(y, container_height - height) if height <= container_height else 0
    return max(x, 0), max(y, 0)


def clamp(container: Node, x: int, y: int, width: int, height: int,
          rects: Optional[Rects] = None) -> tuple[int, int]:
    """Wie clamp_to; Containergröße gemessen (rects) oder aus dem Modell."""
    if rects and container.id in rects:
        size = (rects[container.id].width, rects[container.id].height)
    else:
        size = container_size(container)
    return clamp_to(size, x, y, width, height)


def free_spot(container: Node, size: tuple[int, int],
              ignore: frozenset[str] = frozenset(),
              rects: Optional[Rects] = None) -> tuple[int, int]:
    """Erste Stelle (zeilenweise von links oben), an der ein Widget dieser Größe
    keine Geschwister überdeckt. Ist der Container voll: versetzt links oben."""
    width, height = size
    others = [rect_of(child, rects) for child in container.children if child.id not in ignore]
    if rects and container.id in rects:
        container_width, container_height = rects[container.id].width, rects[container.id].height
    else:
        container_width, container_height = container_size(container)
    for y in range(MARGIN, max(container_height - height, MARGIN) + 1, SCAN_STEP):
        for x in range(MARGIN, max(container_width - width, MARGIN) + 1, SCAN_STEP):
            candidate = Rect(x, y, width, height)
            if not any(candidate.overlaps(other, GAP) for other in others):
                return x, y
    offset = MARGIN + 16 * (len(others) % 8)
    return clamp(container, offset, offset, width, height, rects)


def spot_below(container: Node, size: tuple[int, int], anchor: Optional[str] = None,
               ignore: frozenset[str] = frozenset(),
               rects: Optional[Rects] = None) -> tuple[int, int]:
    """Stelle für ein neues Widget: unter anchor (bzw. unter dem untersten Kind) mit
    gleicher linker Kante – so ergeben aufeinanderfolgende Klicks eine Spalte. Passt
    es dort nicht hinein, die erste freie Stelle."""
    children = [c for c in container.children if c.id not in ignore]
    if not children:
        return MARGIN, MARGIN
    above = next((c for c in children if c.id == anchor), None)
    if above is None:
        above = max(children, key=lambda c: (rect_of(c, rects).bottom, rect_of(c, rects).x))
    rect = rect_of(above, rects)
    x, y = rect.x, rect.bottom + GAP
    height = rects[container.id].height if rects and container.id in rects \
        else container_size(container)[1]
    others = [rect_of(c, rects) for c in children]
    while y + size[1] <= height:
        candidate = Rect(x, y, *size)
        blocking = [o for o in others if candidate.overlaps(o)]
        if not blocking:
            return clamp(container, x, y, *size, rects=rects)
        y = max(o.bottom for o in blocking) + GAP  # unter dem, was im Weg liegt
    return free_spot(container, size, ignore, rects)


ALIGN = 4      # Kante so nah am Bandrand: Widget wird dorthin ausgerichtet (sticky)
GRID_PAD = 4   # Abstand der Widgets nach Frei -> Raster


def _merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if bands and start < bands[-1][1]:
            bands[-1] = (bands[-1][0], max(bands[-1][1], end))
        else:
            bands.append((start, end))
    return bands


def bands(intervals: Mapping[str, tuple[int, int]]) -> list[tuple[int, int]]:
    """Zeilen bzw. Spalten auf einer Achse: maximale Strecken ohne Lücke.

    Verbindet ein einzelnes großes Widget sonst getrennte Bänder (z. B. eine hohe
    Textbox neben drei Labels), zählt es nicht mit – es überspannt sie später.
    """

    def extent(i: str) -> int:
        return intervals[i][1] - intervals[i][0]

    def split(ids: list[str]) -> list[tuple[int, int]]:
        result = []
        for band in _merge([intervals[i] for i in ids]):
            members = [i for i in ids if band[0] <= intervals[i][0] < band[1]]
            # Überlappen sich alle gegenseitig, haben sie einen gemeinsamen Punkt:
            # dann trennt kein Herausnehmen das Band (häufigster Fall: eine Spalte
            # bündig ausgerichteter Widgets)
            if len(members) < 2 or (max(intervals[i][0] for i in members)
                                    < min(intervals[i][1] for i in members)):
                result.append(band)
                continue
            # Das Widget, ohne das das Band in die meisten Teile zerfällt (bei
            # Gleichstand das größte), überspannt sie. Kein Zurückverfolgen:
            # höchstens n Ebenen mit je n Versuchen.
            best, parts = None, 1
            for candidate in sorted(members, key=extent, reverse=True):
                count = len(_merge([intervals[i] for i in members if i != candidate]))
                if count > parts:
                    best, parts = candidate, count
            if best is None:
                result.append(band)
            else:
                result += split([i for i in members if i != best])
        return result

    return split(list(intervals))


def _span(interval: tuple[int, int], axis_bands: list[tuple[int, int]]) -> tuple[int, int]:
    """(erstes Band, Anzahl) der Bänder, die das Intervall überlappt."""
    hits = [i for i, (start, end) in enumerate(axis_bands)
            if start < interval[1] and interval[0] < end]
    if not hits:  # kann nur bei Rundungsfällen passieren: nächstes Band
        hits = [min(range(len(axis_bands)), key=lambda i: abs(axis_bands[i][0] - interval[0]))]
    return hits[0], hits[-1] - hits[0] + 1


def grid_cells(children: list[WidgetNode], rects: Optional[Rects] = None
               ) -> tuple[dict[str, dict[str, object]], int, int]:
    """Verteilt frei platzierte Widgets auf ein Raster.

    Zeilen und Spalten sind Bänder ohne Lücke (siehe bands); ein Widget, das
    mehrere Bänder überdeckt, bekommt rowspan/columnspan. sticky folgt der
    Ausrichtung im Band (Kante bündig mit dem Bandrand). Überschneidungen werden
    in Lesereihenfolge aufgelöst. Liefert {ID: Layout-Felder}, Zeilen, Spalten.
    """
    if not children:
        return {}, 1, 1
    boxes = {c.id: rect_of(c, rects) for c in children}
    rows = bands({i: (r.y, r.bottom) for i, r in boxes.items()})
    columns = bands({i: (r.x, r.right) for i, r in boxes.items()})
    cells: dict[str, dict[str, object]] = {}
    taken: set[tuple[int, int]] = set()
    width = len(columns)
    order = sorted(boxes, key=lambda i: (boxes[i].y, boxes[i].x))
    for node_id in order:
        box = boxes[node_id]
        row, rowspan = _span((box.y, box.bottom), rows)
        column, columnspan = _span((box.x, box.right), columns)

        def area(r: int, c: int, rs: int, cs: int) -> set[tuple[int, int]]:
            return {(r + i, c + j) for i in range(rs) for j in range(cs)}

        if area(row, column, rowspan, columnspan) & taken:
            rowspan = columnspan = 1
            while (row, column) in taken:
                column += 1
        width = max(width, column + columnspan)
        taken |= area(row, column, rowspan, columnspan)
        first_row, last_row = rows[row], rows[min(row + rowspan, len(rows)) - 1]
        first_col = columns[min(column, len(columns) - 1)]
        last_col = columns[min(column + columnspan, len(columns)) - 1]
        sticky = ""
        if abs(box.y - first_row[0]) <= ALIGN:
            sticky += "n"
        if abs(box.bottom - last_row[1]) <= ALIGN:
            sticky += "s"
        if abs(box.right - last_col[1]) <= ALIGN:
            sticky += "e"
        if abs(box.x - first_col[0]) <= ALIGN:
            sticky += "w"
        cells[node_id] = {"row": row, "column": column, "rowspan": rowspan,
                          "columnspan": columnspan, "sticky": sticky,
                          "padx": GRID_PAD, "pady": GRID_PAD}
    return cells, len(rows), width
