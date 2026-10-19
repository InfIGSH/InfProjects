# NW-Planungstools

Zwei Einzeldatei-Werkzeuge für die NW-Jahresplanung. Beide kommen ohne Internet, ohne Server und
ohne externe Bibliothek aus: HTML-Datei öffnen, fertig — auch von einem USB-Stick.

Hier liegen die **datenfreien Vorlagen**. Die Planungsdaten werden nicht mitgecheckt, weil dieses
Repository öffentlich ist; jede Vorlage lädt ihren Datensatz zur Laufzeit (Knopf oder Drag & Drop).
Die gefüllten Fassungen entstehen beim Bauen und bleiben lokal.

| Datei | Zweck | Datensatz |
|---|---|---|
| `jap-netz.html` | Vier Spalten — Kerncurriculum, Jahresarbeitsplan, Einzelstunden, Material — mit Pfad-Markierung und Lücken-Modus | `jap-data.json` |
| `taskcards-vorlage.html` | Überträgt Notion-Inhalte Karte für Karte in Taskcards-Pinnwände und merkt sich, was schon übertragen ist | `taskcards-spec.json` |

## Leitgedanke

Die Datensätze enthalten **Fakten**, die Tools treffen das **Urteil**. Was eine Lücke ist, ob ein
Kürzel-Treffer zählt und ob eine Stunde schon stattgefunden hat, entscheidet der Code beim Anzeigen
— nicht der Build. Dadurch lassen sich die Regeln ändern, ohne die Daten neu zu bauen, und ein
alter Datensatz wird nicht automatisch zu einer falschen Aussage.

## Tests

Beide Vorlagen laufen headless gegen einen echten Datensatz, mit einem kleinen DOM-Ersatz statt
eines Browsers. Das ist bei Einzeldatei-Tools die einzige Möglichkeit, eine Änderung zu prüfen:

```sh
node tests/jap-netz.test.js  jap-netz.html  ../pfad/zu/jap-data.json
node tests/taskcards.test.js taskcards-vorlage.html            # localStorage vorhanden
node tests/taskcards.test.js taskcards-vorlage.html nostore    # localStorage blockiert
```

Die Tests prüfen nicht nur, dass nichts abstürzt: sie rendern jede Fach-/Jahrgangs-Kombination,
öffnen das Detailpanel für jeden Knotentyp, und spielen beim Taskcards-Tool einen vollen
Fortschritts-Export, ein Löschen und ein Zurückladen durch.

## Was hier gegenüber dem ersten Entwurf geändert wurde

### 1. Zeit wird live gerechnet, nicht aus dem Snapshot gelesen

Vorher trug jede Stunde ein `vergangen`-Flag vom Bau-Zeitpunkt. Weil die erste Stunde im Datensatz
nach dem Stichtag lag, war das Flag bei **allen** Stunden `false` — der Zustand „gehalten“ war
praktisch unerreichbar, und ab der ersten gehaltenen Stunde hätte die Datei stillschweigend
Falsches gezeigt.

Jetzt gilt: `vergangen` und der 21-Tage-Materialhorizont werden gegen **heute** gerechnet
(`TODAY`, in UTC wie die Datumsangaben im Datensatz). Zusätzlich nennt die Kopfzeile das Alter des
Snapshots, ab 14 Tagen als Warnung. Was der Build einmal gezählt hat — Material- und Stundenstände
— kann das Tool nicht nachrechnen; der Hinweis sagt das ausdrücklich.

### 2. Angeschnittene Kerncurricula senden keine falschen Signale mehr

Ein KC, das in einem anderen Jahrgang verplant ist, erscheint trotzdem in Spalte 1, wenn ein
Baustein daraus vorgezogen wurde (bei NW 5 ist das TF3 wegen der Laborregeln). Seine Kompetenzen
standen auf rot „offen“, obwohl die Lückenlogik sie bewusst nicht als Lücke zählt. Sie sind jetzt
neutral markiert, und das Detailpanel schreibt dazu, in welchem Jahrgang sie verplant sind.

### 3. Der Status hängt nicht mehr allein an der Farbe

Statt eines farbigen Punkts mit Tooltip tragen die vier Zustände ein Zeichen: `✓` gehalten,
`›` geplant, `~` nur Vorbereitung/Bezug, `!` offen, `·` in diesem Jahrgang nicht verplant. Jedes
mit `aria-label`. Eine Legende steht im Hinweis-Panel.

