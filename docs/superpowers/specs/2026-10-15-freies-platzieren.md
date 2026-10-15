# Freies Platzieren (place-Layout)

Stand: 2026-10-15 · Ergänzt `2026-10-13-ctk-gui-builder-design.md`

## Ziel

Widgets lassen sich frei auf der Fläche verschieben und in der Größe ändern, statt in
Rasterzellen einzurasten. Das Raster (`grid()`) bleibt als Option erhalten.

## Entscheidungen

| Thema | Entscheidung |
|---|---|
| Anordnung pro Container | Fenster und jeder Frame haben `manager`: `"place"` (Frei) oder `"grid"` (Raster) |
| Standard | Neue Projekte (`model.new_project()`): Fenster frei. Neue Frames übernehmen die Anordnung ihres Eltern-Containers. Die Dataclass-Standardwerte bleiben neutral (Raster) |
| Alte Projekte | Format 1 wird als Raster geladen; beim Öffnen erscheint „Alles frei anordnen“ |
| Dateiformat | Format 2, sobald ein Container frei ist; reine Raster-Projekte bleiben Format 1 (ohne `manager`, `x`, `y`) und damit für Builder 1.0.x lesbar |
| Position | `Layout.x`, `Layout.y` in logischen Pixeln (ohne CTk-Skalierung); das Modell ist die Quelle der Wahrheit |
| Größe | über die Eigenschaften `width`/`height`. In einem freien Container ist **jedes** Kind genau so groß – auch ein Frame mit Raster-Inhalt (`grid_propagate(False)` in Vorschau und Export) |
| Export | freie Container: `self.x.place(x=…, y=…)`, keine `grid_*configure`-Zeilen |
| Z-Reihenfolge | Reihenfolge der Kinder (später = oben); zugleich Reihenfolge im Export und Tab-Reihenfolge. Befehle „Nach vorne/hinten“, „Ganz nach vorne/hinten“ |

## Bedienung im freien Modus

- **Aus der Palette ziehen:** Ein Rahmen in der echten Größe des neuen Widgets (unsichtbar
  gemessenes Probe-Exemplar) folgt dem Mauszeiger (Zeiger in der Mitte).
- **Klick in der Palette:** unter dem ausgewählten Widget (gleiche linke Kante, 8 px
  Abstand), sonst unter dem untersten; passt es dort nicht, die erste freie Stelle.
- **Verschieben:** Das Widget folgt dem Mauszeiger live und liegt dabei obenauf. Über einem
  anderen Container bleibt es an seinem Platz, dort erscheint ein Rahmen. Der Ziel-Container
  wird über die Geometrie bestimmt (das gezogene Widget, Anfasser und Hilfslinien stören
  nicht). Außerhalb der Fläche bleibt das Widget am Rand seines Containers.
- **Einrasten:** an Kanten und Mitten der Geschwister, an Rand, Mitte und Innenabstand des
  Containers (Fenster 16 px, Frames 8 px), Abstand ≤ 6 px, pinke Hilfslinien. Optional
  zusätzlich am 8-px-Raster (Magnet in der Werkzeugleiste, gespeichert in den
  Einstellungen). `Alt` (macOS `Option`) während des Ziehens: kein Einrasten.
- **Größe ändern:** acht Anfasser am ausgewählten Widget, nur für Widgets mit `width` und
  `height` (CheckBox, Switch, RadioButton: nur Rahmen). CTk behandelt `width`/`height` oft
  als Mindestmaß (Text): gespeichert wird die sichtbare Größe. Ein Label mit `width` 0
  (automatisch) bekommt dabei eine feste Breite.
- **Pfeiltasten:** 1 px, mit `Shift` 10 px. Das Widget bewegt sich sofort; der Befehl folgt
  nach 800 ms Pause (länger als die Wiederholverzögerung der Tastatur), vor jeder anderen
  Änderung, vor jeder Geste und vor der Frage nach ungespeicherten Änderungen.
