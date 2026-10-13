"""Hauptfenster: setzt die Panels zusammen, Menüs, Tastenkürzel, Dateien."""

from __future__ import annotations

import sys
import tkinter
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from ctk_builder import exporter
from ctk_builder.commands import DuplicateWidget, MoveWidget, RemoveWidget
from ctk_builder.project_io import SUFFIX, ProjectFileError
from ctk_builder.runner import ProcessRunner
from ctk_builder.session import Session
from ctk_builder.settings import Settings
from ctk_builder.ui.canvas import DesignCanvas
from ctk_builder.ui.drag_drop import DragController
from ctk_builder.ui.grid_overlay import GridOverlay
from ctk_builder.ui.output_console import OutputConsole
from ctk_builder.ui.palette import Palette
from ctk_builder.ui.properties import PropertiesPanel
from ctk_builder.ui.structure_tree import StructureTree

MOD = "Command" if sys.platform == "darwin" else "Control"
MOD_LABEL = "Cmd" if sys.platform == "darwin" else "Strg"
FILETYPES = [("CTk Builder Projekt", f"*{SUFFIX}")]


class MainWindow(ctk.CTk):
    def __init__(self, session: Optional[Session] = None,
                 settings: Optional[Settings] = None):
        super().__init__()
        self.session = session or Session()
        self.settings = settings or Settings()
        self.runner = ProcessRunner()
        self.geometry("1280x800")
        self.minsize(900, 600)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent", width=220)
        left.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(8, 4), pady=8)
        left.grid_rowconfigure(1, weight=1)
        self.palette = Palette(left, self.session)
        self.palette.grid(row=0, column=0, sticky="ew")
        self.tree = StructureTree(left, self.session)
        self.tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        self.canvas = DesignCanvas(self, self.session)
        self.canvas.grid(row=0, column=1, sticky="nsew", pady=8)
        self.grid_overlay = GridOverlay(self.canvas)
        self.drag = DragController(self.canvas, self.palette)
        self.console = OutputConsole(self, self.runner)
        self.console.grid(row=1, column=1, sticky="ew", pady=(0, 8))

        self.properties = PropertiesPanel(self, self.session)
        self.properties.configure(width=280)
        self.properties.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(4, 8), pady=8)

        self.status = ctk.CTkLabel(self, text="", anchor="w", height=20)
        self.status.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12)
        self.session.on_status = self.show_status
        self.session.subscribe(self.update_title)

        self._build_menu()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.update_title()

    # ------------------------------------------------------------ Rahmen

    def show_status(self, message: str) -> None:
        self.status.configure(text=message)
        self.after(5000, lambda: self.status.winfo_exists()
                   and self.status.cget("text") == message
                   and self.status.configure(text=""))

    def update_title(self) -> None:
        name = self.session.path.name if self.session.path else "Unbenannt"
        dirty = " •" if self.session.dirty else ""
        self.title(f"{name}{dirty} – CTk Builder")

    def _build_menu(self) -> None:
        menubar = tkinter.Menu(self)
        file_menu = tkinter.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Neu", accelerator=f"{MOD_LABEL}+N", command=self.new_project)
        file_menu.add_command(label="Öffnen…", accelerator=f"{MOD_LABEL}+O", command=self.open_project)
        file_menu.add_command(label="Speichern", accelerator=f"{MOD_LABEL}+S", command=self.save)
        file_menu.add_command(label="Speichern unter…", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exportieren", accelerator=f"{MOD_LABEL}+E", command=self.export)
        menubar.add_cascade(label="Datei", menu=file_menu)

        edit_menu = tkinter.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Rückgängig", accelerator=f"{MOD_LABEL}+Z", command=self.session.undo)
        edit_menu.add_command(label="Wiederholen", accelerator=f"{MOD_LABEL}+Shift+Z", command=self.session.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplizieren", accelerator=f"{MOD_LABEL}+D", command=self.duplicate_selected)
        edit_menu.add_command(label="Löschen", accelerator="Entf", command=self.delete_selected)
        menubar.add_cascade(label="Bearbeiten", menu=edit_menu)

        run_menu = tkinter.Menu(menubar, tearoff=False)
        run_menu.add_command(label="Ausführen", accelerator=f"{MOD_LABEL}+R", command=self.run)
        run_menu.add_command(label="Python-Interpreter wählen…", command=self.choose_interpreter)
        menubar.add_cascade(label="Ausführen", menu=run_menu)
        tkinter.Tk.configure(self, menu=menubar)

    def _bind_keys(self) -> None:
        shortcuts = {
            "n": self.new_project, "o": self.open_project, "s": self.save,
            "e": self.export, "r": self.run, "d": self.duplicate_selected,
            "z": self.session.undo, "Z": self.session.redo,
        }
        for key, action in shortcuts.items():
            self.bind_all(f"<{MOD}-{key}>", lambda e, a=action: (a(), "break")[1])
        self.bind_all(f"<{MOD}-Shift-z>", lambda e: (self.session.redo(), "break")[1])
        for widget in (self.canvas, self.tree.tree):
            widget.bind("<Delete>", lambda e: self.delete_selected())
            widget.bind("<BackSpace>", lambda e: self.delete_selected())
        for key, (d_row, d_column) in {"Up": (-1, 0), "Down": (1, 0),
                                       "Left": (0, -1), "Right": (0, 1)}.items():
            self.canvas.bind(f"<{key}>", lambda e, r=d_row, c=d_column: self.nudge(r, c))

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

    def open_project(self) -> None:
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, filetypes=FILETYPES)
        if not path:
            return
        try:
            self.session.open(Path(path))
        except ProjectFileError as exc:
            messagebox.showerror("Öffnen fehlgeschlagen", str(exc), parent=self)

    def save(self) -> bool:
        if self.session.path is None:
            return self.save_as()
        self.session.save()
        self.show_status(f"Gespeichert: {self.session.path.name}")
        return True

    def save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self, filetypes=FILETYPES, defaultextension=SUFFIX,
            initialfile=f"{self.session.project.window.class_name.lower()}{SUFFIX}")
        if not path:
            return False
        if not path.endswith(SUFFIX):
            path = path.removesuffix(".json") + SUFFIX
        self.session.save(Path(path))
        self.show_status(f"Gespeichert: {Path(path).name}")
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
        path = filedialog.askopenfilename(parent=self, title="Python-Interpreter wählen")
        if path:
            self.settings.interpreter = path
            self.show_status(f"Interpreter: {path}")

    def quit_app(self) -> None:
        if self.confirm_discard():
            self.runner.stop()
            self.destroy()


def main() -> None:
    MainWindow().mainloop()
