# Testskripte KlassenPlaner

Headless-Prüfung von `../Klassenbildungstool_v1.html` in Chromium über
Playwright. Die Skripte starten das Tool als `file://`-Seite, laden eine
generierte CSV und messen Verhalten – es gibt keine Testbibliothek und keine
Assertions, jedes Skript gibt ein JSON-Protokoll aus, das man liest.

## Start

```bash
npm i playwright
npx playwright install chromium
./run-all.sh
```

Liegt Chromium an einem eigenen Ort (z.B. in einem Container):
`PW_CHROME=/pfad/zu/chrome ./run-all.sh`

## Fixtures

Zwei generierte Jahrgänge mit je 150 erfundenen Schüler/innen – **keine echten
Personendaten**:

| Generator | Datensatz | Besonderheit |
|---|---|---|
| `gen-fair.js` | `fair150.csv` | Wunsch- und Ausschlusspaare disjunkt (Normalfall) |
| `gen-konfliktdatensatz.js` | `jahrgang150.csv` | Wunschpaar **ist** Ausschlusspaar – der Konfliktfall „Elternwunsch gegen Lehrervermerk" |
| `03-…` erzeugt selbst | `skew150.csv` | Geschlecht korreliert mit Topf |

`fixtures/` wird nicht versioniert, die Dateien entstehen beim Start neu.

## Skripte

| Skript | prüft |
|---|---|
| `01-import-solver-performance.js` | Import von 150 Zeilen, Laufzeit von Render/Statistik/Solver, Ergebnisqualität (Geschlecht, Topf, Wünsche), Ausschlusszähler |
| `02-ausschluss-roundtrip-autosave.js` | Ausschlussverletzungen nach Import und nach beiden Optimierern, Export→Import, Semikolon in Notizen, Autosave von Noten und Notizen, HTML-Injection |
| `03-skew-injection-drag.js` | schiefe Geschlechterverteilung, Rückfrage bei „Struktur optimieren", Injection, Fixierung beim Ziehen |
| `04-solver-suchraum.js` | wie viele der 80.000 Iterationen tatsächlich etwas bewirken (Hard-Constraint-Ablehnungen, angenommene Tausche, echte Verbesserungen) |
| `05-fixes-echte-handler.js` | die Fixes über die **echten** Handler: CSV-Roundtrip per Download/Upload, Semikolon- und Mehrzeilen-Notiz, ID-Vergabe nach Löschung, Alias-Reset, Ziehbarkeit fixierter Karten, Löschfunktion |

## Worauf zu achten ist

- `pageerrors` muss in jedem Skript `[]` sein.
- In `02` müssen `viol_nach_struktur` und `viol_nach_wuensche` **0** sein.
- In `01` gegen `jahrgang150.csv` (Konfliktfall) ist eine Wunscherfüllung
  **unter** 75/75 korrekt: die Wünsche, die nur unter Verletzung eines
  Ausschlusses erfüllbar wären, dürfen nicht erfüllt werden.
- `05` muss überall `true` / `kollidiert:false` / `localStorage:null` zeigen.
