# KlassenPlaner – Projekt-Snapshot

**Letzte Aktualisierung:** Juli 2026  
**Datei:** `Klassenbildungstool_v1.html` (2.887 Zeilen, 142 KB, SHA256: `2a895c2f…fe7a13ae3`)  
**Architektur:** Single-file, offline-first HTML/CSS/JS · keine externen Abhängigkeiten · localStorage-Autosave

---

## Aktueller Stand

### Was implementiert ist (vollständig getestet)

**CSV-Import (flexibel)**
- Separator-Erkennung: Semikolon (DE-Standard) / Komma / Tab — automatisch, mit Rückfrage + In-Memory-Re-Parse ohne Neu-Upload
- Spalten-Synonyme: Header case-insensitiv, reihenfolgeunabhängig, Synonym-Wörterbuch (`COLUMN_SYNONYMS`) für alle 17 Felder
- AV/SV aus CSV gelesen; Fallback auf `'C'` wenn Spalte fehlt oder Wert ungültig (`parseAVSV`)

**Hauptansicht (Tab 1)**
- Panel 1: Daten & Dateien (farbcodierte Boxen: Personen-CSV grün / Sitzungsspeicher lila / Gebildete Klassen blau)
- Panel 2 (Klassen): Einklappbare Klassen-Gruppen, kompakte Karten mit AV/SV-Farbkodierung, Topf-Farbkodierung, Gender-Icons; alle Details immer sichtbar; Klassen-Dropdown direkt auf Karte
- Panel 3 (Statistik): Optimieren-Buttons im Header; Ausschluss-Verletzungen klickbar; Wunschnamen-Resolver mit Vorschlägen, Alias-Verwaltung
- Sticky Header + Tab-Bar (scrollt nicht weg)

**Klassenzuteilung (Tab 2)**
- Kanban-Board, responsive (flex-wrap)
- Pro-Spalte: Tutoren-Editor ausklappbar (3 Zeilen Kürzel + Fächer), Export-Buttons (CSV/Word/PDF) mit hellen Farben
- Tausch: Schüler+Tutoren ODER Nur Tutoren — Modus-Selector
- Sortierung global: Dropdown (Name/Topf/Geschlecht/AV/SV/FB) + Richtungsbutton
- „Als geplant fixieren"-Button pro Klasse (Bulk-Lock, toggle)
- Tutoren-Sync zur Hauptansicht: live (kein re-render, DOM-direktaktualisierung)

**Klassenübersicht (Tab 3)**
- Sub-Navigation: Alle Klassen / 5.1–5.5 einzeln
- Sortierbare Spaltenheader (Name, Topf, Geschlecht, AV, SV, FB) — klickbar, ▲/▼-Pfeil, pro Klasse unabhängig
- Export: CSV (Semikolon, UTF-8-BOM) / Excel / Word (Querformat) / PDF (Druckdialog)
- SuS-Zahl in jeder Export-Überschrift, laufende `#`-Spalte

**Solver (Hill-Climbing, rein JS)**
- Keine externen Abhängigkeiten, 80.000 Iterationen, ~50ms für N≤35
- Optimiert: Geschlechterbalance, Topf-Verteilung, Förderbedarf-Streuung, Wunschpartner
- Hard Constraints: NICHTINEIN, D/E-Cap, Topf-Balance, Locked

**Sonstiges**
- Auto-Save localStorage (`kbplaner_v3`), Recovery-Banner beim nächsten Öffnen
- Hilfe-Modal (?-Button im Header)
- Vollexport/Vollimport JSON v3 (inkl. wishAliases, confirmedAbsent)
- Clipboardfreie Ausschlussverletzungen: klickbar in Statistik UND auf Karten

---

## Offene Issues (bekannte Bugs)

_Keine bekannten kritischen Bugs._ Tutor-Sync-Bug (B1) wurde in letzter Session behoben.

---

## Offenes Backlog (priorisiert)

### Runde 3 — Datenmodell (Opus 4.8)
- **C1:** Förderbedarf `lernen` zählt doppelt als 2 Personen (nur informativ, Zählanzeige)
- **C2:** Neue CSV-Spalte `DaZ`; gleichmäßige Verteilung; bevorzugt zu Tutoren mit Fächerkürzel `DE` (weiches Kriterium empfohlen)

### Runde 4 — Solver-Feature (Opus 4.8)
- **D2:** Wunschpaar gemeinsam verschieben + automatischer Tauschvorschlag (Topf/Geschlecht/AV/SV-Balance)