### 4. Unscharfe Kürzel-Treffer werden als Frage gezeigt, nicht als Tatsache

Die Zuordnung „Kürzel auf der JAP-Seite → KC-Kompetenz“ entsteht automatisch und trägt einen
Trefferwert. Der Build schreibt jede davon als `status: "auto"` fort, auch bei 0.6. Das Tool wertet
jetzt selbst: unter `ALIAS_OK` (0.8) wird die Zuordnung als „prüfen“ markiert — am Chip in Spalte 3,
im Detailpanel und als Zähler in der Lücken-Leiste. Beim NW-5-Datensatz betrifft das 15 der 104
Stunden-Kompetenz-Zuordnungen.

### 5. Nicht ausgewertete Daten werden benannt statt verschluckt

Der Loader kannte neun Kantentypen und übersprang alles andere stumm. Jetzt zählt er unbekannte
Typen und listet sie im Hinweis-Panel; `kc_jap` ist dabei als bekannt-redundant vermerkt (die
24 Kanten sagen dasselbe wie das Feld `kc` am JAP-Knoten). Die zehn SOL-Kompetenzen, die im
Datensatz liegen, aber mit keinem JAP-Eintrag verbunden sind, bekommen keine eigene Spalte —
sie sind über das Hinweis-Panel einsehbar, damit sie nicht unsichtbar mitreisen.

### 6. Fortschritt ist sicherbar, und sein Ausfall ist sichtbar

Die Taskcards-Vorlage merkte sich Häkchen und Links in `localStorage` und verschluckte jeden
Fehler. Unter `file://` oder bei blockierten Website-Daten wären damit bis zu 79 Häkchen
unbemerkt verloren gegangen — während der Hilfetext versprach, der Browser merke sich alles.

Jetzt wird `localStorage` beim Start geprüft. Fällt es aus, erscheint ein rotes Banner und der
Fortschritt läuft für die Sitzung im Speicher weiter. **Fortschritt sichern** schreibt alles in
eine JSON-Datei, **laden** holt es zurück — auch auf einem anderen Rechner.

### 7. Bestehende Pinnwände werden abgeglichen, nicht neu gebaut

Die vier TF-Pinnwände existieren bereits; ihre Adressen standen im JG-5-Datensatz, während die
andere Vorlage anleitete, sie neu anzulegen und die Links von Hand einzutragen. Die Vorlage
unterscheidet nun `angelegt` (mit „Pinnwand öffnen“) von `neu anlegen`, belegt bekannte Link-Felder
vor und zeigt pro Pinnwand, was dort gepflegt wird.

Die Arbeitsteilung, nach der die Hinweise gesetzt sind:

- **Jahresarbeitsplan JG 5** — Jahresplanung für Jg. 5: Steckbriefe, Stundenfolge, Klassenarbeiten.
- **NW 5/6 – Themenfelder** — Material-Einstieg über Jg. 5 und 6.
- **TF-Pinnwände** — Bausteine, Stundenmaterial und Dateien des jeweiligen Themenfelds.

## Was die Generatoren noch brauchen

`build_html.py` und `build_taskcards.py` liegen nicht in diesem Repository. Damit die gefüllten
Fassungen alles Obige können, müssen sie drei Dinge ausgeben:

1. **`let SPEC = …` statt `const SPEC = …`.** Die Vorlage ersetzt den Datensatz zur Laufzeit,
   wenn eine Datei geladen wird; `const` verhindert das. (`jap-netz.html` nutzt dafür schon eine
   eigene Variable und braucht keine Änderung.)
2. **`SPEC.links`** — eine Zuordnung `link_slot → URL` für jede Pinnwand, deren Adresse bekannt
   ist, und `url` am Pinnwand-Objekt selbst. Ohne das muss man Adressen abtippen, die das System
   schon kennt.
3. **`board.pflege`** — ein Satz je Pinnwand, was dort gepflegt wird. Solange zwei Übersichten
   nebeneinander bestehen, ist das der einzige Schutz gegen doppelte Pflege.

Nicht dringend, aber lohnend: Der JAP-Datensatz enthält alle Fächer und Jahrgänge (680 KB, davon
rund ein Fünftel für die jeweils angezeigte Auswahl relevant; die 800 Kompetenz-Knoten allein
machen 335 KB). Ein Bau je Fach würde die Datei etwa um den Faktor fünf verkleinern. Und die
`kc_jap`-Kanten können entfallen, solange die JAP-Knoten ihr `kc`-Feld behalten.
