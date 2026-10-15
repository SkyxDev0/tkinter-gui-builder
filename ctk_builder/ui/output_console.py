"""Ausgabe-Panel für das gestartete Programm."""

from __future__ import annotations

import customtkinter as ctk

from ctk_builder.runner import ProcessRunner
from ctk_builder.ui import theme

POLL_MS = 100


class OutputConsole(ctk.CTkFrame):
    def __init__(self, master, runner: ProcessRunner):
        super().__init__(master, fg_color=theme.CARD, corner_radius=theme.RADIUS,
                         border_width=1, border_color=theme.BORDER)
        self.runner = runner
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(header, text="Ausgabe", font=theme.font(14, "bold"),
                     text_color=theme.TEXT).pack(side="left")
        self.state_label = ctk.CTkLabel(header, text="", height=22, corner_radius=11,
                                        font=theme.font(11, "bold"))
        self.state_label.pack(side="left", padx=10)
        theme.secondary_button(header, text="Leeren", width=64, height=26,
                               font=theme.font(12), command=self.clear).pack(side="right")
        theme.secondary_button(header, text="Stopp", width=64, height=26,
                               font=theme.font(12), command=runner.stop).pack(side="right", padx=6)
        self.text = ctk.CTkTextbox(self, height=110, font=theme.mono(12), corner_radius=8,
                                   fg_color=theme.CONSOLE_BG, text_color=theme.TEXT,
                                   border_width=0)
        self.text.pack(fill="both", expand=True, padx=10, pady=(8, 10))
        self.text.configure(state="disabled")
        self._shown_running: bool | None = None
        self._show_state()
        self._poll_job = self.after(POLL_MS, self._poll)

    def destroy(self) -> None:
        self.after_cancel(self._poll_job)  # sonst meldet Tcl nach dem Schließen einen Fehler
        super().destroy()

    def write(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _show_state(self) -> None:
        running = self.runner.running
        if running == self._shown_running:
            return
        self._shown_running = running
        if running:
            self.state_label.configure(text="  ● läuft  ", fg_color=("#dcfce7", "#14321f"),
                                       text_color=("#15803d", "#4ade80"))
        else:
            self.state_label.configure(text="  bereit  ", fg_color=theme.HEADER_BG,
                                       text_color=theme.MUTED)

    def _poll(self) -> None:
        text = self.runner.drain()
        if text:
            self.write(text)
        self._show_state()
        self._poll_job = self.after(POLL_MS, self._poll)
