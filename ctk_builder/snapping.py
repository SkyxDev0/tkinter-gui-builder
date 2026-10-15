"""Einrasten beim freien Verschieben und Größe-Ändern. Ohne Tkinter.

Rastet an Kanten und Mitten der Geschwister und des Containers ein (Hilfslinien),
sonst auf ein festes Raster. Alle Werte in logischen Pixeln.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ctk_builder.geometry import Rect

STEP = 8        # Raster, wenn keine Hilfslinie greift (Umschalter „Am Raster einrasten“)
THRESHOLD = 6   # Abstand, ab dem eine Hilfslinie greift
MIN_SIZE = 8    # kleinste Größe beim Ziehen an den Anfassern

# Anfasser: welche Kanten sie bewegen (links, oben, rechts, unten)
HANDLES = {
    "nw": (True, True, False, False), "n": (False, True, False, False),
    "ne": (False, True, True, False), "e": (False, False, True, False),
    "se": (False, False, True, True), "s": (False, False, False, True),
    "sw": (True, False, False, True), "w": (True, False, False, False),
}


@dataclass(frozen=True)
class Guide:
    """Hilfslinie: axis "x" = senkrechte Linie bei position, "y" = waagerechte."""

    axis: str
    position: int
    start: int
    end: int


@dataclass(frozen=True)
class Snapped:
    rect: Rect
    guides: tuple[Guide, ...]


def _lines(rect: Rect, axis: str) -> tuple[float, float, float]:
    if axis == "x":
        return rect.x, rect.x + rect.width / 2, rect.right
    return rect.y, rect.y + rect.height / 2, rect.bottom


def _targets(others: Sequence[Rect], container: tuple[int, int], axis: str,
             inset: int = 0) -> list[tuple[float, Optional[Rect]]]:
    """Mögliche Hilfslinien: Kanten/Mitten der Geschwister (mit Rechteck) und des
    Containers samt Innenabstand inset (ohne Rechteck)."""
    size = container[0] if axis == "x" else container[1]
    lines = {0, size / 2, size} | ({inset, size - inset} if 0 < inset < size / 2 else set())
    targets: list[tuple[float, Optional[Rect]]] = [(line, None) for line in sorted(lines)]
    for other in others:
        targets += [(line, other) for line in _lines(other, axis)]
    return targets


def _quantize(value: float, step: Optional[int]) -> int:
    """Auf das Raster runden – ohne Raster (step None) nur auf ganze Pixel."""
    return round(value / step) * step if step else round(value)


def _best(edges: Sequence[float], targets: list[tuple[float, Optional[Rect]]],
          threshold: float) -> Optional[float]:
    """Kleinste Verschiebung, mit der eine der Kanten auf einer Hilfslinie liegt."""
    best = None
    for edge in edges:
        for line, _ in targets:
            delta = line - edge
            if abs(delta) <= threshold and (best is None or abs(delta) < abs(best)):
                best = delta
    return best


def _guides(rect: Rect, edges: Sequence[float], targets: list[tuple[float, Optional[Rect]]],
            axis: str, container: tuple[int, int]) -> list[Guide]:
    """Hilfslinien, auf denen eine der Kanten jetzt liegt – über die beteiligten
    Rechtecke hinweg gezeichnet (beim Container über die ganze Höhe/Breite)."""
    guides: dict[int, Guide] = {}
    across = "y" if axis == "x" else "x"
    for line, other in targets:
        if not any(abs(line - edge) < 0.5 for edge in edges):
            continue
        position = round(line)
        if other is None:
            start, end = 0, container[1] if axis == "x" else container[0]
        else:
            start = min(_lines(rect, across)[0], _lines(other, across)[0])
            end = max(_lines(rect, across)[2], _lines(other, across)[2])
        old = guides.get(position)
        if old is not None:
            start, end = min(start, old.start), max(end, old.end)
        guides[position] = Guide(axis, position, round(start), round(end))
    return list(guides.values())


def snap_move(rect: Rect, others: Sequence[Rect], container: tuple[int, int],
              enabled: bool = True, step: Optional[int] = STEP,
              threshold: float = THRESHOLD, inset: int = 0) -> Snapped:
    """Rastet ein verschobenes Rechteck ein (Größe bleibt).

    Hilfslinien haben Vorrang; greift keine, wird auf step gerundet (None: kein Raster).
    """
    if not enabled:
        return Snapped(rect, ())
    position = {}
    for axis in ("x", "y"):
        edges = _lines(rect, axis)
        targets = _targets(others, container, axis, inset)
        delta = _best(edges, targets, threshold)
        start = rect.x if axis == "x" else rect.y
        position[axis] = round(start + delta) if delta is not None else _quantize(start, step)
    snapped = Rect(position["x"], position["y"], rect.width, rect.height)
    guides = []
    for axis in ("x", "y"):
        guides += _guides(snapped, _lines(snapped, axis),
                          _targets(others, container, axis, inset), axis, container)
    return Snapped(snapped, tuple(guides))


def resize(start: Rect, handle: str, dx: float, dy: float,
           others: Sequence[Rect], container: tuple[int, int],
           enabled: bool = True, step: Optional[int] = STEP,
           threshold: float = THRESHOLD, inset: int = 0) -> Snapped:
    """Neue Geometrie, wenn der Anfasser handle um (dx, dy) gezogen wird."""
    move_left, move_top, move_right, move_bottom = HANDLES[handle]
    edges = {"left": float(start.x), "top": float(start.y),
             "right": float(start.right), "bottom": float(start.bottom)}
    moving = {"left": move_left, "top": move_top, "right": move_right, "bottom": move_bottom}
    for name, delta in (("left", dx), ("right", dx), ("top", dy), ("bottom", dy)):
        if not moving[name]:
            continue
        axis = "x" if name in ("left", "right") else "y"
        value = edges[name] + delta
        if enabled:
            snap = _best([value], _targets(others, container, axis, inset), threshold)
            value = value + snap if snap is not None else _quantize(value, step)
        edges[name] = value
    # Mindestgröße: die gezogene Kante gibt nach, die gegenüberliegende bleibt
    if edges["right"] - edges["left"] < MIN_SIZE:
        if move_left:
            edges["left"] = edges["right"] - MIN_SIZE
        else:
            edges["right"] = edges["left"] + MIN_SIZE
    if edges["bottom"] - edges["top"] < MIN_SIZE:
        if move_top:
            edges["top"] = edges["bottom"] - MIN_SIZE
        else:
            edges["bottom"] = edges["top"] + MIN_SIZE
    left, top = round(edges["left"]), round(edges["top"])
    rect = Rect(left, top, round(edges["right"]) - left, round(edges["bottom"]) - top)
    if not enabled:
        return Snapped(rect, ())
    guides = []
    for axis, names in (("x", ("left", "right")), ("y", ("top", "bottom"))):
        moved = [edges[n] for n in names if moving[n]]
        if moved:
            guides += _guides(rect, moved, _targets(others, container, axis, inset), axis,
                              container)
    return Snapped(rect, tuple(guides))
