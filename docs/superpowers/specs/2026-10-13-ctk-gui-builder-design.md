# CTk Builder – Design-Spezifikation

Datum: 2026-10-13
Status: abgestimmt; Pläne unter `docs/superpowers/plans/`

## Ziel

Eine Desktop-App, mit der man eine CustomTkinter-GUI per Drag & Drop in einem `grid()`-Layout zusammenbaut und daraus sauberen, lesbaren Python-Code exportiert. Vorbild: PyUIBuilder – aber als native Python-Desktop-App.

## Entscheidungen

| Thema | Entscheidung |
|---|---|
| Ergebnis | Projektdatei (JSON) → Export von Python-Code |
| Plattform des Builders | Desktop-App in Python + CustomTkinter |
| Layout-Manager im erzeugten Code | ausschließlich `grid()` |
| Widget-Familie | CustomTkinter |
| Logik/Handler | Zwei Dateien: `<name>_ui.py` (immer überschrieben) + `<name>.py` (nur einmal angelegt, erbt von UI-Klasse) |
| Arbeitsfläche | Echte CTk-Widgets, normales Verhalten abgefangen, Overlays für Raster/Auswahl |
| Builder-Fensterlayout | Kopfzeile; links Icon-Leiste mit umschaltbarem Panel (Palette / Strukturbaum), Mitte Arbeitsfläche + Ausgabe, rechts Eigenschaften |
| Fenster pro Projekt | genau eins |

## Umfang Version 1

**Widgets:** `CTkLabel`, `CTkButton`, `CTkEntry`, `CTkTextbox`, `CTkCheckBox`, `CTkSwitch`, `CTkRadioButton`, `CTkFrame` (Container, beliebig verschachtelbar, mit eigenem Grid).

**Nicht in V1:** `CTkOptionMenu`, `CTkComboBox`, `CTkSlider`, `CTkProgressBar`, `CTkScrollableFrame`, `CTkTabview`, mehrere Fenster/Dialoge pro Projekt, `pack()`/`place()`, ttk-/tk-Export, eingebauter Code-Editor, Import von bestehendem Python-Code.

## Architektur

Zentral ist ein Projektmodell (Baum). Alle UI-Panels sind Ansichten darauf und ändern es ausschließlich über Befehle.

```
Projektmodell (Baum)
  Fenster(title, size, resizable, appearance_mode, color_theme, row/col-config)
   └ Widget(id, typ, name, props, grid-Position)
      └ Frame → Kinder … + eigene row/col-config

UI-Panels ──Befehle──► Modell ──Änderungsmeldung──► UI-Panels
Modell ──► project_io (JSON)
Modell ──► codegen (Python-Quelltext)
```

### Module

- **`model`** – Reine Datenklassen ohne Tkinter-Import: `Project`, `WindowNode`, `WidgetNode`, `GridConfig` (Gewichte, `minsize`, `uniform` je Zeile/Spalte). Bietet einen einfachen Beobachter-Mechanismus (`subscribe(callback)`), der nach jeder Änderung feuert.
- **`widget_specs`** – Ein Eintrag pro Widget-Typ: CTk-Klassenname, Präfix für Standardnamen (z. B. `button`), Liste der Eigenschaften (Name, Typ, Standardwert, Editor-Art), Flag `is_container`, Flag `has_command`. Neues Widget = neuer Eintrag.
- **`commands`** – Jede Modelländerung ist ein Befehlsobjekt mit `do()`/`undo()`: `AddWidget`, `RemoveWidget`, `MoveWidget` (inkl. Tausch), `SetProperty`, `SetLayout`, `InsertRow/Column`, `RemoveRow/Column`, `SetRowColConfig`. Ein `CommandStack` verwaltet Undo/Redo und das „ungespeichert“-Flag.
- **`project_io`** – Speichern/Laden als JSON (`*.ctkb.json`) mit Feld `format_version`. Atomar speichern (temporäre Datei + Umbenennen). Beim Laden Validierung; Fehler als eigene Exception mit verständlicher Meldung.
- **`codegen`** – Reine Funktion `generate(project) -> GeneratedFiles(ui_source, logic_source)`. Keine GUI-Abhängigkeit.
- **`ui/`** – `main_window`, `palette`, `structure_tree`, `canvas`, `properties`, `output_console`. Panels kennen nur Modell und Befehle, nicht einander. Die gemeinsame Auswahl (welcher Knoten ist ausgewählt) liegt in einem kleinen `Selection`-Objekt mit eigenem `subscribe()`, nicht im Projektmodell (sie wird nicht gespeichert und ist nicht Teil von Undo). CustomTkinter hat kein Baum-Widget; `structure_tree` nutzt daher `ttk.Treeview`, per `ttk.Style` an das CTk-Farbschema angepasst.