### Weitere (Sonnet ok)
- Wunschnamen „Nicht angemeldet" in separater Liste, weiterhin zuordenbar
- Schuljahr einstellbar / automatische Erkennung aus Systemzeit (wenn 2026 → SJ 26/27)
- Copyright-Vermerk + Kontaktdaten im Hilfe-Modal (sobald Wortlaut vorliegt)
- Lizenz/Kopierschutz: erst relevant wenn Electron-App entschieden (Browser-Sandbox verhindert echten Schutz)

### App-Perspektive
- Electron-Wrapper geplant: echter Dateisystem-Autosave, kein Druckdialog für PDF, Installer, Lizenzierung möglich

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
wishAliases  = { 'normalisierter text': personId }
confirmedAbsent = Set<string>        // als Array im JSON-Export
```

### Schlüssel-Funktionen
| Funktion | Zweck |
|---|---|
| `detectSeparator(text)` | Semikolon/Komma/Tab-Erkennung |
| `csvParse(text, sep)` | Konfigurierbarer Parser mit Quote-Handling |
| `canonicalizeRow(raw)` | Roh-Header → kanonische Felder via Synonyme |
| `buildPersonsFromRows(rows)` | Validierung + persons[]-Aufbau |
| `matchPersonByName(str)` | Alias → Vollname → Token-Matching → Substring |
| `hillClimbSolve(mode)` | Greedy-Start + 80k Iterationen; `mode: 'struktur'|'wuensche'` |
| `computeSolverScore(ctx,mode)` | Score: Geschlecht + FB-Streuung + Wunschpaare |
| `renderGroups()` | Hauptansicht Panel 2; ruft alle attach*() + scheduleAutoSave |
| `renderZuteilung()` | Tab 2 Kanban; inkl. sortGroupForZuteilung() |
| `renderKlassenansicht()` | Tab 3; sortierbar via klassenansichtSort |
| `exportKlasseData(g)` | Gemeinsame Datenbasis (respektiert Sortierung) |
| `doSwapKlassen()` | Tausch: `mode='both'` oder `mode='tutors'` |
| `lockAllInGroup(g)` | Alle Personen einer Klasse fixieren |
| `bindTutorHeaderInputs()` | Bindet Tutor-Inputs im Kanban-Header, synct zur Hauptansicht |
| `scheduleAutoSave()` | Debounced localStorage-Save (1.5s) |

### Kritische CSS-Klassen (nie ohne Prüfung löschen)
- `.group` — Drag&Drop-Dropzone (data-group Attribut entscheidend)
- `.person` — Drag&Drop-Source + flex-direction:column (war ein wiederkehrender Bug wenn fehlend)
- `.group-details` — einklappbare Klassen-Gruppen Hauptansicht
- `.zuteil-col`, `.zuteil-header` — Kanban-Spalten
- `.sortable-th` — Event-Delegation für Tabellensortierung

### Bekannte Fallstricke
1. **CSS-Semikolon-Bug:** Style-Konstanten (`btnS`, `exBtn`) die als `${btnS}background:#xxx` konkateniert werden MÜSSEN mit Semikolon enden — sonst wird background ignoriert. Zweimal aufgetreten.
2. **Doppeltes `id="msgArea"`** gab es früher (behoben) — bei Panel-1-Umbauten prüfen.
3. **`renderTutors()`** ist eine No-Op (tutorInputTable existiert nicht mehr) — bleibt aber referenziert, null-guard ist drin.
4. **`exportKlasseData(g)`** nutzt `sortIdsForKlassenansicht()` — Exporte respektieren aktive Sortierung.
5. **Tab-Wechsel zur Klassenzuteilung** ruft `renderZuteilung()` — wenn neue State-Variablen eingeführt werden, dort initialisieren.
6. **JSON-Export-Version:** aktuell `v:3`; beim nächsten Datenmodell-Umbau auf `v:4` erhöhen und Migrations-Fallback in `fullImportFile.onchange` ergänzen.

---

## Warnings für nächste Session

- **Vor Runde 3 (C1/C2):** Datenmodell-Erweiterung (`lernen`-Gewichtung, `daz`-Feld) betrifft `persons[]`, `COLUMN_SYNONYMS`, `computeSolverScore`, Statistik-Anzeige — alle vier Stellen konsistent halten.
- **D2 (Wunschpaar-Verschiebung):** Eigene Optimierungsfunktion nötig (kein Eingriff in hillClimbSolve), mit Bestätigungs-UI. Komplex — nicht mit anderen Features mixen.
- **Electron-Pfad:** Single-HTML-Architektur bleibt erhalten; Electron-spezifische Änderungen (fs-Zugriff, Auto-Update) als separates Wrapper-Projekt, nicht in die HTML einbauen.
