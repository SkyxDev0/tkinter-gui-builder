"""Startet das exportierte Programm als eigenen Prozess und sammelt die Ausgabe."""

from __future__ import annotations

import queue
import subprocess
import threading
from pathlib import Path
from typing import Optional


class ProcessRunner:
    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None
        self.output: "queue.Queue[str]" = queue.Queue()

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, interpreter: str, script: Path) -> None:
        """Beendet einen noch laufenden Prozess und startet script neu."""
        self.stop()
        script = Path(script)
        self.process = subprocess.Popen(
            [interpreter, "-u", script.name],
            cwd=script.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        threading.Thread(target=self._pump, args=(self.process,), daemon=True).start()

    def _pump(self, process: subprocess.Popen) -> None:
        for line in process.stdout:
            self.output.put(line)
        code = process.wait()
        self.output.put(f"[Prozess beendet mit Code {code}]\n")

    def stop(self) -> None:
        if self.running:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def drain(self) -> str:
        """Holt alle bisher gesammelten Ausgabezeilen ab."""
        lines = []
        while True:
            try:
                lines.append(self.output.get_nowait())
            except queue.Empty:
                return "".join(lines)
