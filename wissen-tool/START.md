# Erster Start

Einmal einrichten, dann ist der Alltag drei Befehle. Zum Nachschlagen später:
`README.md`.

## 0. Tool auf den Rechner holen

Das Tool liegt im Repo `InfIGSH/InfProjects` auf dem Branch
`claude/zealous-galileo-htpo0r`.

```bash
cd ~
git clone -b claude/zealous-galileo-htpo0r https://github.com/InfIGSH/InfProjects.git
cd InfProjects/wissen-tool
```

Ohne Git: auf GitHub den Branch wählen → *Code* → *Download ZIP*, entpacken,
in den Ordner `wissen-tool` wechseln.

## 1. Einrichten

**macOS / Linux**

```bash
bash setup.sh
```

**Windows** — die beiden Konsolen haben unterschiedliche Syntax. Woran du
erkennst, in welcher du bist: die Eingabeaufforderung zeigt
`C:\Users\...>`, PowerShell zeigt `PS C:\Users\...>`.

PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
mkdir "$env:USERPROFILE\.config\wissen" -Force
copy wissen.toml.example "$env:USERPROFILE\.config\wissen\wissen.toml"
```

Eingabeaufforderung (cmd):

```cmd
py -3 -m venv .venv
.venv\Scripts\activate.bat
pip install -e ".[dev]"
playwright install chromium
mkdir "%USERPROFILE%\.config\wissen"
copy wissen.toml.example "%USERPROFILE%\.config\wissen\wissen.toml"
```

Wird `py` nicht gefunden: `python` statt `py -3`.

Zusätzlich **ffmpeg** (nur für Screenshots aus Videos nötig, sonst
überspringen):

- macOS: `brew install ffmpeg`
- Windows: `winget install Gyan.FFmpeg`
- Debian/Ubuntu: `sudo apt install ffmpeg`

## 2. Den einen Pfad eintragen

`~/.config/wissen/wissen.toml` öffnen (Windows:
`%USERPROFILE%\.config\wissen\wissen.toml`) und oben den Pfad zum
`buch`-Ordner setzen — der Ordner, in dem `ANLEITUNG.md` liegt:

```toml
[ablage]
pfad = "~/Ultimate Production Helper/buch"
```

Das ist die einzige Pflichtangabe. Alles andere in der Datei hat brauchbare
Vorgaben.

Unter Windows mit Schrägstrichen oder doppelten Backslashes schreiben — ein
einfacher Backslash gilt in TOML als Escape-Zeichen und macht die Datei
unlesbar:

```toml
pfad = "C:/Users/Rene/Ultimate Production Helper/buch"
```

## 3. Loslegen

```bash
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
wissen init
```

`wissen init` legt `eingang/`, `eingang/verarbeitet/` und `eingang/media/` an,
falls sie fehlen, und meldet sich, wenn im angegebenen Ordner keine
`ANLEITUNG.md` liegt — dann stimmt der Pfad aus Schritt 2 nicht.

### Das `source` jedes Mal sparen

Einmal in `~/.zshrc` (macOS) bzw. `~/.bashrc` (Linux) eintragen:

```bash
alias wissen="$HOME/InfProjects/wissen-tool/.venv/bin/wissen"
```

Danach geht `wissen ...` aus jedem Ordner, ohne Aktivieren.

Unter Windows geht dasselbe über den vollen Pfad zum Programm:

```cmd
%USERPROFILE%\InfProjects\wissen-tool\.venv\Scripts\wissen.exe eingang
```

Oder in PowerShell einmalig als Funktion ins Profil (`notepad $PROFILE`):

```powershell
function wissen { & "$env:USERPROFILE\InfProjects\wissen-tool\.venv\Scripts\wissen.exe" @args }
```

## 4. Erster Test: ein Video, das du schon kennst

Nimm Teil 1 der Cubase-Serie — die Datei dazu hast du von Hand erfasst, du
kannst das Ergebnis also direkt vergleichen:

```bash
wissen yt https://www.youtube.com/watch?v=9QkIYDESems --praefix test
```

Erwartet: eine neue Datei `eingang/test_9QkIYDESems.md` und eine
Abdeckungszeile in der Nähe von

```
Transkript 0:00–12:57 von 13:03 (Auto-Captions)
```

Vergleich mit `eingang/verarbeitet/synthwave_9QkIYDESems.md`. Stimmt der
Inhalt, lösch die Testdatei einfach wieder.

`--praefix test` statt `synthwave`, damit die Testdatei nicht wie ein echter
Eintrag aussieht.

## 5. Thinkspace anmelden

```bash
wissen login https://campus.thinkspace.ac.uk/
```

Es öffnet sich ein Chromium-Fenster. Dort anmelden, Zwei-Faktor durchlaufen,
**einmal in eine Lektion hineinklicken** (damit alle Cookies gesetzt sind),
dann im Terminal Enter drücken. Die Anmeldung bleibt im Profilordner
erhalten — das ist einmalig, nicht pro Sitzung.

## 6. Eine Lektion erfassen

```bash
wissen kurs "<URL der Lektion>" \
  --praefix thinkspace_how-to-write-cinematic-music \
  --modul "Modul 2: How to Write a Melody" \
  --lektion "Theme Writing with Bruce Broughton"
```

Der Präfix ist der Dateiname deiner Kursdatei unter `kurse/` — so bleibt
erkennbar, wohin das Material gehört.

Steht danach `KEIN Transkript gefunden` in der Ausgabe:

```bash
wissen inspect "<dieselbe URL>" --ausgabe ./berichte
```

Das schreibt einen Bericht mit allen Frames und Transkript-Kandidaten plus
einem fertigen Block für `wissen.toml`. Den Bericht kannst du mir geben,
dann trage ich den Selektor ein.

## 7. Ein ganzes Modul

URL-Liste anlegen, eine Zeile pro Lektion, Titel nach dem `|` optional:

```
https://campus.thinkspace.ac.uk/... | Introduction and Overview
https://campus.thinkspace.ac.uk/... | How to Write a Melody
https://campus.thinkspace.ac.uk/... | Theme Writing with Bruce Broughton
```

```bash
wissen kurs --liste modul2.txt --praefix thinkspace_how-to-write-cinematic-music
```

Der Browser bleibt für alle Seiten offen, die Anmeldung gilt durchgehend.
Scheitert eine Seite, läuft der Rest weiter und am Ende steht, was fehlt.

---

## Der Alltag

Beschaffen:

```bash
wissen yt <url> --praefix <genre>          # Einzelvideo
wissen kurs --liste <datei> --praefix <kurs>   # Kursmodul
wissen pdf <ordner> --praefix <kurs> --kurs "<Kursname>"
```

Nachsehen, was noch offen ist:

```bash
wissen eingang
```

Dann in einer Claude-Session nach `ANLEITUNG.md` einarbeiten — Delta-Abgleich,
Genre-Rezept oder Kursdatei, Konzeptregister. Das macht das Tool nicht.

Danach abschließen:

```bash
wissen quellen <datei>        # Entwurf für quellen.md, zum Hineinkopieren
wissen verarbeitet <datei>    # nach eingang/verarbeitet/ (Ablauf C 6)
```

Und wenn beim Einarbeiten eine offene Frage mit Timestamp übrig bleibt
(Regel 5 — Plugin-GUI, Automation, nur im Bild zu sehen):

```bash
wissen frames <url> --zeit 4:12 --zeit 7:30
```

Die Bilder landen in `eingang/media/` und werden an der passenden Stelle im
Transkript verlinkt.
