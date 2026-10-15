"""Kleine Bedienelemente im modernen Look: Icon-Knöpfe, Leisten-Einträge, Chips."""

from __future__ import annotations

import tkinter
from typing import Callable, Optional

import customtkinter as ctk

from ctk_builder.ui import theme
from ctk_builder.ui.icons import draw_icon, round_rect


def all_parts(widget: tkinter.Misc) -> list[tkinter.Misc]:
    """widget und alle Teil-Widgets – auch die, die CTkFrame in winfo_children() verbirgt."""
    parts = [widget]
    for child in tkinter.Misc.winfo_children(widget):
        parts += all_parts(child)
    return parts


def add_bindtag(widget: tkinter.Misc, tag: str) -> None:
    """Setzt tag vor die Bindtags von widget und allen Teil-Widgets."""
    for part in all_parts(widget):
        if part.bindtags()[0] != tag:
            part.bindtags((tag, *part.bindtags()))


def pointer_inside(widget: tkinter.Misc, event: tkinter.Event) -> bool:
    x = event.x_root - widget.winfo_rootx()
    y = event.y_root - widget.winfo_rooty()
    return 0 <= x < widget.winfo_width() and 0 <= y < widget.winfo_height()


class Tooltip:
    """Kurzer Hinweistext unter einem Widget, erscheint nach kurzem Verweilen."""

    DELAY_MS = 600

    def __init__(self, widget: tkinter.Misc, text: str):
        self.widget = widget
        self.text = text
        self._after: Optional[str] = None
        self._tip: Optional[tkinter.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        for sequence in ("<Leave>", "<ButtonPress>", "<Destroy>"):
            widget.bind(sequence, self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._hide()
        self._after = self.widget.after(self.DELAY_MS, self._show)

    def _show(self) -> None:
        self._after = None
        if not self.widget.winfo_exists():
            return
        tip = tkinter.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tkinter.Label(tip, text=self.text, bg=theme.pick(theme.PRIMARY),
                      fg=theme.pick(theme.PRIMARY_TEXT), padx=8, pady=4,
                      font=theme.tk_font(12)).pack()
        tip.update_idletasks()
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() - tip.winfo_width()) // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        tip.wm_geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, _event=None) -> None:
        if self._after is not None:
            self.widget.after_cancel(self._after)
            self._after = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


def arm_click(widget: tkinter.Misc, action: Callable[[], None]) -> None:
    """Wie ein normaler Knopf: nur auslösen, wenn auch das Drücken hier begann.

    Sonst löst ein verirrtes Loslassen (z. B. nach abgebrochenem Ziehen auf der
    Arbeitsfläche) Löschen, Duplizieren oder Rückgängig aus.
    """
    armed = [False]

    def press(_event: tkinter.Event) -> None:
        armed[0] = True

    def release(event: tkinter.Event) -> None:
        was_armed, armed[0] = armed[0], False
        if was_armed and pointer_inside(widget, event):
            action()

    widget.bind("<Button-1>", press, add="+")
    widget.bind("<ButtonRelease-1>", release, add="+")


class IconButton(tkinter.Canvas):
    """Quadratischer Icon-Knopf mit runder Hover-Fläche; optional umschaltbar (active)."""

    def __init__(self, master, icon: str, command: Callable[[], None], *,
                 bg: theme.Color = theme.CARD, size: int = 34, tooltip: str = "",
                 danger: bool = False, active: bool = False):
        self._bg = theme.pick(bg)
        super().__init__(master, width=size, height=size, bg=self._bg,
                         highlightthickness=0, bd=0)
        self.icon = icon
        self.command = command
        self.size = size
        self.danger = danger
        self.active = active
        self._hover = False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        arm_click(self, self.invoke)
        if tooltip:
            Tooltip(self, tooltip)
        self._draw()

    def invoke(self) -> None:
        self.command()

    def set_active(self, active: bool) -> None:
        self.active = active
        self._draw()

    def _set_hover(self, hover: bool) -> None:
        self._hover = hover
        if self.winfo_exists():
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        fill = None
        if self.active:
            fill = theme.ACCENT_SOFT
        elif self._hover:
            fill = theme.DANGER_SOFT if self.danger else theme.HOVER
        if fill is not None:
            round_rect(self, 1, 1, self.size - 1, self.size - 1, 8,
                       fill=theme.pick(fill), outline="")
        if self.danger:
            color = theme.DANGER
        elif self.active:
            color = theme.ACCENT_TEXT
        else:
            color = theme.TEXT
        draw_icon(self, self.icon, self.size / 2, self.size / 2, 20, theme.pick(color),
                  theme.pick(fill) if fill is not None else self._bg)


class RailItem(tkinter.Canvas):
    """Eintrag der linken Icon-Leiste: Icon mit Beschriftung darunter."""

    WIDTH, HEIGHT = 64, 58

    def __init__(self, master, icon: str, text: str, command: Callable[[], None], *,
                 bg: theme.Color = theme.BG):
        self._bg = theme.pick(bg)
        super().__init__(master, width=self.WIDTH, height=self.HEIGHT, bg=self._bg,
                         highlightthickness=0, bd=0)
        self.icon = icon
        self.text = text
        self.command = command
        self.active = False
        self._hover = False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        arm_click(self, lambda: self.command())
        self._draw()

    def set_active(self, active: bool) -> None:
        self.active = active
        self._draw()

    def _set_hover(self, hover: bool) -> None:
        self._hover = hover
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        fill = theme.ACCENT_SOFT if self.active else theme.HOVER if self._hover else None
        if fill is not None:
            round_rect(self, 4, 2, self.WIDTH - 4, self.HEIGHT - 2, 10,
                       fill=theme.pick(fill), outline="")
        color = theme.pick(theme.ACCENT_TEXT if self.active else theme.MUTED)
        draw_icon(self, self.icon, self.WIDTH / 2, 22, 22, color,
                  theme.pick(fill) if fill is not None else self._bg)
        self.create_text(self.WIDTH / 2, 46, text=self.text, fill=color,
                         font=theme.tk_font(11, "bold" if self.active else "normal"))


class ToggleChip(ctk.CTkButton):
    """Kleiner Umschaltknopf (z. B. sticky N/S/E/W). toggle() wie bei CTkCheckBox."""

    def __init__(self, master, text: str, value: bool, command: Callable[[bool], None]):
        self._chip_on = value
        self._chip_command = command
        super().__init__(master, text=text, width=38, height=28, corner_radius=8,
                         border_width=1, font=theme.font(12, "bold"), command=self.toggle)
        self._apply_style()

    def get(self) -> bool:
        return self._chip_on

    def toggle(self) -> None:
        self._chip_on = not self._chip_on
        self._apply_style()
        self._chip_command(self._chip_on)

    def _apply_style(self) -> None:
        on = self._chip_on
        self.configure(fg_color=theme.ACCENT if on else theme.INPUT,
                       hover_color=theme.ACCENT_HOVER if on else theme.HOVER,
                       text_color="#ffffff" if on else theme.TEXT,
                       border_color=theme.ACCENT if on else theme.BORDER)
