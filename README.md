# CTk Builder

Drag & Drop GUI-Builder für [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter):
GUI im `grid()`-Layout zusammenklicken und sauberen Python-Code exportieren.

## Einrichten

Python 3.12+ mit Tk 8.6 oder neuer wird benötigt (das macOS-System-Python 3.9 mit Tk 8.5 reicht nicht).

```bash
# macOS (Homebrew)
brew install python@3.12 python-tk@3.12
python3.12 -m venv .venv

# Linux (Debian/Ubuntu)
sudo apt-get install -y python3-venv python3-tk xvfb
python3 -m venv .venv

.venv/bin/pip install -r requirements-dev.txt
```

## Starten

```bash
.venv/bin/python -m ctk_builder
```

## Tests

```bash
.venv/bin/pytest            # macOS / Linux mit Desktop
xvfb-run -a .venv/bin/pytest  # Linux ohne Display (z. B. Cloud/CI)
```

Ohne Display werden die Oberflächentests übersprungen.

## Dokumentation

- Design: `docs/superpowers/specs/2026-10-13-ctk-gui-builder-design.md`
- Pläne: `docs/superpowers/plans/`
