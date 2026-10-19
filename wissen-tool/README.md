# wissen

Beschaffungswerkzeug für das Buchprojekt *Ultimate Production Helper*. Holt
Transkripte, Kursseiten und PDF-Text in den vorhandenen `buch/eingang/`-Ordner.

**Ohne API-Key.** Transkripte kommen aus der Untertitelspur, Kursseiten aus
einem echten Browser mit der eigenen Anmeldung, PDFs aus dem Textlayer.

> **Zum ersten Mal hier?** → [START.md](START.md) führt durch Einrichtung und
> ersten Durchlauf. Diese Datei ist das Nachschlagewerk.

## Was es abdeckt — und was nicht

Das Werkzeug ersetzt genau die mechanischen Schritte aus `ANLEITUNG.md`:

| Schritt | vorher | jetzt |
| --- | --- | --- |
| Ablauf A 2 | Transkript per Scroll+Screenshot aus dem Embedded-Player | `wissen kurs <url>` |
| Ablauf C 1 | Transkript-Panel in Chrome öffnen, Text lesen, Abdeckung von Hand prüfen | `wissen yt <url>` — Abdeckung wird berechnet |
| Ablauf C 2 | Rohtranskript mit Kopf in `eingang/` schreiben | passiert automatisch |
| Ablauf C 6 | Datei nach `eingang/verarbeitet/` verschieben | `wissen verarbeitet <datei>` |
| Regel 5 | Screenshot zu einer offenen Frage besorgen | `wissen frames <url> --zeit 4:12` |

**Alles andere bleibt Handarbeit nach ANLEITUNG.md:** Delta-Abgleich und
Delta-Klassen, das Einarbeiten in die Genre-Rezepte und Teil I–V, das
Konzeptregister, `quellen.md`, die Kursdetaildateien unter `kurse/` und die
Notion-Meldung an den Learning Coach. Das Werkzeug schreibt ausschließlich
in `eingang/` und fasst keine andere Datei im `buch/`-Ordner an.

Es liegt deshalb auch keine Skill bei. `ANLEITUNG.md` ist die Anleitung –
eine zweite daneben würde nur mit ihr konkurrieren.

## Das Kernproblem: der Cross-Origin-iframe

In `ANLEITUNG.md` steht:

> Transkripte sind nur per Scroll+Screenshot lesbar (Cross-Origin-iframe,
> kein automatischer Texabgriff)

Das gilt für eine Chrome-Erweiterung, deren Skript *in* der Seite läuft – die
Same-Origin-Policy sperrt sie aus dem Player-iframe aus. Playwright steuert
den Browser von außen über das Debug-Protokoll und erreicht jeden Frame,
unabhängig vom Origin. Das Transcript-Panel ist damit direkt als Text
lesbar, ohne Scrollen und ohne Screenshots.

Gefunden wird das Panel über die **Dichte der Zeitmarken**: ein Container mit
mindestens fünf Kindelementen, deren ganzer Text eine Zeitangabe ist
(`0:42`, `12:57`), ist fast immer das Transkript – unabhängig davon, wie die
Plattform ihre CSS-Klassen nennt. Erst danach wird auf Benennungen wie
`transcript` geschaut.

Auch der Lektionstext wird in allen Frames gesucht, nicht nur im
Hauptdokument: Kursplattformen laden ihn regelmäßig in ein eigenes iframe,
im Hauptdokument steht dann nur die Navigationshülle.

### Wenn das Transkript gar nicht im DOM steht

Häufigster Fall bei eingebetteten Playern (Thinkspace nutzt Vimeo): das
Transkript-Panel ist Teil der Player-Oberfläche und existiert erst, nachdem
man ein Icon angeklickt hat. Statt diese Oberfläche nachzuklicken, holt das
Werkzeug die **Untertitelspur selbst** – per yt-dlp, mit der Kursseite als
Referer, weil solche Embeds meist auf die Plattform-Domain beschränkt sind.

Das ist nicht nur robuster, es ist auch besser: echte Zeitstempel aus der
VTT-Datei statt abgeschriebener Oberfläche, und dieselbe Entdoppelung,
Zeitmarken-Aufteilung und Abdeckungsprüfung wie bei YouTube.

Erkannt werden Vimeo, YouTube und Wistia. Findet das Werkzeug weder Panel
noch Player, sagt `wissen inspect`, was auf der Seite steht.

## Fortschritts-Buttons

`ANLEITUNG.md`: *„keine Fortschritts-/'Mark as done'-Buttons anklicken"*.

