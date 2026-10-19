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

**Mehrfach ausführen ist unbedenklich.** Die Befehle sind idempotent: `pip
install -e .` landet immer in derselben `.venv`, und `playwright install`
überspringt schon vorhandene Browser (daher der Schalter `--force`, der ein
Neuinstallieren erzwingt) und räumt alte Versionen von sich aus auf. Die
Browser liegen ohnehin nicht in der `.venv`, sondern in einem gemeinsamen
Cache — unter Windows `%LOCALAPPDATA%\ms-playwright`, unter macOS
`~/Library/Caches/ms-playwright`, unter Linux `~/.cache/ms-playwright`.

Nachsehen, was installiert ist (zeigt alle Playwright-Installationen des
Rechners): `playwright install --list`. Alles entfernen:
`playwright uninstall --all`.

`playwright install chromium` lädt drei Pakete — Chrome for Testing, ffmpeg
und die Headless Shell, zusammen etwa 200 MB. Das ist normal.

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

Unter Windows den Pfad in **einfache** Anführungszeichen setzen. Die sind in
TOML wortwörtlich, der Pfad kann also unverändert aus dem Explorer kommen:

```toml
pfad = 'C:\Users\Rene\Ultimate Production Helper\buch'
```

Mit doppelten Anführungszeichen ist `\` ein Escape-Zeichen (`\n`, `\t`, `\U`)
— `"C:\Users\..."` scheitert deshalb mit `Invalid hex value`. Dort gehen nur
Schrägstriche (`"C:/Users/..."`) oder doppelte Backslashes
(`"C:\\Users\\..."`).

## 3. Loslegen

Die virtuelle Umgebung aktivieren — der Befehl unterscheidet sich je System,
`source` gibt es nur in Bash und Zsh, und der Ordner heißt unter Windows
`Scripts` statt `bin`:

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows, PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

**Windows, Eingabeaufforderung (cmd)**

```cmd
.venv\Scripts\activate.bat
```

Dann, überall gleich:

```
wissen init
```

`wissen init` legt `eingang/`, `eingang/verarbeitet/` und `eingang/media/` an,
falls sie fehlen, und meldet sich, wenn im angegebenen Ordner keine
`ANLEITUNG.md` liegt — dann stimmt der Pfad aus Schritt 2 nicht.

Meldet PowerShell *„die Datei kann nicht geladen werden, da das Ausführen von
Skripts auf diesem System deaktiviert ist"*, dann blockiert die
Ausführungsrichtlinie das Aktivierungsskript. Zwei Wege: einmalig erlauben
mit

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

oder das Aktivieren ganz überspringen und das Programm direkt aufrufen (siehe
nächster Abschnitt) — dafür braucht es keine Richtlinienänderung.

### Das Aktivieren jedes Mal sparen

Das Programm liegt in der Umgebung und lässt sich direkt mit vollem Pfad
aufrufen, ohne vorher zu aktivieren.

macOS / Linux — einmal in `~/.zshrc` bzw. `~/.bashrc`:

```bash
alias wissen="$HOME/InfProjects/wissen-tool/.venv/bin/wissen"
```

Windows, PowerShell — einmal ins Profil (`notepad $PROFILE`):

```powershell
function wissen { & "$env:USERPROFILE\InfProjects\wissen-tool\.venv\Scripts\wissen.exe" @args }
```

Windows, cmd — direkt aufrufen:

```cmd
%USERPROFILE%\InfProjects\wissen-tool\.venv\Scripts\wissen.exe eingang
```

Danach geht `wissen ...` aus jedem Ordner.

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

Bei Thinkspace steckt das Transkript nicht in der Seite, sondern im
eingebetteten Vimeo-Player. Das Werkzeug klickt dessen Oberfläche nicht nach,
sondern holt die Untertitelspur direkt — in der Ausgabe steht dann
*„Transkript aus dem Vimeo-Player geholt"*, und im Dateikopf die
Player-URL unter `Video:`.

Steht stattdessen `KEIN Transkript` in der Ausgabe:

```bash
wissen inspect "<dieselbe URL>"
```

Das schreibt drei Sachen in den Ordner `berichte` **im aktuellen
Verzeichnis**:

| Datei | Inhalt |
| --- | --- |
| `<host>_<lektion>_<kennung>.bericht.md` | Frames, Transkript-Kandidaten mit fertigem Selektor, Vorschlag für `wissen.toml` |
| `….png` | Bild der ganzen Seite |
| `….frame0.html`, `.frame1.html`, … | das HTML jedes Frames zum Nachsehen |

Der Befehl gibt den vollen Ordnerpfad aus, du musst also nicht suchen. Mit
`--ausgabe <pfad>` geht auch ein anderer Ordner.

Den `.bericht.md` kannst du mir geben, dann trage ich den Selektor ein.
`inspect` liest nur und klickt nichts.

## 7. Ein ganzes Modul

Die URL-Liste musst du nicht von Hand zusammensuchen. Auf der Kursübersicht:

```bash
wissen links "https://campus.thinkspace.ac.uk/student/course/view/329"
```

Das sammelt alle Links der Seite, gruppiert sie nach Pfadform und legt die
größte gleichartige Gruppe als fertige Liste ab — die Lektionen eines Kurses
teilen in der Regel eine Form, Navigation und Fußzeile nicht. Liste
durchsehen, Reihenfolge prüfen, nicht gewollte Zeilen mit `#` auskommentieren.

Dann:

```bash
wissen kurs --liste "<die Datei>" --praefix thinkspace_how-to-write-cinematic-music
```

**Schon erfasste Lektionen werden übergangen** — auch die, die du bereits
eingearbeitet und nach `verarbeitet/` verschoben hast. Ein abgebrochener
Durchlauf lässt sich also einfach wiederholen, und eingearbeitete Lektionen
kommen nicht als Dubletten zurück. Ist nichts offen, öffnet sich kein
Browser. Mit `--neu-laden` holst du trotzdem alles erneut.

Von Hand geht die Liste natürlich auch — eine Zeile pro Lektion, Titel nach
dem `|` optional:

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