- **Reihenfolge:** `Strg/Cmd+↑/↓` (mit `Shift`: ganz), zusätzlich `[`/`]`; Rechtsklick-Menü
  und Menü „Bearbeiten“.
- **Esc:** bricht Ziehen oder Größe-Ändern ab (kein Befehl); sonst wählt Esc den
  Eltern-Container.
- **Duplizieren:** Kopie 16 px nach rechts unten, am Rand nach links oben – nie genau auf
  dem Original.
- **Anzeige:** Position bzw. Größe in einem kleinen Schild über dem Widget.
- Die Arbeitsfläche hält Positionen beim Ziehen, Anfassen und mit den Pfeiltasten im
  Container (mit gemessenen Größen). Befehle prüfen nur `x, y ≥ 0`. Ein kleineres Fenster
  verschiebt keine Widgets; außerhalb liegende bleiben über Struktur und x/y erreichbar.

## Umschalten Frei ↔ Raster

Eigenschaften von Fenster und Frames: **Anordnung: Frei | Raster** mit kurzem Hinweis zum
Verhalten beim Vergrößern des Fensters. Umschalten rechnet das Layout neu; exakt zurück
geht es nur per Rückgängig.

- **Raster → Frei:** Jedes Kind bleibt, wo es zu sehen war (Messung auf der Arbeitsfläche).
  Per `sticky` gestreckte Widgets und alle Frames behalten ihre sichtbare Größe als
  `width`/`height`; der umgestellte Frame selbst ebenso.
- **Frei → Raster:** Zeilen und Spalten sind Bänder ohne Lücke (`geometry.bands`); ein
  Widget, das sonst getrennte Bänder verbindet, überspannt sie (`rowspan`/`columnspan`).
  `sticky` folgt der Ausrichtung im Band, `padx`/`pady` = 4. Überschneidungen werden in
  Lesereihenfolge aufgelöst.
- „Alles frei anordnen“ stellt Fenster und alle Frames in einem Schritt um.

## Technik

- CTk skaliert `x`/`y` bei `place()` selbst (`int(v * s)`); Hilfselemente nutzen dieselbe
  Rechnung (`geometry.to_physical`), Messwerte werden mit `ceil(p / s)` zurückgerechnet
  (`geometry.to_logical`) – exakt bei 100–225 %.
- Hilfselemente (Auswahlrahmen, Anfasser, Hilfslinien, Rahmen) sind Kinder der
  Arbeitsfläche, nicht der Fensterfläche: nicht abgeschnitten, keine Entwurfs-Bindtags.
- Drag-Invarianten: Das gedrückte Widget wird nie zerstört, unsichtbar gemacht oder neu
  angeordnet (sonst geht der Maus-Grab verloren). Dafür zeichnet die Arbeitsfläche bei
  reinen Positionsänderungen frei platzierter Widgets nicht neu, sondern verschiebt die
  Ansichten (`DesignCanvas._move_views`). Abbrechen stellt Position, Größe und Stapelung
  direkt aus dem Modell wieder her (`restore`, `restack`). Live-`place()` nur in freien
  Containern. Ein Befehl während einer Geste (z. B. Strg+Z) bricht sie ab; jeder neue Klick
  räumt Reste einer Geste auf, deren Loslassen nie ankam. Nie `lower()` ohne Bezug, sonst
  verschwindet das Widget hinter dem internen Canvas eines CTkFrame.
- Frei → Raster ist polynomiell: Ein Band, dessen Mitglieder sich alle überlappen, wird
  nicht weiter untersucht; sonst ohne Zurückverfolgen.
- Einrasten (`ctk_builder/snapping.py`) und Geometrie (`ctk_builder/geometry.py`) ohne Tk,
  gut testbar.
- Raster-Overlay (Linien, Köpfe) nur für Raster-Container.

## Bewusst nicht enthalten

Mehrfachauswahl, Ausrichten/Verteilen mehrerer Widgets, Abstands-Hilfslinien, Anker
(`relx`/`rely`, Mitwachsen beim Vergrößern des Fensters).