Das Werkzeug klickt nie von sich aus. Geklickt wird ausschließlich, was in
`wissen.toml` unter `klicks` ausdrücklich steht – und auch das nur, wenn der
Text des Elements die Sperrliste in `web.py` passiert (`complete`,
`mark as`, `abgeschlossen`, `weiter`, `submit`, `enroll`, `log out` …). Passt
ein konfigurierter Selektor versehentlich auf so einen Knopf, wird der Klick
verweigert und gemeldet statt ausgeführt.

## Einrichtung

Läuft auf dem eigenen Rechner, nicht in einer Cloud-Session: YouTube sperrt
Rechenzentrums-IPs, und ein Kurs-Login mit Zwei-Faktor braucht ein sichtbares
Browserfenster.

```bash
cd wissen-tool
bash setup.sh
```

Danach in `~/.config/wissen/wissen.toml` den Pfad setzen:

```toml
[ablage]
pfad = "~/Ultimate Production Helper/buch"
```

Und die Eingangsordner anlegen:

```bash
source .venv/bin/activate
wissen init
```

Voraussetzungen: Python 3.11+, ffmpeg (nur für Screenshots aus Videos).
Unter Windows statt `setup.sh`: `python -m venv .venv`,
`.venv\Scripts\activate`, `pip install -e ".[dev]"`,
`playwright install chromium`.

## Bedienung

### Einzelvideos (Ablauf C)

```bash
wissen yt https://www.youtube.com/watch?v=9QkIYDESems --praefix synthwave
```

Legt `eingang/synthwave_9QkIYDESems.md` an, mit dem Kopf aus Ablauf C
Schritt 2 und Zeitmarken alle 30 Sekunden:

```markdown
# Getting Inspired and Recording First Ideas

- Kanal: Cubase
- URL: https://www.youtube.com/watch?v=9QkIYDESems
- Veröffentlicht: 2024-08-30
- Erfassungsdatum: 2026-10-19
- Abdeckung: Transkript 0:00–12:57 von 13:03 (Auto-Captions)

> Rohmaterial — wird nicht ins Buch zitiert.
```

Die Abdeckungsprüfung aus Ablauf C Schritt 1 läuft automatisch: reicht die
letzte Zeitmarke nicht bis eine Minute an die Videolänge, steht
`UNVOLLSTÄNDIG, n s fehlen` im Kopf und das Werkzeug warnt. Die Schwelle
ist `max_luecke` in `wissen.toml`.

Von Hand erstellte Untertitel gewinnen immer gegen automatische – sie haben
Interpunktion. Im Kopf steht, welche Sorte es war, als Hinweis für die
`(?)`-Markierungen nach Regel 5.

Die rollenden Wiederholungen der Auto-Captions werden entfernt. Unbehandelt
steht darin jeder Satz zwei- bis dreimal.

### Kurslektionen (Ablauf A)

Einmal anmelden – sichtbares Chromium, Zwei-Faktor von Hand, Sitzung bleibt
im Profilordner:

```bash
wissen login https://campus.thinkspace.ac.uk/
```

Dann eine Lektion:

```bash
wissen kurs "https://campus.thinkspace.ac.uk/..." \
  --praefix thinkspace_how-to-write-cinematic-music \
  --modul "Modul 2: How to Write a Melody" \
  --lektion "Theme Writing with Bruce Broughton"
```

Oder ein ganzes Modul aus einer URL-Liste – der Browser bleibt dabei offen,
die Anmeldung gilt durchgehend:

```bash
cat > modul2.txt <<'EOF'
https://campus.thinkspace.ac.uk/... | Introduction and Overview
https://campus.thinkspace.ac.uk/... | How to Write a Melody
https://campus.thinkspace.ac.uk/... | Theme Writing with Bruce Broughton
EOF

wissen kurs --liste modul2.txt --praefix thinkspace_how-to-write-cinematic-music
```

Transkript und Seitentext landen als getrennte Abschnitte in einer Datei –
die automatische Seiten-Summary wird nicht angefasst, wie in `ANLEITUNG.md`
gefordert.

### Wenn kein Transkript gefunden wird

```bash
wissen inspect "https://campus.thinkspace.ac.uk/..." --ausgabe ./berichte
```

