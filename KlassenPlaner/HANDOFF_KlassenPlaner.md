# KlassenPlaner – Projekt-Snapshot

**Letzte Aktualisierung:** Oktober 2026 (Fix-Runde nach Code-Evaluation)
**Datei:** `Klassenbildungstool_v1.html` (3.040 Zeilen, 152 KB, SHA256: `e37af0b345e7de51…`)
**Vorgänger-Stand:** 2.887 Zeilen, SHA256 `2a895c2f…fe7a13ae3` (im Repo als erster Commit erhalten)
**Architektur:** Single-file, offline-first HTML/CSS/JS · keine externen Abhängigkeiten · localStorage-Autosave

**Einsatz:** zwei Dienstrechner (Sek I-Leitung, Jahrgangsleitung), keine geteilten Geräte.
Übergabe zwischen den Arbeitsplätzen erfolgt per **JSON-Export/Import**.

---

## Diese Runde: behobene Fehler

Alle Punkte sind headless in Chromium mit zwei 150-Schüler-Datensätzen nachgemessen
(Testskripte siehe „Testaufbau" unten). Das frühere Handoff meldete
„keine bekannten kritischen Bugs" – das war nicht korrekt.

### Stille Datenverluste

| # | Fehler | Vorher (gemessen) | Nachher |
|---|---|---|---|
| 1 | Klassen-CSV-Import stellte nie die Klassen wieder her: Export schrieb Spalte `Klasse`, Import las `r.Gruppe` | 0 von 150 Zeilen zugeordnet, Meldung trotzdem „Import erfolgreich." | 150 von 150, Zuordnung identisch zum Export; Meldung nennt jetzt die Zahl |
| 2 | Autosave hing allein an `renderGroups()`; AV/SV-Änderungen und Notizen wurden nicht gesichert | `localStorage` nach Noten- und Notizeingabe byte-identisch | beide Änderungen landen im Speicher |
| 3 | `_ts` wurde nie geschrieben, Recovery-Banner konnte das Alter des Stands nicht nennen | Zeitstempel toter Code | Banner zeigt „Stand: <Datum, Uhrzeit>" |
| 4 | Neue Person bekam `persons.length` als ID → nach einer Löschung eine bereits belegte ID | nächste ID 149 war schon an eine andere Person vergeben | `nextPersonId()` = max(id)+1, keine Kollision |
| 5 | `wishAliases` / `confirmedAbsent` überlebten einen neuen CSV-Import, IDs werden dabei neu vergeben | Aliase zeigten auf fremde Kinder | beide werden in `buildPersonsFromRows()` zurückgesetzt |

### Ausschluss (NICHTINEIN) ist jetzt ein echtes Constraint

Vorher existierte die Prüfung **fünfmal in drei Semantiken** (exakter Vollname im
Solver, im Preflight, auf der Karte und in der Statistik; Fuzzy-Matching in der
roten Box). Der Solver sah damit Konflikte nicht, die die Oberfläche anzeigte.
Zusätzlich bestrafte `computeSolverScore()` Verletzungen überhaupt nicht –
`swapValid()` verhinderte nur *neue*. Weil `greedyFallback()` am Ende Wunschpaare
zusammenführt und `canPlaceInGroup()` den Ausschluss nicht prüfte, blieb jede so
erzeugte Verletzung dauerhaft bestehen.

Gemessen mit einem Datensatz, in dem ein Paar gleichzeitig Wunsch- **und**
Ausschlusspaar ist (der realistische Fall „Elternwunsch gegen Lehrervermerk"):

- vorher: **6 von 6** Ausschlusspaaren landeten zusammen und blieben es nach
  beiden Optimierungsläufen; Statistik zeigte 4, rote Box 6
- nachher: **0 Verletzungen**, beide Anzeigen stimmen überein; die Wunscherfüllung
  sinkt dabei von 75/75 auf 67/75 – genau die 8 Wünsche, die nur unter Verletzung
  eines Ausschlusses erfüllbar wären

Umsetzung: eine gemeinsame Quelle (`exclusionNamesOf`, `getExclusionPartners`,
`exclusionPairKeys`, `exclusionConflictInGroup`), Strafterm `-1000 * Verletzungen`
in beiden Score-Modi, `canPlaceInGroup()` prüft den Ausschluss,
Zähler-Halbierung (`Math.ceil(n/2)`) entfernt. **Ein Ausschlussfeld darf jetzt
mehrere Namen enthalten**, getrennt durch `,` `;` `/` `&` oder „und".

### Fixierung trägt jetzt

- `attachDrag()` hob die Fixierung beim Ziehen **stillschweigend** auf – ein
  versehentlicher Zug genügte, und „Als geplant fixieren" war wertlos.
  Fixierte Karten sind jetzt `draggable="false"`.
- Das Klassen-Dropdown auf der Karte bleibt der bewusste Weg, eine Fixierung zu
  übergehen – mit Rückfrage.
- Drag&Drop in eine Klasse mit Ausschlusskonflikt fragt nach (Sperre wäre falsch:
  manuelles Verschieben muss gewinnen dürfen, nur nicht unbemerkt).
- „Struktur optimieren" fragt vor dem Lauf nach und nennt die Zahl der geschützten
  Personen. Vorher verwarf der Button ohne Rückfrage jede Handarbeit –
  „Wünsche optimieren" fragte, der destruktivere Button nicht.

### Export, Parser, Hygiene

- `csvEscape()` quotet jetzt auch das **Semikolon**. Die Klassen-Exporte sind
  semikolongetrennt; eine Notiz wie „Mutter angerufen; bitte beachten" hat vorher
  die Spalten verschoben (gemessen: 12 Felder statt 11; jetzt 11, Notiz intakt).
- `csvParse()` scannt den Text zeichenweise statt zeilenweise → **Zeilenumbrüche
  in Anführungszeichen** sind erlaubt (mehrzeilige Notiz aus Excel, Alt+Enter).
- Fehlermeldungen escapen ihre Werte. Vorher landete HTML aus der CSV ausführbar
  im Dokument (gemessen: `<img src=q onerror=…>` aus einem Namensfeld wurde
  ausgeführt). Heute geringes Risiko, **kritisch sobald der Electron-Wrapper kommt.**
- Klassen-CSV-Export: Semikolon + UTF-8-BOM + CRLF wie die übrigen Exporte, damit
  er in Excel direkt korrekt öffnet. Der Import erkennt das Trennzeichen selbst,
  ältere Komma-Dateien laden weiter.
- Beide Transport-Dateien tragen jetzt das **Datum im Namen**
  (`Klassenbildung_Jg5_2026-10-19.json`, `Klasseneinteilung_Jg5_2026-10-19.csv`).
  Ein konstanter Name endete als „vollexport (3).json" – bei zwei Arbeitsplätzen
  war nicht mehr erkennbar, welcher Stand der aktuelle ist.
- JSON-Import prüft `state.v` (bricht bei v>3 ab) und füllt fehlende Pflichtfelder.
- Gesamt-PDF: Popup-Guard und `setTimeout` vor `print()` wie beim Einzelklassen-
  Export (sofortiges `print()` druckte sonst leere Seiten); Tippfehler `>>` behoben.
- Toter Code entfernt: `renderTutors()` und `initTutorInputs()` samt 12 Aufrufstellen
  (die Zieltabellen existierten nicht mehr); doppeltes `</style>` bereinigt.

### Datenschutz

Förderbedarf ist ein Gesundheitsdatum nach Art. 9 DSGVO. Da nur zwei Dienstrechner
betroffen sind, ist das kein Offenlegungsproblem – es ging um Löschfrist und
Nachvollziehbarkeit:

- Neuer Button **„Sitzungsdaten löschen"** im Panel „Daten & Dateien": leert
  Programmzustand und `localStorage` (gemessen: Schlüssel danach `null`).
  Exportierte Dateien bleiben unberührt.
- Hinweis im Panel und neuer Abschnitt „Daten & Speicherort" im Hilfe-Modal:
  wo der Stand liegt, wie die Übergabe läuft, dass „Browserdaten löschen" den
  Zwischenstand mitnimmt, und dass nach Abschluss gelöscht werden sollte.

---

## Bewusst **nicht** geändert

| Punkt | Begründung |
|---|---|
| 5 Klassen, Töpfe 1–5, „Jahrgang 5" fest verdrahtet | Größter Deckel auf dem Produktwert, aber eine Produktentscheidung (wie viele Klassen, wo konfigurierbar, Migration bestehender Exporte). Eigene Runde. |
| `persons.find()` an 63 Stellen (O(N²) in Render und Statistik) | Gemessen unkritisch: 150 SuS → Render 87 ms, Statistik 9 ms. Optimierung ohne Problem; 63 Aufrufstellen in dieser Datei anzufassen ist das größere Risiko. |
| Strenge Topf-Balance im Solver | Siehe „Solver" unten – das ist eine fachliche Entscheidung, keine Reparatur. |
| `#`-Spalte der Klassenübersicht nummeriert bei aktivem Filter mit Lücken | Kosmetisch; Filterung läuft über CSS, Umnummerierung bräuchte JS. |
| C1 / C2 / D2 (Backlog) | Features. Erst nach dieser Runde. |

---

## Solver: was die Messung zeigt

Laufzeit bei **150 SuS**: Struktur 210 ms, Wünsche 138 ms. Die Handoff-Angabe
„~50 ms für N≤35" unterschätzte die Kapazität deutlich – ein ganzer Jahrgang
läuft flüssig.

Der Suchraum wird allerdings kaum genutzt. Über 80.000 Iterationen gemessen:

- 72 % der Versuche von Hard Constraints verworfen (davon 51.039 wegen Topf)
- 652 Tausche angenommen
- **37 echte Verbesserungen**

Grund: `swapValid()` erlaubt einen topfübergreifenden Tausch nur, wenn eine Gruppe
bei der Obergrenze und die andere bei der Untergrenze dieses Topfes liegt. Ist eine
Topf-Summe durch 5 teilbar, gilt `floor == ceil` → **topfübergreifende Tausche sind
mathematisch unmöglich**, der Solver tauscht dann nur innerhalb desselben Topfes.

Das Ergebnis ist trotzdem gut (Geschlecht und Topf exakt balanciert), weil der
Greedy-Start die Arbeit schon macht – die 80.000 Iterationen tragen wenig bei.
**„80.000 Iterationen" ist deshalb kein Qualitätsmaß.** Wer die Ergebnisse weiter
verbessern will, lockert die Topf-Balance (z.B. ±1 Toleranz statt floor/ceil) oder
führt 3er-Rotationen statt nur Paartausche ein – nicht mehr Iterationen.

---

## Offene Issues

_Keine bekannten Bugs._ Die oben gelisteten Punkte sind behoben und nachgemessen;
in allen Testläufen trat keine JS-Exception auf.

---

## Offenes Backlog (priorisiert)

### Runde 3 — Datenmodell (Opus 4.8)
- **C1:** Förderbedarf `lernen` zählt doppelt als 2 Personen (nur informativ, Zählanzeige)
- **C2:** Neue CSV-Spalte `DaZ`; gleichmäßige Verteilung; bevorzugt zu Tutoren mit Fächerkürzel `DE` (weiches Kriterium empfohlen)

### Runde 4 — Solver-Feature (Opus 4.8)
- **D2:** Wunschpaar gemeinsam verschieben + automatischer Tauschvorschlag (Topf/Geschlecht/AV/SV-Balance)

### Weitere (Sonnet ok)
- Klassenanzahl und Jahrgang konfigurierbar machen (siehe „Bewusst nicht geändert")
- Topf-Balance lockern / 3er-Rotation im Solver (siehe „Solver")
- Wunschnamen „Nicht angemeldet" in separater Liste, weiterhin zuordenbar
- Schuljahr einstellbar / automatische Erkennung aus Systemzeit (wenn 2026 → SJ 26/27)
- Copyright-Vermerk + Kontaktdaten im Hilfe-Modal (sobald Wortlaut vorliegt)
- Lizenz/Kopierschutz: erst relevant wenn Electron-App entschieden (Browser-Sandbox verhindert echten Schutz)

### App-Perspektive
- Electron-Wrapper geplant: echter Dateisystem-Autosave, kein Druckdialog für PDF, Installer, Lizenzierung möglich
- **Vor dem Wrapper:** das HTML-Escaping in Fehlermeldungen ist dort kein Schönheitsfehler mehr. Mit `nodeIntegration` wird aus der CSV-Injection Codeausführung auf dem Rechner.

---

## Architektur-Referenz

### Schlüssel-Datenstrukturen
```js
persons[i] = {
  id, name, vorname, geschlecht, topf,
  av, sv,               // 'A'–'E', default 'C'
  emotionale, geistigeen, hören, körperlmot, lernen, sehen, sprache, // boolean
  erstwunsch, zweitwu, nichtinein, notiz,
  locked, group         // group: 0–4 oder null
}
groups[g]   = [pid, …]   // 5 Arrays, Index 0–4
tutors[g][j] = { kürzel, fächer }  // 5 Klassen × 3 Tutoren
wishAliases  = { 'normalisierter text': personId }   // Reset bei neuem CSV-Import
confirmedAbsent = Set<string>        // als Array im JSON-Export
```

Autosave- und Exportformat: `{v:3, _ts:<ms>, persons, tutors, wishAliases, confirmedAbsent}`

### Schlüssel-Funktionen
| Funktion | Zweck |
|---|---|
| `detectSeparator(text)` | Semikolon/Komma/Tab-Erkennung |
| `csvParse(text, sep)` | Zeichenweiser Parser; Zeilenumbrüche in Quotes erlaubt |
| `csvEscape(v)` | Quotet `; , " \n \r \t` |
| `canonicalizeRow(raw)` | Roh-Header → kanonische Felder via Synonyme |
| `buildPersonsFromRows(rows)` | Validierung + persons[]-Aufbau; setzt Aliase zurück |
| `nextPersonId()` | max(id)+1 – **nie** `persons.length` verwenden |
| `isoDate(d)` | YYYY-MM-DD für Dateinamen |
| `matchPersonByName(str)` | Alias → Vollname → Token-Matching → Substring |
| `exclusionNamesOf(p)` | Ausschlussfeld in einzelne Namen zerlegen |
| `getExclusionPartners(p)` | **Einzige** Quelle für Ausschlusspartner einer Person |
| `exclusionPairKeys()` | Alle Ausschlusspaare als `"kleinereId_groessereId"` |
| `exclusionConflictInGroup(p,g,ignoreId)` | Liegt ein Ausschlusspartner in Klasse g? |
| `getExclusionViolations()` | Aktive Verletzungen – speist Statistik UND rote Box |
| `hillClimbSolve(mode)` | Greedy-Start + 80k Iterationen; `mode: 'struktur'|'wuensche'` |
| `computeSolverScore(ctx,mode)` | Score: Ausschluss (−1000) + Geschlecht + FB-Streuung + Wunschpaare |
| `canPlaceInGroup(pid,g)` | Hard Constraints inkl. Ausschluss |
| `renderGroups()` | Hauptansicht Panel 2; ruft alle attach*() + scheduleAutoSave |
| `renderZuteilung()` | Tab 2 Kanban; inkl. sortGroupForZuteilung() |
| `renderKlassenansicht()` | Tab 3; sortierbar via klassenansichtSort |
| `exportKlasseData(g)` | Gemeinsame Datenbasis (respektiert Sortierung) |
| `doSwapKlassen()` | Tausch: `mode='both'` oder `mode='tutors'` |
| `lockAllInGroup(g)` | Alle Personen einer Klasse fixieren |
| `bindTutorHeaderInputs()` | Bindet Tutor-Inputs im Kanban-Header, synct zur Hauptansicht |
| `clearSessionData()` | Zustand + localStorage löschen (Löschfrist) |
| `scheduleAutoSave()` | Debounced localStorage-Save (1.5s), schreibt `_ts` |

### Kritische CSS-Klassen (nie ohne Prüfung löschen)
- `.group` — Drag&Drop-Dropzone (data-group Attribut entscheidend)
- `.person` — Drag&Drop-Source + flex-direction:column (war ein wiederkehrender Bug wenn fehlend)
- `.group-details` — einklappbare Klassen-Gruppen Hauptansicht
- `.zuteil-col`, `.zuteil-header` — Kanban-Spalten
- `.sortable-th` — Event-Delegation für Tabellensortierung

### Bekannte Fallstricke
1. **CSS-Semikolon-Bug:** Style-Konstanten (`btnS`, `exBtn`), die als `${btnS}background:#xxx` konkateniert werden, MÜSSEN mit Semikolon enden – sonst wird background ignoriert. Zweimal aufgetreten.
2. **Doppeltes `id="msgArea"`** gab es früher (behoben) — bei Panel-1-Umbauten prüfen.
3. **Autosave hängt an `renderGroups()` und `updateStats()`.** Wer eine Mutation einbaut, die keines von beiden aufruft (wie damals die Notiz-Eingabe), muss `scheduleAutoSave()` selbst aufrufen.
4. **Ausschlussprüfung nur über `getExclusionPartners()`.** Keine eigene Namenssuche nachbauen – genau daran sind Solver und Oberfläche vorher auseinandergelaufen.
5. **IDs nie aus `persons.length`.** Immer `nextPersonId()`.
6. **`exportKlasseData(g)`** nutzt `sortIdsForKlassenansicht()` — Exporte respektieren aktive Sortierung.
7. **Tab-Wechsel zur Klassenzuteilung** ruft `renderZuteilung()` — wenn neue State-Variablen eingeführt werden, dort initialisieren.
8. **JSON-Export-Version:** aktuell `v:3`; beim nächsten Datenmodell-Umbau auf `v:4` erhöhen, Migrations-Fallback in `fullImportFile.onchange` ergänzen **und** die dortige Versionsschranke (`state.v>3`) mitziehen.

---

## Testaufbau

Die Prüfung lief headless in Chromium über Playwright gegen zwei generierte
150-Schüler-Datensätze (`fair150.csv`: Wunsch- und Ausschlusspaare disjunkt;
der Datensatz aus `gen.js`: Wunschpaar == Ausschlusspaar, also der Konfliktfall).
Geprüft wurden unter anderem: Import mit 150 Zeilen, Laufzeit beider Optimierer,
Ausschlussverletzungen nach jedem Lauf, Export→Import-Roundtrip über die echten
Handler, Semikolon und Zeilenumbruch in Notizen, ID-Vergabe nach Löschung,
Alias-Reset, Ziehbarkeit fixierter Karten, Rückfrage-Dialoge, Löschfunktion und
HTML-Injection aus CSV-Feldern.

Die Skripte liegen versioniert unter **`KlassenPlaner/tests/`** samt Generatoren,
Runner und einer README, die sagt, worauf bei den Ausgaben zu achten ist:

```bash
cd KlassenPlaner/tests
npm i playwright && npx playwright install chromium
./run-all.sh
```

Die Fixtures enthalten **keine echten Personendaten** – sie werden bei jedem Lauf
aus zwei Generatorskripten neu erzeugt und sind nicht versioniert (`.gitignore`).

Vor jeder Änderung am Tool lohnt ein Lauf: `pageerrors` muss überall leer sein,
`viol_nach_struktur`/`viol_nach_wuensche` müssen 0 sein, und Skript 05 prüft die
Fixes dieser Runde über die echten Handler.

---

## Warnings für nächste Session

- **Vor Runde 3 (C1/C2):** Datenmodell-Erweiterung (`lernen`-Gewichtung, `daz`-Feld) betrifft `persons[]`, `COLUMN_SYNONYMS`, `computeSolverScore`, Statistik-Anzeige — alle vier Stellen konsistent halten.
- **D2 (Wunschpaar-Verschiebung):** Eigene Optimierungsfunktion nötig (kein Eingriff in hillClimbSolve), mit Bestätigungs-UI. Komplex — nicht mit anderen Features mixen.
- **Electron-Pfad:** Single-HTML-Architektur bleibt erhalten; Electron-spezifische Änderungen (fs-Zugriff, Auto-Update) als separates Wrapper-Projekt, nicht in die HTML einbauen.
