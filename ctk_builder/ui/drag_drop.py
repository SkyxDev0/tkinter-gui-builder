"""Drag & Drop: Widgets aus der Palette ziehen, verschieben und in der Größe ändern.

Raster-Container: Das Ziel ist eine Zelle (grüner Rahmen), belegte Zellen tauschen.
Freie Container: Das Widget folgt dem Mauszeiger und rastet an Hilfslinien ein,
auf Wunsch auch am 8-px-Raster (Alt bzw. Option während des Ziehens: frei).
Anfasser am ausgewählten Widget ändern seine Größe. Esc bricht ab.
"""

from __future__ import annotations

import sys
import tkinter
from dataclasses import dataclass
from typing import Callable, Optional

from ctk_builder import geometry, snapping
from ctk_builder.commands import AddWidget, MoveWidget, SetGeometry
from ctk_builder.geometry import Rect
from ctk_builder.model import WidgetNode
from ctk_builder.ui import theme
from ctk_builder.ui.canvas import EMPTY_LINE_MIN, DesignCanvas
from ctk_builder.ui.palette import Palette
from ctk_builder.ui.widgets import add_bindtag
from ctk_builder.widget_specs import SPECS

DRAG_THRESHOLD = 5  # Pixel, ab denen aus einem Klick ein Ziehen wird
TARGET_COLOR = theme.DROP
HANDLE_SIZE = 8
PLATFORM = sys.platform  # in Tests ersetzbar
# Modifier-Bit von Alt/Option in event.state: Linux Mod1, macOS Mod2, Windows eigenes Bit
ALT_MASKS = {"darwin": 0x0010, "win32": 0x20000}
HANDLE_CURSORS = {
    "nw": "top_left_corner", "n": "top_side", "ne": "top_right_corner",
    "e": "right_side", "se": "bottom_right_corner", "s": "bottom_side",
    "sw": "bottom_left_corner", "w": "left_side",
}
HANDLE_ANCHORS = {"nw": (0, 0), "n": (0.5, 0), "ne": (1, 0), "e": (1, 0.5),
                  "se": (1, 1), "s": (0.5, 1), "sw": (0, 1), "w": (0, 0.5)}
WINDOW_INSET = 16  # Hilfslinie für den Innenabstand im Fenster
FRAME_INSET = 8    # … in Frames (deckt auch die runden Ecken ab)


@dataclass(frozen=True)
class DropTarget:
    """Ziel eines Drops: Zelle (Raster-Container) oder Position x, y (freier Container)."""

    container_id: str
    row: int = 0
    column: int = 0
    x: Optional[int] = None
    y: Optional[int] = None

    @property
    def free(self) -> bool:
        return self.x is not None


def snapping_enabled(state: object, platform: Optional[str] = None) -> bool:
    """Einrasten, solange Alt (macOS: Option) nicht gedrückt ist.

    Die Bits unterscheiden sich je System; NumLock darf nicht als Alt gelten
    (Linux: NumLock = Mod2 0x10, Windows: NumLock = Mod1 0x8).
    """
    if not isinstance(state, int):
        return True
    return not state & ALT_MASKS.get(PLATFORM if platform is None else platform, 0x0008)


def has_size(widget_type: str) -> bool:
    names = {p.name for p in SPECS[widget_type].props}
    return {"width", "height"} <= names


def drop_target(canvas: DesignCanvas, x_root: int, y_root: int,
                moving: Optional[str] = None) -> Optional[DropTarget]:
    """Container und Zelle unter der Bildschirmposition (Raster-Container).

    Ein Widget selbst ist nie Ziel, nur der innerste Container darunter. Beim
    Verschieben (moving) wird das gezogene Widget samt Inhalt übersprungen.
    Zeilen-/Spaltenindex gleich der Anzahl bedeutet „neue Zeile/Spalte anhängen“.
    Für freie Container nur der Container (Position berechnet der DragController).
    """
    container_id = canvas.container_at(x_root, y_root, exclude=moving)
    if container_id is None:
        return None
    node = canvas.session.project.find(container_id)
    if node.is_free:
        return DropTarget(node.id)
    view = canvas.view_of(node.id)
    column, row = view.grid_location(x_root - view.winfo_rootx(),
                                     y_root - view.winfo_rooty())
    row = min(max(row, 0), len(node.grid.rows))
    column = min(max(column, 0), len(node.grid.columns))
    return DropTarget(node.id, row, column)