## Bedienung

### Widgets hinzufügen
- Drag aus der Palette auf eine Grid-Zelle; Zielzelle wird beim Ziehen hervorgehoben.
- Drop auf den Rand außerhalb des Grids legt automatisch eine neue Zeile/Spalte an.
- Ein Klick (ohne Ziehen) in der Palette fügt in die nächste freie Zelle des ausgewählten Containers ein; ist ein Nicht-Container ausgewählt, in dessen Eltern-Container.
- Neue Widgets bekommen einen eindeutigen Standardnamen (`button_1`, `button_2`, …).

### Auswahl
- Klick auf Widget wählt es aus (oranger Rahmen). Arbeitsfläche, Strukturbaum und Eigenschaften sind synchron.
- `Entf` löscht, `Cmd+D` dupliziert (in nächste freie Zelle), Pfeiltasten verschieben um eine Zelle.
- `Cmd+Z` / `Cmd+Shift+Z` für Undo/Redo, `Cmd+S` speichern, `Cmd+E` exportieren, `Cmd+R` ausführen.

### Verschieben
- Ausgewähltes Widget in andere Zelle oder in einen anderen Frame ziehen.
- Ist die Zielzelle belegt, werden die beiden Widgets getauscht.
- Ein Frame kann nicht in sich selbst oder einen eigenen Nachfahren verschoben werden.

### Zeilen und Spalten
- Rasterlinien werden für alle Container gezeichnet. Köpfe je Zeile/Spalte (Index und Gewicht, plus `[+]` zum Anhängen) erscheinen am Rand des **aktiven Containers** (ausgewählter Container bzw. Eltern-Container des ausgewählten Widgets), damit verschachtelte Frames übersichtlich bleiben.
- Klick auf einen Kopf zeigt im Eigenschaften-Panel `weight`, `minsize`, `uniform`.
- Rechtsklick-Menü: Zeile/Spalte davor/danach einfügen, löschen. Löschen ist nur erlaubt, wenn sie leer ist.

### Eigenschaften-Panel
- **Widget-Bereich:** `name` sowie die in `widget_specs` definierten Eigenschaften (z. B. `text`, `placeholder_text`, `width`, `height`, `fg_color`, `text_color`, `font`, `corner_radius`, `state`, `command`). Bei RadioButtons zusätzlich `variable_group` (Name einer gemeinsamen `StringVar`) und `value`.
- **Layout-Bereich:** `row`, `column`, `rowspan`, `columnspan`, `sticky` (vier Checkboxen N/S/E/W), `padx`, `pady`.
- **Fenster** (Wurzel im Baum ausgewählt): `title`, Startgröße, `resizable`, `appearance_mode` (Light/Dark/System), `color_theme` (blue/green/dark-blue), Name der generierten Klasse.

