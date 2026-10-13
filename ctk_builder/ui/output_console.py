"""Ausgabe-Panel für das gestartete Programm."""

from __future__ import annotations

import customtkinter as ctk

from ctk_builder.runner import ProcessRunner

POLL_MS = 100


class OutputConsole(ctk.CTkFrame):
    def __init__(self, master, runner: ProcessRunner):
        super().__init__(master)
        self.runner = runner
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(4, 0))
        ctk.CTkLabel(header, text="Ausgabe", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Leeren", width=60, height=22,
                      command=self.clear).pack(side="right")
        ctk.CTkButton(header, text="Stopp", width=60, height=22,
                      command=runner.stop).pack(side="right", padx=4)
        self.text = ctk.CTkTextbox(self, height=110, font=ctk.CTkFont(family="Menlo", size=12))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")
        self.after(POLL_MS, self._poll)

    def write(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _poll(self) -> None:
        text = self.runner.drain()
        if text:
            self.write(text)
        self.after(POLL_MS, self._poll)