Öffnet die Seite mit der vorhandenen Anmeldung, geht jeden Frame durch und
schreibt einen Bericht: Frames mit Textmenge, alle Kandidaten mit fertigem
Selektor, Zeitmarkenzahl und Textvorschau, dazu Seitenbild und Frame-HTML zum
Nachsehen – und am Ende einen Block zum Hineinkopieren in `wissen.toml`.
Liest nur, klickt nichts. Ein eingeklapptes Panel lässt sich mit
`--klick '<selektor>'` einmalig mitöffnen; auch das läuft durch die
Sperrliste.

### Screenshots zu offenen Fragen (Regel 5)

Regel 5 der Genre-Rezepte: *was nur im Bild zu sehen ist, wird nicht geraten
→ offene Frage mit Timestamp; übernommen erst mit Screenshot.* Genau diese
Timestamps kommen hier herein:

```bash
wissen frames https://youtu.be/9QkIYDESems --zeit 4:12 --zeit 7:30
```

Die Bilder landen in `eingang/media/<video-id>/` und werden an der passenden
Stelle im Transkript verlinkt. Es wird **nicht** das ganze Video geladen:
ffmpeg springt im Stream an die Position und holt nur dieses Einzelbild.

### PDFs

```bash
wissen pdf ~/Downloads/Kursunterlagen/ --praefix jovani --kurs "Marc Jovani"
```

Alphabetisch eingelesen und durchnummeriert, Seitenmarken `[Seite n]`,
Original nach `eingang/media/`. Ein PDF gilt als Scan, wenn mindestens die
Hälfte der Seiten keinen Text hergibt – ein kurzes Titel- oder Übungsblatt
löst die Meldung also nicht aus. Nachbearbeiten mit
`ocrmypdf -l deu --skip-text alt.pdf neu.pdf`.

### Rückstand und Abschluss

```bash
wissen eingang                              # was liegt noch da
wissen quellen synthwave_9QkIYDESems.md     # Entwurf für quellen.md
wissen verarbeitet synthwave_9QkIYDESems.md # Ablauf C 6
```

`wissen quellen` gibt nur einen Textentwurf aus; `quellen.md` selbst wird
nicht angefasst. Beim Verschieben werden relative Bildlinks mitgezogen, weil
die Datei eine Ebene tiefer rutscht.

## Selektoren hinterlegen

Sobald `wissen inspect` den richtigen Selektor gezeigt hat:

```toml
[hosts."campus.thinkspace.ac.uk"]
plattform = "Thinkspace Education"
klicks = ["button[aria-label='Transcript']"]
transkript = ["#transcript-panel"]
inhalt = ["div.lesson-content"]
```

Der genaueste passende Host gewinnt, `thinkspace.ac.uk` kann also eine
Grundregel setzen und `campus.thinkspace.ac.uk` sie verfeinern.

## Weitere Störungen

**Seite lädt nicht fertig** → `warte_ms` hochsetzen.

**Portal merkt die Automatisierung** → `--headless` weglassen. Ein sichtbares
Fenster wird deutlich seltener blockiert.

**YouTube liefert keine Untertitel** → meist gibt es sie in der gewünschten
Sprache nicht; die Fehlermeldung nennt die vorhandenen. `sprachen` anpassen.

**Keine Screenshots** → ffmpeg fehlt, oder YouTube hat die Stream-URL
gesperrt. Dann lädt das Werkzeug ersatzweise nur die zwei Sekunden um den
Zeitpunkt.

## Tests

```bash
.venv/bin/python -m pytest
```

177 Tests über die netzunabhängigen Teile: Untertitel-Verarbeitung samt
Entdoppelung, Abdeckungsrechnung, Dateikopf und Dateinamen, Ablage und
Verschieben, `quellen.md`-Entwurf, PDF-Einlesen, Konfiguration, Spur- und
Formatwahl, Player-Erkennung, Frame-Auswahl beim Seitentext und die
Sperrliste für Fortschritts-Buttons.

Was Netz braucht, ist nicht automatisch getestet: der YouTube- und
Vimeo-Abruf und die Browser-Automatisierung. Für die Player-Erkennung prüft
ein Test aber immerhin, dass yt-dlp für jede erkannte URL-Form tatsächlich
einen Extraktor hat — ohne Netzzugriff.

## Rechtliches

Massendownloads verstoßen bei YouTube und den meisten Kursplattformen gegen
die Nutzungsbedingungen. Für den eigenen Lernbestand ist das üblich; für
Weitergabe oder Veröffentlichung ist es das nicht. Jede abgelegte Datei trägt
den Hinweis, dass sie Rohmaterial ist und nicht ins Buch zitiert wird.