### Arbeitsfläche – Umsetzung
- Das entworfene Fenster wird als `CTkFrame` in der Arbeitsfläche gerendert; Widgets sind echte CTk-Instanzen in echtem `grid()`.
- Das normale Verhalten der Widgets wird unterdrückt: Klick-/Tastatur-Events werden auf allen internen Teil-Widgets abgefangen (rekursiv über `winfo_children()`) und auf Auswahl umgeleitet; `command` wird im Builder nicht gesetzt; Eingabefelder sind nicht editierbar.
- Rasterlinien und Auswahlrahmen werden als dünne Overlay-Elemente gezeichnet, deren Position aus `grid_bbox()` berechnet wird.
- Leere Zeilen/Spalten erhalten im Builder eine Mindestgröße, damit man hineinziehen kann; diese Mindestgröße landet nicht im generierten Code (außer der Nutzer setzt `minsize` explizit).
- Bei jeder Modelländerung wird die Arbeitsfläche komplett neu aufgebaut (V1: einfaches Neurendern, keine feingranulare Aktualisierung).
- Appearance-Mode und Farbthema sind in CustomTkinter global. Die Vorschau nutzt daher die Einstellungen des Builders; das echte Aussehen zeigt **▶ Ausführen**.

## Gestaltung

Moderner, kartenbasierter Look nach dem Vorbild von PyUIBuilder:

- **Farben:** heller Grundton mit weißen Karten (runde Ecken, dünner Rand); jede Farbe ist ein
  (hell, dunkel)-Paar, sodass auch der Dunkelmodus passt (`ui/theme.py`).
- **Kopfzeile:** Logo, Menüs „Datei“ und „Bearbeiten“, Projektname mit Hinweis „ungespeichert“,
  Rückgängig/Wiederholen, Speichern, Exportieren und der dunkle Hauptknopf **▶ Ausführen**.
  Auf macOS stehen die Menüs zusätzlich in der Systemmenüleiste.
- **Links:** Icon-Leiste (Widgets / Struktur), die das Seitenpanel umschaltet. Die Palette zeigt
  Kacheln mit gezeichneter Vorschau und hat ein Suchfeld.
- **Arbeitsfläche:** Rasterhintergrund; das entworfene Fenster sitzt in einem Rahmen mit Titelleiste
  (Ampelpunkte, Titel, Größe). Eine schwebende Werkzeugleiste bietet Duplizieren, Löschen und
  Rasterlinien ein/aus. Klick auf Hintergrund oder Titelleiste wählt das Fenster.
- **Eigenschaften:** Kopf mit Name und Typ, darunter aufklappbare Abschnitte. Kurze Auswahlen
  (≤ 3 Werte) sind Segment-Knöpfe, `sticky` sind vier Umschalt-Chips, `resizable` ein Schalter.
- **Icons** sind Vektorgrafiken auf `tkinter.Canvas` (`ui/icons.py`) – keine Bilddateien, keine
  zusätzliche Abhängigkeit, scharf auf jedem Bildschirm.

## Code-Export

Für ein Projekt `kontakt` entstehen neben der Projektdatei:

- `kontakt_ui.py` – wird bei jedem Export überschrieben.
- `kontakt.py` – wird nur angelegt, wenn sie noch nicht existiert; danach nie verändert.

### `kontakt_ui.py`
- Kopfkommentar `# AUTOMATISCH GENERIERT von CTk Builder – nicht von Hand bearbeiten!`
- Setzt `ctk.set_appearance_mode(...)` und `ctk.set_default_color_theme(...)` auf Modulebene.
- Klasse `<Name>UI(ctk.CTk)`; im `__init__`: Titel, Geometrie, `resizable`, `grid_rowconfigure`/`grid_columnconfigure` (nur nicht-Standardwerte), dann alle Widgets in Baumreihenfolge (Tiefensuche), jeweils Erzeugung + `.grid(...)`.
- Widgets werden als `self.<name>` gespeichert; Kinder eines Frames verwenden `self.<frame_name>` als Master.
- RadioButton-Gruppen: je Gruppe eine `self.<gruppe> = ctk.StringVar(value=...)` vor den Widgets.
- Nur Eigenschaften, die vom Standardwert abweichen, werden ausgegeben.
- Für jeden eindeutigen `command`-Namen eine Platzhalter-Methode, die `NotImplementedError` mit Hinweis auf die Logik-Datei wirft.
- Ausgabe ist deterministisch (gleiches Modell → byte-identischer Code).

### `kontakt.py`
- Importiert die UI-Klasse, definiert `class Kontakt(KontaktUI)` mit einer Methode pro beim ersten Export vorhandenem Handler (Rumpf `pass`) und `if __name__ == "__main__": Kontakt().mainloop()`.

