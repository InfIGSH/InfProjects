# wissen

Liest YouTube-Tutorials, Online-Kurse und PDF-Unterlagen aus und legt sie als
Markdown in einer zentralen Wissensbasis ab, auf die andere Claude-Projects
zugreifen können.

**Ohne API-Key.** Transkripte kommen aus der Untertitelspur, Kursseiten aus
einem echten Browser mit deiner Anmeldung, PDFs aus dem Textlayer.

## Wie es aufgebaut ist

Vier Schichten, bewusst getrennt:

| Schicht | macht | liegt in |
| --- | --- | --- |
| Beschaffung | Transkripte, Seitentexte, Screenshots, PDF-Text holen | `wissen yt` / `kurs` / `pdf` |
| Normalisierung | alles wird Markdown mit YAML-Frontmatter, feste Ordnerstruktur | `store.py` |
| Ausarbeitung | Kompendien schreiben | Claude, via `.claude/skills/kompendium` |
| Ablage | ein Git-Repo als zentrale Quelle | deine Wissensbasis |

Die Trennung von `raw/` und `compendia/` ist der Kern: Rohmaterial wird nie
überschrieben, Kompendien lassen sich jederzeit neu erzeugen, ohne erneut
auszulesen. Das ist wichtig, weil erneutes Auslesen der teure und fehleranfällige
Teil ist.

## Einrichtung

Läuft auf deinem Rechner, nicht in einer Cloud-Session – YouTube sperrt
Rechenzentrums-IPs, und ein Kurs-Login mit Zwei-Faktor braucht ein sichtbares
Browserfenster.

```bash
cd wissen-tool
bash setup.sh
```

Das Skript legt eine virtuelle Umgebung an, installiert die Abhängigkeiten,
holt Chromium für Playwright und kopiert die Konfigurationsvorlage nach
`~/.config/wissen/wissen.toml`.

Danach dort den Pfad der Ablage setzen:

```toml
[ablage]
pfad = "~/Wissensbasis"
```

Und die Wissensbasis anlegen:

```bash
source .venv/bin/activate
wissen init
cd ~/Wissensbasis && git init && git add -A && git commit -m "Wissensbasis angelegt"
```

`wissen init` legt die Ordnerstruktur an, schreibt ein README, das anderen
Claude-Projects den Aufbau erklärt, und installiert die Kompendium-Skill unter
`.claude/skills/kompendium/`.

Voraussetzungen: Python 3.11+, ffmpeg (nur für Screenshots aus Videos).
Unter Windows statt `setup.sh`: `python -m venv .venv`,
`.venv\Scripts\activate`, `pip install -e ".[dev]"`, `playwright install chromium`.

## Bedienung

### YouTube-Tutorials

```bash
wissen yt https://www.youtube.com/watch?v=...
```

Holt die Untertitelspur und legt sie als Transkript mit Zeitmarken `[mm:ss]`
alle 30 Sekunden ab. Von Hand erstellte Untertitel gewinnen immer gegen
automatische – sie haben Interpunktion. Steht im Frontmatter
`untertitel: automatisch`, ist mit Fehlern bei Fachbegriffen zu rechnen.

Screenshots dazu, wenn du die Stellen schon kennst:

```bash
wissen yt https://youtu.be/... --zeit 4:12 --zeit 7:30
```

Oder – der üblichere Weg – erst das Transkript holen, Claude die erklärenden
Stellen bestimmen lassen und dann nachziehen:

```bash
wissen frames https://youtu.be/... --zeit 4:12 --zeit 7:30
```

Die Bilder landen in `assets/` und werden an der passenden Stelle im
Transkript verlinkt. Es wird **nicht** das ganze Video geladen: ffmpeg springt
im Stream an die Position und holt nur dieses Einzelbild.

### Online-Kurse hinter Login

Einmal anmelden:

```bash
wissen login https://lernplattform.de/login
```

Es öffnet sich ein sichtbares Chromium. Du meldest dich an – inklusive
Zwei-Faktor – und navigierst einmal in den Kurs. Die Sitzung bleibt im
Profilordner, alle späteren Aufrufe nutzen sie weiter. Es wird kein Passwort
gespeichert, nur die Cookies, die der Browser ohnehin hält.

Danach einzelne Seiten:

```bash
wissen kurs https://lernplattform.de/kurs/lektion-1 --kurs "Python Grundkurs" --lektion 1
```

Oder einen ganzen Kurs aus einer URL-Liste – das ist der Normalfall:

```bash
cat > python-kurs.txt <<'EOF'
https://lernplattform.de/kurs/lektion-1 | Einführung
https://lernplattform.de/kurs/lektion-2 | Variablen
https://lernplattform.de/kurs/lektion-3
EOF

wissen kurs --liste python-kurs.txt --kurs "Python Grundkurs"
```

