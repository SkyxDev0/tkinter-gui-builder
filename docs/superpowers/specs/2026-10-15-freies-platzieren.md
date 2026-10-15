# Freies Platzieren (place-Layout)

Stand: 2026-10-15 · Ergänzt `2026-10-13-ctk-gui-builder-design.md`

## Ziel

Widgets lassen sich frei auf der Fläche verschieben und in der Größe ändern, statt in
Rasterzellen einzurasten. Das Raster (`grid()`) bleibt als Option erhalten.

## Entscheidungen

| Thema | Entscheidung |
|---|---|
| Layout pro Container | Fenster und jeder Frame haben `manager`: `"place"` (Frei) oder `"grid"` (Raster) |
| Standard | Neue Projekte: Fenster frei. Neue Frames übernehmen den Modus ihres Eltern-Containers |
| Alte Projekte | Format 1 wird als Raster geladen (unverändert); gespeichert wird Format 2 |
| Position | `Layout.x`, `Layout.y` in logischen Pixeln (ohne CTk-Skalierung), nur im freien Modus |
| Größe | über die vorhandenen Eigenschaften `width`/`height` des Widgets |
| Export | freie Container: `self.x.place(x=…, y=…)`, keine `grid_*configure`-Zeilen |
| Z-Reihenfolge | Reihenfolge der Kinder (später angelegt = oben), wie in Tk |

## Bedienung im freien Modus

- **Aus der Palette ziehen:** Ein Rahmen in Größe des neuen Widgets folgt dem Mauszeiger
  (Zeiger in der Mitte). Loslassen legt das Widget dort an.
- **Klick in der Palette:** legt das Widget an der ersten freien Stelle an (Suche von
  links oben, geschätzte Größen der Geschwister).
- **Verschieben:** Das Widget folgt dem Mauszeiger live (Griffpunkt bleibt erhalten).
  Über einem anderen Container erscheint dort ein Rahmen; Loslassen verschiebt das Widget
  in diesen Container (auch in Raster-Container: dann Zelle wie bisher).
- **Einrasten:** an Kanten und Mitten der Geschwister und des Containers (Abstand ≤ 6 px,
  pinke Hilfslinien), sonst auf ein 8-px-Raster. `Alt` (macOS: `Option`) gedrückt halten:
  kein Einrasten.
- **Größe ändern:** acht Anfasser am ausgewählten Widget (nur Widgets mit `width` und
  `height`); rastet ebenfalls ein. Mindestgröße 8 px.
- **Pfeiltasten:** 1 px, mit `Shift` 10 px. Im Raster-Modus weiter zellenweise.
- **Duplizieren:** Kopie um 16 px nach rechts unten versetzt.
- Positionen bleiben im Container: x, y ≥ 0; passt das Widget hinein, ragt es nicht über
  den rechten/unteren Rand.

## Umschalten Frei ↔ Raster

Eigenschaften von Fenster und Frames: Auswahl **Anordnung: Frei | Raster**.

- **Raster → Frei:** Jedes Kind behält seine sichtbare Position (gemessen auf der
  Arbeitsfläche). Wurde es per `sticky` gestreckt, wird die gestreckte Breite/Höhe als
  `width`/`height` übernommen, sofern das Widget diese Eigenschaften hat.
- **Frei → Raster:** Kinder werden nach Zeilen gruppiert (vertikale Überlappung), innerhalb
  einer Zeile nach x sortiert und auf Zellen verteilt. Das Raster bekommt so viele Zeilen und
  Spalten wie nötig.
- Beides ist ein Befehl und lässt sich rückgängig machen.

## Modell

- `WindowNode.manager`, `WidgetNode.manager` (nur Container sinnvoll; sonst ignoriert).
- `Layout` bekommt `x`, `y` (Standard 0). Raster-Felder bleiben erhalten, damit ein
  Wechsel zurück nichts verliert.
- `model.size_hint(node)`: geschätzte Größe aus den Eigenschaften (für die freie Stelle
  und Frei → Raster ohne Messung).
- Befehle: `AddWidget(…, x=, y=)`, `MoveWidget(…, x=, y=)` (Ziel frei),
  `SetLayout(x=, y=)`, `SetGeometry(node, x, y, width, height)` (Anfasser),
  `SetManager(container, manager, rects=None)`.

## Technik

- CTk skaliert `x`/`y` bei `place()` selbst; Messwerte (`winfo_x`, `winfo_width`) werden
  durch `_get_widget_scaling()` geteilt.
- Einrasten als reine Funktion ohne Tk (`ctk_builder/snapping.py`), gut testbar.
- Raster-Overlay (Linien, Köpfe) nur für Raster-Container.