### Ausführen
- **▶ Ausführen** = speichern + exportieren + `kontakt.py` mit dem konfigurierten Python-Interpreter als Unterprozess starten (`subprocess.Popen`, Arbeitsverzeichnis = Projektordner).
- stdout/stderr erscheinen in einem kleinen Ausgabe-Panel im Builder.
- Interpreter ist in den Builder-Einstellungen wählbar; Standard: der Interpreter, mit dem der Builder läuft.

## Fehlerbehandlung

- **Namen:** müssen gültige Python-Bezeichner sein (`str.isidentifier()`), kein Schlüsselwort (`keyword.iskeyword`), eindeutig im Projekt und dürfen nicht mit Attributen von `ctk.CTk` kollidieren. Ungültig → Feld rot, alter Wert bleibt.
- **Werte:** Zahlenfelder nur Ganzzahlen ≥ 0; Farben müssen `#rrggbb` oder ein von Tk akzeptierter Farbname sein. Ungültig → Feld rot, kein Befehl wird ausgeführt. Das Modell enthält nie ungültige Werte.
- **Überlappung:** Ein `rowspan`/`columnspan` oder Verschieben, das ein anderes Widget überdecken würde, wird abgelehnt; Hinweis in der Statusleiste.
- **Projektdatei:** atomar speichern; beim Laden Validierung von Struktur und `format_version`. Kaputte oder zu neue Datei → Dialog mit verständlicher Meldung, kein Absturz.
- **Export:** `<name>.py` wird nie überschrieben. Fehlt in vorhandener `<name>_ui.py` der Kopfkommentar, wird vor dem Überschreiben nachgefragt.
- **Ungespeicherte Änderungen:** Nachfrage beim Schließen, Öffnen oder Neu; Fenstertitel zeigt `•`.

## Tests (pytest)

- **model/commands:** Hinzufügen, Verschieben, Tauschen, Löschen, Zeilen/Spalten einfügen/löschen; `do()` + `undo()` stellt den Zustand exakt wieder her; Überlappungs- und Zyklus-Prüfungen.
- **project_io:** Roundtrip speichern → laden ergibt gleiches Modell; kaputte/zu neue Dateien erzeugen die definierte Exception.
- **codegen:** Snapshot-Tests gegen Referenzdateien; erzeugter Code besteht `compile()`; ein Test instanziiert die UI-Klasse tatsächlich (`update()`, `destroy()`), wird übersprungen, wenn kein Display verfügbar ist; Determinismus-Test.
- **ui:** Smoke-Tests – jedes Panel startet und reagiert auf eine Modelländerung. Drag & Drop wird manuell getestet.

## Technik

- Python 3.12+ (Homebrew oder python.org; das macOS-System-Python 3.9 mit Tk 8.5 ist ungeeignet).
- Abhängigkeiten: `customtkinter>=6.0,<7`; Entwicklung: `pytest`.
- Virtualenv `.venv` im Projektordner.
- Paketstruktur:

```
ctk_builder/
  __main__.py
  model.py
  widget_specs.py
  names.py          # Prüfung generierter Bezeichner
  commands.py
  project_io.py
  codegen.py
  exporter.py       # generierte Dateien schreiben
  session.py        # Projekt + Verlauf + Auswahl + Dateipfad
  runner.py         # exportiertes Programm starten
  settings.py       # ~/.ctk_builder.json
  ui/
    theme.py        # Farben (hell/dunkel), Schriften, Karten- und Knopfstile
    icons.py        # Vektor-Icons und Widget-Vorschauen
    widgets.py      # Icon-Knopf, Leisten-Eintrag, Umschalt-Chip, Tooltip
    main_window.py
    palette.py
    structure_tree.py
    canvas.py
    grid_overlay.py # Rasterlinien, Zeilen-/Spaltenköpfe
    drag_drop.py    # Drag & Drop
    properties.py
    output_console.py
tests/
  conftest.py
  snapshots/
  test_*.py         # ein Testmodul je Modul bzw. Panel
```

Start: `python -m ctk_builder`.
