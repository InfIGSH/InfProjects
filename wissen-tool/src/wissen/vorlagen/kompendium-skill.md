---
name: kompendium
description: Aus dem Rohmaterial der Wissensbasis (raw/) ein Kompendium zu einem Kurs oder Thema schreiben oder fortschreiben. Verwenden, wenn aus Transkripten, Kursseiten oder PDF-Texten eine zusammenhaengende Lernunterlage werden soll, oder wenn ein vorhandenes Kompendium um neues Material erweitert wird.
---

# Kompendium schreiben

Ein Kompendium ist die ausgearbeitete Fassung des Rohmaterials: durchgehend
lesbar, geordnet, mit Verweisen zurueck auf die Quelle. Es ist eine abgeleitete
Datei und darf jederzeit neu geschrieben werden.

## Vorgehen

1. **Bestand sichten.** `INDEX.md` lesen, nicht alle Dateien. Daraus ergibt
   sich, welche Quellen zum Kurs oder Thema gehoeren.
2. **Quellen lesen.** Die zugehoerigen Dateien unter `raw/` vollstaendig
   lesen -- Transkripte, Seitentexte, PDF-Texte.
3. **Gliederung festlegen,** bevor geschrieben wird. Sie folgt der Sache,
   nicht der Reihenfolge der Quellen: was in drei Videos verteilt erklaert
   wird, gehoert in ein Kapitel.
4. **Schreiben** nach `compendia/<kurs-slug>.md`.
5. **`wissen index`** ausfuehren, damit das Kompendium im Index auftaucht.

## Aufbau der Datei

```markdown
---
id: komp:<kurs-slug>
typ: kompendium
titel: <Klartext-Titel>
kurs: <kurs-slug>
stand: <YYYY-MM-DD>
quellen:
  - raw/kurse/<kurs>/01--...md
  - raw/youtube/<id>--...md
---

# <Titel>

## Worum es geht
Drei bis fuenf Saetze: was der Kurs behandelt, fuer wen, was man danach kann.

## Ueberblick
Die Gliederung als Liste, damit man springen kann.

## <Kapitel 1>
Der ausgearbeitete Inhalt.

## Schluesselbegriffe
Begriff -- Erklaerung in einem Satz. Nur was wirklich gebraucht wird.

## Offene Fragen
Was im Material unklar blieb oder sich widersprach. Weglassen, wenn nichts.

## Quellen
Die verwendeten Dateien mit Link und Originalquelle.
```

## Regeln

**Quellen bleiben nachvollziehbar.** Jede inhaltliche Aussage muss sich
zuordnen lassen. Bei Videos die Zeitmarke mitnehmen, bei PDFs die Seite:

```markdown
Rekursion braucht immer einen Abbruchfall ([Video, 04:12](../raw/youtube/abc--rekursion.md)).
Die Formel steht in der Trainingsunterlage ([Seite 7](../raw/pdf/training/03--woche-3.md)).
```

**Automatische Untertitel sind fehlerhaft.** Steht im Frontmatter
`untertitel: automatisch`, dann sind Fachbegriffe, Eigennamen und
Zahlen oft verstuemmelt. Offensichtliches stillschweigend korrigieren;
bei Unsicherheit die Stelle unter "Offene Fragen" nennen, statt zu raten.

**Code und Formeln wortgetreu uebernehmen,** in Codebloecke mit
Sprachangabe. Nichts dazuerfinden, was nicht im Material stand -- auch
nicht, wenn eine Luecke offensichtlich scheint.

**Screenshots einbinden, wo das Wort nicht reicht** -- bei Oberflaechen,
Diagrammen, Schaltplaenen. Vorhandene stehen im Frontmatter unter `assets`.
Fehlt ein Bild an einer Stelle, die es braucht, die Zeitpunkte aus dem
Transkript bestimmen und nachziehen:

```bash
wissen frames <video-url> --zeit 4:12 --zeit 7:30
```

Sparsam bleiben: ein Bild pro erklaerbedingter Stelle, nicht pro Abschnitt.

**Beim Fortschreiben** das vorhandene Kompendium zuerst lesen und die
gewachsene Gliederung weiterfuehren, statt sie umzuwerfen. Neues Material
einsortieren, `stand` und `quellen` nachziehen.

**Nie `raw/` aendern.** Das ist Rohmaterial. Korrekturen gehoeren ins
Kompendium.