class DragController:
    def __init__(self, canvas: DesignCanvas, palette: Palette):
        self.canvas = canvas
        self.palette = palette
        self.session = canvas.session
        self._start: Optional[tuple[int, int]] = None
        self._dragging = False
        self._widget_type: Optional[str] = None  # aus der Palette
        self._moving: Optional[str] = None        # vorhandenes Widget
        self._target: Optional[DropTarget] = None
        self._grab = (0.0, 0.0)                   # Griffpunkt im Widget (logisch)
        self._size = (0, 0)                       # Größe des gezogenen Widgets (logisch)
        self._displaced = False                   # gezogenes Widget live verschoben?
        self._resizing: Optional[tuple[str, str, Rect]] = None  # Knoten, Anfasser, Start
        self._resized: Optional[Rect] = None
        self._swallow_release = False             # nach Esc: Loslassen ignorieren
        self.grid_snap = False                    # zusätzlich am 8-px-Raster einrasten
        self._lifted = False                      # gezogenes Widget nach oben geholt
        self._last_free: Optional[str] = None     # zuletzt getroffener freier Container
        # vor jeder Geste aufgerufen (Hauptfenster: offene Pfeiltasten-Bewegung übernehmen)
        self.on_gesture_start: Callable[[], None] = lambda: None
        # Hilfselemente gehören zur Arbeitsfläche (nicht abgeschnitten am Fensterrand)
        self._marker = [tkinter.Frame(canvas, bg=TARGET_COLOR) for _ in range(4)]
        self._ghost = [tkinter.Frame(canvas, bg=theme.pick(theme.ACCENT)) for _ in range(4)]
        self._guides: list[tkinter.Frame] = []
        self._handles = {name: self._make_handle(name) for name in HANDLE_ANCHORS}
        self._badge = tkinter.Label(canvas, font=theme.tk_font(10), bg="#111827",
                                    fg="#ffffff", padx=6, pady=1)
        canvas.overlay_parts.update(self._marker, self._ghost, self._handles.values(),
                                    [self._badge])
        canvas.on_press = self.press_on_canvas
        canvas.on_motion = self.motion
        canvas.on_release = self.release
        canvas.after_selection.append(self.show_handles)
        # Ein Befehl mitten in einer Geste (z. B. Strg+Z, Entf) beendet sie zuerst
        self.session.before_change.append(self._interrupt)
        for widget_type, button in palette.buttons.items():
            self._hook_palette_button(button, widget_type)
        self.show_handles()

    # ------------------------------------------------------------ Start

    def _hook_palette_button(self, button: tkinter.Misc, widget_type: str) -> None:
        tag = f"palette-drag-{widget_type}"
        button.bind_class(tag, "<Button-1>", lambda e: self._begin(e, widget_type=widget_type))
        button.bind_class(tag, "<B1-Motion>", self.motion)
        button.bind_class(tag, "<ButtonRelease-1>", self.release)
        add_bindtag(button, tag)

    def press_on_canvas(self, node_id: str, event: tkinter.Event) -> None:
        if node_id != "window":
            self._begin(event, moving=node_id)

    def _fresh_gesture(self) -> None:
        """Neuer Klick: Reste einer Geste, deren Loslassen nie ankam, aufräumen."""
        if self.active:
            self.cancel()
        self._swallow_release = False
        self._resizing = self._resized = None
        self._start = None
        self.on_gesture_start()

    def _interrupt(self) -> None:
        """Vor jeder Modelländerung: laufende Geste abbrechen, offenen Klick vergessen
        (das gedrückte Widget gibt es danach vielleicht nicht mehr)."""
        if not self.cancel() and self._start is not None and self._resizing is None:
            self._start = None
            self._moving = self._widget_type = None

    def _begin(self, event: tkinter.Event, widget_type: Optional[str] = None,
               moving: Optional[str] = None) -> None:
        self._fresh_gesture()
        self._start = (event.x_root, event.y_root)
        self._dragging = False
        self._widget_type = widget_type
        self._moving = moving
        self._target = None
        self._displaced = False
        self._lifted = False
        self._last_free = None
        if moving is not None:
            rect = self.canvas.rect_of(moving)
            parent = self.session.project.parent_of(moving)
            x, y = self.canvas.to_local(parent.id, event.x_root, event.y_root)
            self._grab = (x - rect.x, y - rect.y)
            self._size = (rect.width, rect.height)
        else:
            self._size = self.canvas.probe_size(widget_type)
            self._grab = (self._size[0] / 2, self._size[1] / 2)  # Zeiger in der Mitte

    # ------------------------------------------------------------ Ziehen

    def motion(self, event: tkinter.Event) -> Optional[str]:
        if self._resizing is not None:
            return self._resize_motion(event)
        if self._start is None:
            return None
        dx = abs(event.x_root - self._start[0])
        dy = abs(event.y_root - self._start[1])
        if not self._dragging and max(dx, dy) < DRAG_THRESHOLD:
            return None
        if not self._dragging:
            self._hide_handles()
        self._dragging = True
        self._target = self._find_target(event)
        self._show_target()
        return "break"

    def _find_target(self, event: tkinter.Event) -> Optional[DropTarget]:
        target = drop_target(self.canvas, event.x_root, event.y_root, self._moving)
        project = self.session.project
        if target is None and self._moving is not None:
            # Zeiger außerhalb der Fläche: das Widget bleibt am Rand des Containers,
            # über dem es zuletzt war (sonst seines bisherigen)
            parent = project.parent_of(self._moving)
            fallback = self._last_free if project.find(self._last_free or "") else None
            if fallback is None and parent is not None and parent.is_free:
                fallback = parent.id
            if fallback is not None:
                target = DropTarget(fallback)
        if target is None:
            return None
        container = project.find(target.container_id)
        if not container.is_free:
            return target
        self._last_free = container.id
        x, y = self.canvas.to_local(container.id, event.x_root, event.y_root)
        raw = Rect(round(x - self._grab[0]), round(y - self._grab[1]), *self._size)
        others = [self.canvas.rect_of(c.id) for c in container.children
                  if c.id != self._moving and c.id in self.canvas.views]
        size = self.canvas.container_size(container.id)
        snapped = snapping.snap_move(raw, others, size, enabled=snapping_enabled(event.state),
                                     step=self._step(), inset=self._inset(container.id))
        left, top = geometry.clamp_to(size, snapped.rect.x, snapped.rect.y, *self._size)
        guides = snapped.guides if (left, top) == (snapped.rect.x, snapped.rect.y) else ()
        self._show_guides(container.id, guides)
        return DropTarget(container.id, x=left, y=top)

    def _step(self) -> Optional[int]:
        return snapping.STEP if self.grid_snap else None

    @staticmethod
    def _inset(container_id: str) -> int:
        return WINDOW_INSET if container_id == "window" else FRAME_INSET

    @property
    def active(self) -> bool:
        """Läuft gerade ein Ziehen oder Größe-Ändern?"""
        return self._resizing is not None or (self._start is not None and self._dragging)

    def cancel(self) -> bool:
        """Esc: laufendes Ziehen oder Größe-Ändern abbrechen, ohne Befehl.

        Stellt die Vorschau direkt wieder her, statt neu zu zeichnen: das gedrückte
        Widget bleibt erhalten, sein Loslassen kommt an und wird verschluckt.
        """
        if not self.active:
            return False
        if self._resizing is not None:
            self.canvas.restore(self._resizing[0])
        self._restore_moving()
        if self._lifted:
            self.canvas.restack()
        self._lifted = False
        self._resizing = self._resized = None
        self._start = None
        self._dragging = False
        self._swallow_release = True
        self._hide_marker()
        self._hide_ghost()
        self._show_guides(None, ())
        self._badge.place_forget()
        self.show_handles()
        return True

    def release(self, event: tkinter.Event) -> Optional[str]:
        if self._swallow_release:
            self._swallow_release = False
            return "break"  # sonst fügte die Palette nach Esc doch noch ein
        if self._resizing is not None:
            return self._resize_release(event)
        if self._start is None:
            return None
        dragging, target = self._dragging, self._target
        widget_type, moving = self._widget_type, self._moving
        self._start = None
        self._dragging = False
        self._restore_moving()
        self._hide_marker()
        self._hide_ghost()
        self._show_guides(None, ())
        self._badge.place_forget()
        if not dragging:
            return None  # normaler Klick: Palette-Button fügt wie gewohnt ein
        lifted, self._lifted = self._lifted, False
        if target is None or not self.drop(target, widget_type=widget_type, moving=moving):
            if lifted:
                self.canvas.restack()  # Stapelreihenfolge wie im Modell (nie lower())
        self.canvas.focus_set()  # Pfeiltasten und Entf wirken gleich auf das Widget
        self.show_handles()
        return "break"

    def drop(self, target: DropTarget, widget_type: Optional[str] = None,
             moving: Optional[str] = None) -> bool:
        """Führt den passenden Befehl aus; False, wenn sich nichts geändert hat."""
        position = ({"x": target.x, "y": target.y} if target.free
                    else {"row": target.row, "column": target.column})
        if widget_type is not None:
            command = AddWidget(target.container_id, widget_type, **position)
            if self.session.execute(command):
                self.session.select(command.node_id)
                return True
            return False
        node = self.session.project.find(moving) if moving is not None else None
        parent = self.session.project.parent_of(moving) if node is not None else None
        if node is None or parent is None:
            return False  # Widget gibt es nicht mehr (z. B. während des Ziehens gelöscht)
        if parent.id == target.container_id:
            where = ((node.layout.x, node.layout.y) if target.free
                     else (node.layout.row, node.layout.column))
            if where == tuple(position.values()):
                return False
        rects = {moving: self.canvas.rect_of(moving)}  # Frames behalten ihre Größe
        return self.session.execute(
            MoveWidget(moving, target.container_id, rects=rects, **position))

    # ------------------------------------------------------------ Anzeige beim Ziehen

    def _show_target(self) -> None:
        target = self._target
        project = self.session.project
        parent = project.parent_of(self._moving) if self._moving else None
        if target is not None and target.free:
            self._hide_marker()
            if parent is not None and parent.id == target.container_id:
                self._hide_ghost()
                view = self.canvas.views[self._moving]
                if not self._lifted:  # beim Ziehen über allen Geschwistern zeigen
                    view.lift()
                    self._lifted = True
                view.place(x=target.x, y=target.y)  # live; CTk skaliert selbst
                self._displaced = True
            else:
                self._restore_moving()
                self._place_frame(self._ghost, target.container_id,
                                  Rect(target.x, target.y, *self._size), thickness=2)
            self._show_badge(target.container_id, Rect(target.x, target.y, *self._size),
                             f"x {target.x} · y {target.y}")
            return
        self._restore_moving()
        self._hide_ghost()
        self._show_guides(None, ())
        self._badge.place_forget()
        self._show_marker()

    def _show_badge(self, container_id: str, rect: Rect, text: str) -> None:
        """Kleine Anzeige über dem Widget: Position beim Ziehen, Größe beim Ändern."""
        view = self.canvas.view_of(container_id)
        physical = self.canvas.to_physical
        self._badge.configure(text=text)
        self._badge.place(in_=view, x=physical(rect.x), y=physical(rect.y) - 6, anchor="sw")
        self._badge.lift()

    def _restore_moving(self) -> None:
        """Live verschobenes Widget zurück an seine Position im Modell."""
        if not self._displaced or self._moving is None:
            return
        self._displaced = False
        node = self.session.project.find(self._moving)
        view = self.canvas.views.get(self._moving)
        if node is not None and view is not None and view.winfo_exists():
            view.place(x=node.layout.x, y=node.layout.y)

    def _place_frame(self, bars: list[tkinter.Frame], container_id: str, rect: Rect,
                     thickness: int) -> None:
        """Rahmen aus vier Balken um rect (logische Pixel im Container)."""
        view = self.canvas.view_of(container_id)
        physical = self.canvas.to_physical
        x, y = physical(rect.x), physical(rect.y)
        width, height = physical(rect.width), physical(rect.height)
        top, bottom, left, right = bars
        top.place(in_=view, x=x, y=y, width=width, height=thickness)
        bottom.place(in_=view, x=x, y=y + height - thickness, width=width, height=thickness)
        left.place(in_=view, x=x, y=y, width=thickness, height=height)
        right.place(in_=view, x=x + width - thickness, y=y, width=thickness, height=height)
        for bar in bars:
            bar.lift()

    def _hide_ghost(self) -> None:
        for bar in self._ghost:
            bar.place_forget()

    def _show_guides(self, container_id: Optional[str],
                     guides: tuple[snapping.Guide, ...]) -> None:
        while len(self._guides) < len(guides):
            line = tkinter.Frame(self.canvas, bg=theme.GUIDE)
            self.canvas.overlay_parts.add(line)
            self._guides.append(line)
        for line in self._guides[len(guides):]:
            line.place_forget()
        if container_id is None:
            return
        view = self.canvas.view_of(container_id)
        physical = self.canvas.to_physical
        for line, guide in zip(self._guides, guides):
            position = physical(guide.position)
            start, length = physical(guide.start), physical(guide.end) - physical(guide.start)
            if guide.axis == "x":
                line.place(in_=view, x=min(position, view.winfo_width() - 1), y=start,
                           width=1, height=max(length, 1))
            else:
                line.place(in_=view, x=start, y=min(position, view.winfo_height() - 1),
                           width=max(length, 1), height=1)
            line.lift()

    def _show_marker(self) -> None:
        target = self._target
        if target is None:
            self._hide_marker()
            return
        project = self.session.project
        container = project.find(target.container_id)
        view = self.canvas.view_of(target.container_id)
        rows, columns = len(container.grid.rows), len(container.grid.columns)
        if target.column < columns:
            x, _, width, _ = view.grid_bbox(target.column, 0)
        else:
            x0, _, w0, _ = view.grid_bbox(columns - 1, 0)
            x, width = x0 + w0, EMPTY_LINE_MIN
        if target.row < rows:
            _, y, _, height = view.grid_bbox(0, target.row)
        else:
            _, y0, _, h0 = view.grid_bbox(0, rows - 1)
            y, height = y0 + h0, EMPTY_LINE_MIN
        top, bottom, left, right = self._marker
        top.place(in_=view, x=x, y=y, width=width, height=3)
        bottom.place(in_=view, x=x, y=y + height - 3, width=width, height=3)
        left.place(in_=view, x=x, y=y, width=3, height=height)
        right.place(in_=view, x=x + width - 3, y=y, width=3, height=height)
        for bar in self._marker:
            bar.lift()

    def _hide_marker(self) -> None:
        for bar in self._marker:
            bar.place_forget()

    # ------------------------------------------------------------ Größe ändern

    def _make_handle(self, name: str) -> tkinter.Frame:
        handle = tkinter.Frame(self.canvas, width=HANDLE_SIZE, height=HANDLE_SIZE,
                               bg="#ffffff", highlightthickness=1,
                               highlightbackground=theme.SELECT, highlightcolor=theme.SELECT,
                               cursor=HANDLE_CURSORS[name])
        handle.bind("<Button-1>", lambda e: self._resize_begin(e, name))
        handle.bind("<B1-Motion>", self.motion)
        handle.bind("<ButtonRelease-1>", self.release)
        return handle

    def resizable(self, node_id: str) -> bool:
        """Anfasser nur für Widgets mit width/height in freien Containern (dort ist
        jedes Widget so groß wie width/height, auch ein Raster-Frame)."""
        node = self.session.project.find(node_id)
        if not isinstance(node, WidgetNode) or not has_size(node.type):
            return False
        return self.session.project.parent_of(node_id).is_free

    def show_handles(self) -> None:
        node_id = self.session.selected_id
        if (self._dragging or node_id not in self.canvas.views
                or not self.resizable(node_id)):
            self._hide_handles()
            return
        view = self.canvas.views[node_id]
        for name, (relx, rely) in HANDLE_ANCHORS.items():
            handle = self._handles[name]
            handle.place(in_=view, relx=relx, rely=rely, anchor="center",
                         width=HANDLE_SIZE, height=HANDLE_SIZE)
            handle.lift()

    def _hide_handles(self) -> None:
        for handle in self._handles.values():
            handle.place_forget()

    def _resize_begin(self, event: tkinter.Event, handle: str) -> str:
        self._fresh_gesture()
        node_id = self.session.selected_id
        if not self.resizable(node_id):
            return "break"
        self._start = (event.x_root, event.y_root)
        self._resizing = (node_id, handle, self.canvas.rect_of(node_id))
        self._resized = None
        return "break"

    def _resize_motion(self, event: tkinter.Event) -> str:
        node_id, handle, start = self._resizing
        project = self.session.project
        container = project.parent_of(node_id)
        scale = self.canvas.scaling()
        dx = (event.x_root - self._start[0]) / scale
        dy = (event.y_root - self._start[1]) / scale
        others = [self.canvas.rect_of(c.id) for c in container.children
                  if c.id != node_id and c.id in self.canvas.views]
        size = self.canvas.container_size(container.id)
        result = snapping.resize(start, handle, dx, dy, others, size,
                                 enabled=snapping_enabled(event.state), step=self._step(),
                                 inset=self._inset(container.id))
        rect = result.rect
        if rect.x < 0 or rect.y < 0:  # nicht über den linken/oberen Rand hinaus
            rect = Rect(max(rect.x, 0), max(rect.y, 0),
                        rect.width + min(rect.x, 0), rect.height + min(rect.y, 0))
        view = self.canvas.views[node_id]
        view.configure(width=rect.width, height=rect.height)
        rect = self._at_least_shown(node_id, handle, rect)
        view.place(x=rect.x, y=rect.y)
        self._resized = rect
        self._show_guides(container.id, result.guides)
        self._show_badge(container.id, rect, f"{rect.width} × {rect.height}")
        return "break"

    def _at_least_shown(self, node_id: str, handle: str, rect: Rect) -> Rect:
        """CTk behandelt width/height oft als Mindestmaß (Text, Rahmen): Gespeichert
        wird, was tatsächlich zu sehen ist. Die gezogene Kante gibt nach."""
        self.canvas.update_idletasks()
        shown = self.canvas.rect_of(node_id)
        width, height = max(rect.width, shown.width), max(rect.height, shown.height)
        move_left, move_top, _, _ = snapping.HANDLES[handle]
        x = max(rect.right - width, 0) if move_left else rect.x
        y = max(rect.bottom - height, 0) if move_top else rect.y
        return Rect(x, y, width, height)

    def _resize_release(self, event: tkinter.Event) -> str:
        node_id, _, start = self._resizing
        rect = self._resized
        self._resizing = None
        self._resized = None
        self._start = None
        self._show_guides(None, ())
        self._badge.place_forget()
        if rect is None or rect == start:
            return "break"
        if not self.session.execute(SetGeometry(node_id, rect.x, rect.y,
                                                rect.width, rect.height)):
            self.canvas.restore(node_id)  # Vorschau zurück auf den Stand im Modell
        self.show_handles()
        return "break"
