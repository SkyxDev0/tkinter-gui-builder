"""Hauptfenster: setzt die Panels zusammen, Menüs, Tastenkürzel, Dateien."""

from __future__ import annotations

import os
import sys
import tkinter
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

from ctk_builder import exporter
from ctk_builder.commands import DuplicateWidget, MoveWidget, RemoveWidget
from ctk_builder.project_io import SUFFIX, ProjectFileError
from ctk_builder.runner import ProcessRunner
from ctk_builder.session import Session
from ctk_builder.settings import Settings
from ctk_builder.ui import theme
from ctk_builder.ui.canvas import DesignCanvas
from ctk_builder.ui.drag_drop import DragController
from ctk_builder.ui.grid_overlay import GridOverlay
from ctk_builder.ui.icons import draw_icon, round_rect
from ctk_builder.ui.output_console import OutputConsole
from ctk_builder.ui.palette import Palette
from ctk_builder.ui.properties import PropertiesPanel
from ctk_builder.ui.structure_tree import StructureTree
from ctk_builder.ui.widgets import IconButton, RailItem

MOD = "Command" if sys.platform == "darwin" else "Control"
MOD_LABEL = "Cmd" if sys.platform == "darwin" else "Strg"
FILETYPES = [("CTk Builder Projekt", f"*{SUFFIX}")]
# Tk 8.6.13–8.6.16 stürzt unter macOS ab, sobald eine Dateiendung einen Punkt
# enthält: [UTType typeWithFilenameExtension:@"ctkb.json"] ist nil (Tk-Ticket
# 080a28104e). Dort daher nur die einfache Endung; project_path() ergänzt den Rest.
MAC_FILETYPES = [("CTk Builder Projekt", "*.json")]
PLATFORM = sys.platform  # in Tests ersetzbar (sys.platform selbst nicht: CTk liest es)


def project_dialog_options(save: bool, initialfile: str = "",
                           platform: Optional[str] = None) -> dict[str, Any]:
    """Optionen für den Öffnen-/Speichern-Dialog von Projektdateien."""
    platform = PLATFORM if platform is None else platform
    if platform == "darwin":
        # auch kein defaultextension: ohne filetypes landet es im selben Absturz
        options: dict[str, Any] = {"filetypes": MAC_FILETYPES}
    else:
        options = {"filetypes": FILETYPES}
        if save:
            options["defaultextension"] = SUFFIX
    if save and initialfile:
        options["initialfile"] = initialfile
    return options


def project_path(chosen: str) -> Path:
    """Gewählter Dateiname -> Projektdatei mit Endung .ctkb.json.

    „kontakt“, „kontakt.json“ und „kontakt.ctkb“ werden zu „kontakt.ctkb.json“;
    Groß-/Kleinschreibung der Endung spielt keine Rolle.
    """
    path = Path(chosen)
    stem = path.name
    if stem.lower().endswith(SUFFIX):
        stem = stem[: -len(SUFFIX)]
    else:
        for ending in (".json", ".ctkb"):
            if stem.lower().endswith(ending):
                stem = stem[: -len(ending)]
    return path.with_name(stem + SUFFIX)


def needs_overwrite_prompt(chosen: str, final: Path) -> bool:
    """True, wenn final schon existiert und der Dialog nicht genau danach gefragt hat."""
    if not final.exists():
        return False
    try:
        return not (Path(chosen).exists() and os.path.samefile(chosen, final))
    except OSError:
        return True