Die Zeilennummer wird zur Lektionsnummer, die Kursreihenfolge bleibt also
erhalten. Zeilen mit `#` werden übersprungen. Gespeichert werden Seitentext
**und** Transkript, getrennt voneinander. Mit `--screenshot` kommt ein Bild
der ganzen Seite dazu.

### PDF-Kurse und Trainingseinheiten

```bash
wissen pdf ~/Downloads/Trainingsplan.pdf --kurs "Krafttraining Winter"
wissen pdf ~/Downloads/Kursunterlagen/ --kurs "Statik Grundlagen"
```

Beim Ordner werden alle PDFs alphabetisch eingelesen und durchnummeriert –
bei Dateinamen wie `01 Einführung.pdf` ergibt das direkt die richtige
Gliederung. Der Text bekommt Seitenmarken `[Seite n]`, das Original wird
danebengelegt.

Gescannte PDFs ohne Textlayer werden erkannt und im Frontmatter mit
`braucht_ocr: true` markiert. Nachbearbeiten und erneut einlesen:

```bash
ocrmypdf -l deu --skip-text alt.pdf neu.pdf
```

### Kompendien

Die Rohdaten sind Material, kein Lernstoff. Das Ausarbeiten macht Claude in
deiner Wissensbasis:

```bash
cd ~/Wissensbasis
claude "Erstelle ein Kompendium zum Kurs python-grundkurs"
```

Die mitgelieferte Skill `kompendium` legt fest, wie: Gliederung nach Sache
statt nach Quellenreihenfolge, jede Aussage mit Rückverweis auf Zeitmarke
oder Seite, Code wortgetreu, Screenshots nur wo das Wort nicht reicht.

## Zugriff aus anderen Claude-Projects

Die Wissensbasis ist ein Git-Repo mit reinem Markdown. Das ist absichtlich
das langweiligste mögliche Format – es ist versioniert, diffbar, durchsuchbar
und von allem lesbar.

- **claude.ai-Projects**: über den GitHub-Connector das Wissens-Repo einbinden
- **Claude Code**: das Repo klonen oder im Arbeitsverzeichnis mit anmelden
- **Notion oder Drive** als zusätzliche Leseoberfläche, falls du am Handy
  darauf zugreifen willst – aber nicht als einzige Ablage

`INDEX.md` ist der Einstieg. Es wird nach jedem Einlesen neu erzeugt und soll
verhindern, dass Claude den ganzen Bestand lesen muss, um etwas zu finden.
Bei Stapelverarbeitung mit `--kein-index` sparen und am Ende einmal
`wissen index` laufen lassen.

## Wenn etwas nicht klappt

**Kein Transkript auf der Kursseite gefunden.** Das Werkzeug sucht mit
Heuristiken nach dem Panel. Wenn die Plattform es anders benennt: im Browser
mit Rechtsklick → *Untersuchen* die Klasse oder ID ablesen und in
`wissen.toml` hinterlegen.

```toml
[hosts."lernplattform.de"]
klicks = ["button[data-purpose='transcript-toggle']"]
transkript = ["[data-purpose='transcript-panel']"]
inhalt = ["div.lesson-body"]
```

`klicks` öffnet ein eingeklapptes Panel, `transkript` liest es aus, `inhalt`
begrenzt den Seitentext. Der genaueste passende Host gewinnt, `lernplattform.de`
kann also eine Grundregel setzen und `kurse.lernplattform.de` sie verfeinern.

**Seite lädt nicht fertig.** `warte_ms` in `wissen.toml` hochsetzen.

**Portal merkt die Automatisierung.** `--headless` weglassen. Ein sichtbares
Fenster wird deutlich seltener blockiert.

**YouTube liefert keine Untertitel.** Meist gibt es sie in der gewünschten
Sprache nicht – die Fehlermeldung nennt die vorhandenen. Dann `sprachen` in
`wissen.toml` anpassen.

**Keine Screenshots.** ffmpeg fehlt, oder YouTube hat die Stream-URL gesperrt.
Das Werkzeug fällt dann automatisch darauf zurück, nur die zwei Sekunden um
den Zeitpunkt herunterzuladen.

## Tests

```bash
.venv/bin/python -m pytest
```

Abgedeckt sind die netzunabhängigen Teile: Untertitel-Verarbeitung inklusive
der rollenden Wiederholungen, Ablage und Index, PDF-Einlesen, Konfiguration,
Spur- und Formatwahl. Was Netz braucht – der eigentliche YouTube-Abruf und die
Browser-Automatisierung – ist nicht automatisch getestet.

## Rechtliches

Massendownloads verstoßen bei YouTube und den meisten Kursplattformen gegen
die Nutzungsbedingungen. Für den eigenen Lernbestand ist das üblich; für
Weitergabe oder Veröffentlichung ist es das nicht. Jede abgelegte Datei trägt
dazu einen Hinweis im Frontmatter.
