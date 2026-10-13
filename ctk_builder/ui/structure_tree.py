"""Strukturbaum aller Widgets (ttk.Treeview im CTk-Look)."""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

from ctk_builder.model import Node
from ctk_builder.session import Session

DARK = {"bg": "#2b2b2b", "fg": "#dce4ee", "sel": "#1f6aa5"}
LIGHT = {"bg": "#f2f2f2", "fg": "#1a1a1a", "sel": "#3a7ebf"}


def node_label(node: Node) -> str:
    if node.id == "window":
        return f"Fenster ({node.title})"
    return f"{node.name}  ·  {node.type.removeprefix('CTk')}"


class StructureTree(ctk.CTkFrame):
    def __init__(self, master, session: Session):
        super().__init__(master)
        self.session = session
        self._updating = False
        ctk.CTkLabel(self, text="Struktur", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4))
        self._style()
        self.tree = ttk.Treeview(self, show="tree", selectmode="browse",
                                 style="Builder.Treeview")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        session.subscribe(self.refresh)
        session.subscribe_selection(self._show_selection)
        self.refresh()

    def _style(self) -> None:
        colors = DARK if ctk.get_appearance_mode() == "Dark" else LIGHT
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Builder.Treeview", background=colors["bg"],
                        fieldbackground=colors["bg"], foreground=colors["fg"],
                        borderwidth=0, rowheight=24)
        style.map("Builder.Treeview",
                  background=[("selected", colors["sel"])],
                  foreground=[("selected", "#ffffff")])

    def refresh(self) -> None:
        self._updating = True
        try:
            self.tree.delete(*self.tree.get_children())
            window = self.session.project.window
            self.tree.insert("", "end", iid=window.id, text=node_label(window), open=True)

            def insert(parent: Node) -> None:
                for child in parent.children:
                    self.tree.insert(parent.id, "end", iid=child.id,
                                     text=node_label(child), open=True)
                    insert(child)

            insert(window)
        finally:
            self._updating = False
        self._show_selection()

    def _show_selection(self) -> None:
        node_id = self.session.selected_id
        if not self.tree.exists(node_id) or self.tree.selection() == (node_id,):
            return
        self._updating = True
        try:
            self.tree.selection_set(node_id)
            self.tree.see(node_id)
        finally:
            self._updating = False

    def _on_select(self, _event=None) -> None:
        if self._updating:
            return
        selection = self.tree.selection()
        if selection and selection[0] != self.session.selected_id:
            self.session.select(selection[0])