class MainWindow(ctk.CTk):
    def __init__(self, session: Optional[Session] = None,
                 settings: Optional[Settings] = None):
        super().__init__(fg_color=theme.BG)
        self.session = session or Session()
        self.settings = settings or Settings()
        self.runner = ProcessRunner()
        self._dialog_open = False
        self.geometry("1360x860")
        self.minsize(1040, 660)

        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_menu()
        self._build_header()

        # Links: Icon-Leiste und umschaltbares Seitenpanel (Widgets / Struktur)
        rail = ctk.CTkFrame(self, fg_color="transparent")
        rail.grid(row=1, column=0, sticky="ns", padx=(8, 0), pady=(14, 6))
        self.side = theme.card(self, width=268)
        self.side.grid(row=1, column=1, sticky="ns", padx=(6, 14), pady=(14, 6))
        self.side.pack_propagate(False)
        self.palette = Palette(self.side, self.session)
        self.tree = StructureTree(self.side, self.session)
        self.rail_items = {
            "widgets": RailItem(rail, "widgets", "Widgets", lambda: self.show_panel("widgets")),
            "tree": RailItem(rail, "tree", "Struktur", lambda: self.show_panel("tree")),
        }
        for item in self.rail_items.values():
            item.pack(pady=(0, 6))

        # Mitte: Arbeitsfläche mit schwebender Werkzeugleiste, darunter die Ausgabe
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=1, column=2, sticky="nsew", pady=(14, 6))
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=1)
        self.canvas = DesignCanvas(center, self.session)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.grid_overlay = GridOverlay(self.canvas)
        self.drag = DragController(self.canvas, self.palette)
        self._build_canvas_toolbar()
        self.console = OutputConsole(center, self.runner)
        self.console.grid(row=1, column=0, sticky="ew", pady=(14, 0))

        # Rechts: Eigenschaften
        self.properties = PropertiesPanel(self, self.session)
        self.properties.grid(row=1, column=3, sticky="ns", padx=14, pady=(14, 6))

        self.status = ctk.CTkLabel(self, text="", anchor="w", height=22,
                                   font=theme.font(12), text_color=theme.MUTED)
        self.status.grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 6))
        self.session.on_status = self.show_status
        self.session.subscribe(self.update_title)

        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        if PLATFORM == "darwin":
            # Cmd+Q, „Beenden“ im App-Menü und im Dock: ohne diesen Handler beendet
            # Tk sofort (Tcl_Exit) – ohne Nachfrage nach ungespeicherten Änderungen
            self.createcommand("::tk::mac::Quit", self.quit_app)
        self.show_panel("widgets")
        self.update_title()

    # ------------------------------------------------------------ Rahmen

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=0, height=60)
        header.grid(row=0, column=0, columnspan=4, sticky="ew")
        header.pack_propagate(False)
        ctk.CTkFrame(header, height=1, corner_radius=0,
                     fg_color=theme.BORDER).pack(side="bottom", fill="x")
        bar = ctk.CTkFrame(header, fg_color="transparent")
        bar.pack(fill="both", expand=True, padx=16)

        logo = tkinter.Canvas(bar, width=32, height=32, bg=theme.pick(theme.CARD),
                              highlightthickness=0, bd=0)
        accent = theme.pick(theme.ACCENT)
        round_rect(logo, 0, 0, 32, 32, 9, fill=accent, outline="")
        draw_icon(logo, "widgets", 16, 16, 18, "#ffffff", accent)
        logo.pack(side="left")
        ctk.CTkLabel(bar, text="CTk Builder", font=theme.font(15, "bold"),
                     text_color=theme.TEXT).pack(side="left", padx=(10, 14))
        for text, key in (("Datei", "file"), ("Bearbeiten", "edit")):
            button = ctk.CTkButton(bar, text=text, width=10, height=32, corner_radius=8,
                                   fg_color="transparent", hover_color=theme.HOVER,
                                   text_color=theme.TEXT, font=theme.font(13))
            button.configure(command=lambda b=button, k=key: self._post_menu(k, b))
            button.pack(side="left", padx=2)
        ctk.CTkFrame(bar, width=1, height=24, fg_color=theme.BORDER).pack(side="left", padx=12)
        self.project_label = ctk.CTkLabel(bar, text="", font=theme.font(13),
                                          text_color=theme.MUTED)
        self.project_label.pack(side="left")

        self.run_button = theme.primary_button(bar, text="▶  Ausführen", width=124,
                                               command=self.run)
        self.run_button.pack(side="right")
        self.export_button = theme.secondary_button(bar, text="Exportieren", width=108,
                                                    command=self.export)
        self.export_button.pack(side="right", padx=8)
        self.save_button = theme.secondary_button(bar, text="Speichern", width=100,
                                                  command=self.save)
        self.save_button.pack(side="right")
        ctk.CTkFrame(bar, width=1, height=24, fg_color=theme.BORDER).pack(side="right", padx=12)
        IconButton(bar, "redo", self.session.redo,
                   tooltip=f"Wiederholen ({MOD_LABEL}+Shift+Z)").pack(side="right", padx=2)
        IconButton(bar, "undo", self.session.undo,
                   tooltip=f"Rückgängig ({MOD_LABEL}+Z)").pack(side="right", padx=2)

    def _build_canvas_toolbar(self) -> None:
        """Schwebende Werkzeugleiste oben rechts auf der Arbeitsfläche."""
        bar = theme.card(self.canvas, corner_radius=10)
        bar.place(relx=1.0, x=-16, y=16, anchor="ne")
        self.toolbar_buttons = {
            "duplicate": IconButton(bar, "copy", self.duplicate_selected,
                                    tooltip=f"Duplizieren ({MOD_LABEL}+D)"),
            "delete": IconButton(bar, "trash", self.delete_selected, danger=True,
                                 tooltip="Löschen (Entf)"),
            "grid": IconButton(bar, "grid", self.toggle_grid_lines, active=True,
                               tooltip="Rasterlinien ein/aus"),
        }
        for i, button in enumerate(self.toolbar_buttons.values()):
            button.pack(side="left", padx=(6 if i == 0 else 0, 6), pady=6)

    def show_panel(self, name: str) -> None:
        """Seitenpanel umschalten: "widgets" (Palette) oder "tree" (Struktur)."""
        panels = {"widgets": self.palette, "tree": self.tree}
        for key, panel in panels.items():
            if key == name:
                # Innenabstand, damit das Panel die runden Ecken der Karte nicht verdeckt
                panel.pack(fill="both", expand=True, padx=4, pady=4)
            else:
                panel.pack_forget()
            self.rail_items[key].set_active(key == name)
        self.current_panel = name

    def toggle_grid_lines(self) -> None:
        visible = not self.grid_overlay.lines_visible
        self.grid_overlay.set_lines_visible(visible)
        self.toolbar_buttons["grid"].set_active(visible)

    def show_status(self, message: str) -> None:
        self.status.configure(text=message)
        self.after(5000, lambda: self.status.winfo_exists()
                   and self.status.cget("text") == message
                   and self.status.configure(text=""))

    def update_title(self) -> None:
        name = self.session.path.name if self.session.path else "Unbenannt"
        dirty = " •" if self.session.dirty else ""
        self.title(f"{name}{dirty} – CTk Builder")
        self.project_label.configure(
            text=f"{name}  ·  ungespeichert" if self.session.dirty else name)

    def _build_menu(self) -> None:
        """Menüs für die Kopfzeile; auf macOS zusätzlich in der Systemmenüleiste."""
        menubar = tkinter.Menu(self) if PLATFORM == "darwin" else None
        parent = menubar or self
        file_menu = tkinter.Menu(parent, tearoff=False)
        file_menu.add_command(label="Neu", accelerator=f"{MOD_LABEL}+N", command=self.new_project)
        file_menu.add_command(label="Öffnen…", accelerator=f"{MOD_LABEL}+O", command=self.open_project)
        file_menu.add_command(label="Speichern", accelerator=f"{MOD_LABEL}+S", command=self.save)
        file_menu.add_command(label="Speichern unter…", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exportieren", accelerator=f"{MOD_LABEL}+E", command=self.export)
        file_menu.add_command(label="Ausführen", accelerator=f"{MOD_LABEL}+R", command=self.run)
        file_menu.add_command(label="Python-Interpreter wählen…", command=self.choose_interpreter)

        edit_menu = tkinter.Menu(parent, tearoff=False)
        edit_menu.add_command(label="Rückgängig", accelerator=f"{MOD_LABEL}+Z", command=self.session.undo)
        edit_menu.add_command(label="Wiederholen", accelerator=f"{MOD_LABEL}+Shift+Z", command=self.session.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplizieren", accelerator=f"{MOD_LABEL}+D", command=self.duplicate_selected)
        edit_menu.add_command(label="Löschen", accelerator="Entf", command=self.delete_selected)
        self.menus = {"file": file_menu, "edit": edit_menu}

        if menubar is not None:
            menubar.add_cascade(label="Datei", menu=file_menu)
            menubar.add_cascade(label="Bearbeiten", menu=edit_menu)
            tkinter.Tk.configure(self, menu=menubar)

    def _post_menu(self, key: str, button: tkinter.Misc) -> None:
        self.menus[key].tk_popup(button.winfo_rootx(),
                                 button.winfo_rooty() + button.winfo_height() + 4)

    def _bind_keys(self) -> None:
        shortcuts = {
            "n": self.new_project, "o": self.open_project, "s": self.save,
            "e": self.export, "r": self.run, "d": self.duplicate_selected,
            "z": self.session.undo, "Z": self.session.redo,
        }
        for key, action in shortcuts.items():
            self.bind_all(f"<{MOD}-{key}>", lambda e, a=action: (a(), "break")[1])
        self.bind_all(f"<{MOD}-Shift-z>", lambda e: (self.session.redo(), "break")[1])
        # tkinter.Misc.bind: CTkFrame.bind() bindet an sein internes Canvas,
        # den Fokus hat aber die Arbeitsfläche selbst (DesignCanvas._pressed)
        for widget in (self.canvas, self.tree.tree):
            tkinter.Misc.bind(widget, "<Delete>", lambda e: self.delete_selected())
            tkinter.Misc.bind(widget, "<BackSpace>", lambda e: self.delete_selected())
        for key, (d_row, d_column) in {"Up": (-1, 0), "Down": (1, 0),
                                       "Left": (0, -1), "Right": (0, 1)}.items():
            tkinter.Misc.bind(self.canvas, f"<{key}>",
                              lambda e, r=d_row, c=d_column: self.nudge(r, c))

    # ------------------------------------------------------------ Bearbeiten

    def delete_selected(self) -> None:
        if self.session.selected_id != "window":
            self.session.execute(RemoveWidget(self.session.selected_id))

    def nudge(self, d_row: int, d_column: int) -> None:
        """Verschiebt das ausgewählte Widget um eine Zelle (Pfeiltasten)."""
        node = self.session.project.find(self.session.selected_id)
        if node is None or node.id == "window":
            return
        row, column = node.layout.row + d_row, node.layout.column + d_column
        if row < 0 or column < 0:
            return
        parent = self.session.project.parent_of(node.id)
        self.session.execute(MoveWidget(node.id, parent.id, row, column))

    def duplicate_selected(self) -> None:
        if self.session.selected_id == "window":
            return
        command = DuplicateWidget(self.session.selected_id)
        if self.session.execute(command):
            self.session.select(command.new_node_id)

    # ------------------------------------------------------------ Dateien

    def confirm_discard(self) -> bool:
        """True, wenn weitergemacht werden darf (gespeichert oder verworfen)."""
        if not self.session.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Ungespeicherte Änderungen", "Änderungen speichern?", parent=self)
        if answer is None:
            return False
        return self.save() if answer else True

    def new_project(self) -> None:
        if self.confirm_discard():
            self.session.new()

    def _file_dialog(self, ask: Callable[..., Any], **options: Any) -> str:
        """Öffnet einen Dateidialog; nie zwei gleichzeitig.

        Unter macOS bleiben Menüeinträge während eines modalen Dialogs bedienbar;
        ein zweiter Dialog würde Tks gemeinsamen Dialogzustand überschreiben.
        """
        if self._dialog_open:
            return ""
        self._dialog_open = True
        try:
            return ask(parent=self, **options) or ""
        finally:
            self._dialog_open = False

    def open_project(self) -> None:
        if not self.confirm_discard():
            return
        path = self._file_dialog(filedialog.askopenfilename,
                                 **project_dialog_options(save=False))
        if not path:
            return
        try:
            self.session.open(Path(path))
        except ProjectFileError as exc:
            messagebox.showerror("Öffnen fehlgeschlagen", str(exc), parent=self)

    def save(self) -> bool:
        if self.session.path is None:
            return self.save_as()
        return self._write(None)

    def save_as(self) -> bool:
        initialfile = f"{self.session.project.window.class_name.lower()}{SUFFIX}"
        chosen = self._file_dialog(filedialog.asksaveasfilename,
                                   **project_dialog_options(save=True, initialfile=initialfile))
        if not chosen:
            return False
        path = project_path(chosen)
        # Der Dialog hat nur nach dem gewählten Namen gefragt, nicht nach dem ergänzten
        if needs_overwrite_prompt(chosen, path) and not messagebox.askyesno(
                "Speichern unter", f"„{path.name}“ existiert bereits.\nErsetzen?",
                icon="warning", parent=self):
            return False
        return self._write(path)

    def _write(self, path: Optional[Path]) -> bool:
        try:
            self.session.save(path)
        except OSError as exc:
            messagebox.showerror("Speichern fehlgeschlagen", str(exc), parent=self)
            return False
        self.show_status(f"Gespeichert: {self.session.path.name}")
        return True

    def export(self) -> Optional[exporter.ExportResult]:
        if not self.save():
            return None
        try:
            result = exporter.export(self.session.project, self.session.path)
        except exporter.ExportNeedsConfirmation as exc:
            if not messagebox.askyesno("Export", str(exc), parent=self):
                return None
            result = exporter.export(self.session.project, self.session.path, force=True)
        created = f", {result.logic_path.name} angelegt" if result.logic_created else ""
        self.show_status(f"Exportiert: {result.ui_path.name}{created}")
        return result

    def run(self) -> None:
        result = self.export()
        if result is None:
            return
        self.console.write(f"$ {self.settings.interpreter} {result.logic_path.name}\n")
        try:
            self.runner.start(self.settings.interpreter, result.logic_path)
        except OSError as exc:
            self.console.write(f"Start fehlgeschlagen: {exc}\n")

    def choose_interpreter(self) -> None:
        path = self._file_dialog(filedialog.askopenfilename, title="Python-Interpreter wählen")
        if path:
            self.settings.interpreter = path
            self.show_status(f"Interpreter: {path}")

    def quit_app(self) -> None:
        if self.confirm_discard():
            self.runner.stop()
            self.destroy()


def main() -> None:
    MainWindow().mainloop()
