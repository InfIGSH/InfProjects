"""Die Ablage: Ordnerstruktur, Schreiben, Index.

Aufbau der Wissensbasis:

    raw/youtube/<video-id>--<slug>.md     Transkripte, unveraendert
    raw/kurse/<kurs>/<nn>--<slug>.md      Seitentext + Kurstranskripte
    raw/pdf/<kurs>/<nn>--<slug>.md        PDF-Text (+ Original daneben)
    assets/<quellen-id>/...               Screenshots und Seitenbilder
    compendia/<kurs>.md                   die generierten Kompendien
    INDEX.md                              Einstiegspunkt, maschinell erzeugt

Trennung ist Absicht: `raw/` wird nie ueberschrieben, `compendia/` kann
jederzeit neu erzeugt werden, ohne erneut auszulesen.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterator

from . import schema

ROH_ORDNER = {"youtube": "raw/youtube", "kurs": "raw/kurse", "pdf": "raw/pdf"}

_BASIS_README = """# Wissensbasis

Zentrale Ablage fuer ausgelesene Lerninhalte. Erzeugt und gepflegt mit dem
Werkzeug `wissen` (siehe InfProjects/wissen-tool).

## Wie diese Ablage zu lesen ist

| Ordner | Inhalt |
| --- | --- |
| `raw/youtube/` | Transkripte von YouTube-Tutorials, mit Zeitmarken `[mm:ss]` |
| `raw/kurse/` | Seitentext und Transkripte aus Online-Kursen, pro Kurs ein Ordner |
| `raw/pdf/` | Text aus PDF-Kursen und Trainingseinheiten, Seitenmarken `[Seite n]`, Original liegt daneben |
| `assets/` | Screenshots, pro Quelle ein Ordner; Dateiname ist der Zeitpunkt im Video |
| `compendia/` | die ausgearbeiteten Kompendien -- abgeleitet, jederzeit neu erzeugbar |

`raw/` ist Rohmaterial und wird nicht von Hand bearbeitet. Wer etwas
korrigieren will, korrigiert es im Kompendium.

Jede Datei beginnt mit einem YAML-Frontmatter (`id`, `typ`, `titel`, `quelle`,
`kurs`, `lektion`, `tags`, `assets`). Alle Pfade darin sind relativ zu diesem
Ordner. `INDEX.md` wird daraus erzeugt -- dort anfangen, nicht alle Dateien lesen.

## Einstieg

1. `INDEX.md` lesen, um Bestand und Struktur zu sehen.
2. Fuer eine inhaltliche Frage zuerst in `compendia/` nachsehen.
3. Nur wenn es auf den Wortlaut ankommt (Zitat, Zeitpunkt, Codebeispiel),
   in die zugehoerige Datei unter `raw/` gehen -- das Kompendium nennt sie.

Zum Schreiben und Fortschreiben der Kompendien liegt eine Anleitung unter
`.claude/skills/kompendium/SKILL.md`.

Die Inhalte sind gespeicherte Kopien fuer persoenliche Lernzwecke.
"""


class Ablage:
    """Zugriff auf die Wissensbasis."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()

    # -- Einrichtung -----------------------------------------------------

    def init(self) -> list[Path]:
        """Legt die Ordnerstruktur an. Vorhandenes bleibt unberuehrt."""
        angelegt: list[Path] = []
        skill = self.root / ".claude" / "skills" / "kompendium" / "SKILL.md"
        if not skill.exists():
            skill.parent.mkdir(parents=True, exist_ok=True)
            skill.write_text(_skill_vorlage(), encoding="utf-8")
            angelegt.append(skill)
        for rel in ["raw/youtube", "raw/kurse", "raw/pdf", "assets", "compendia", "inbox"]:
            pfad = self.root / rel
            if not pfad.exists():
                pfad.mkdir(parents=True)
                (pfad / ".gitkeep").touch()
                angelegt.append(pfad)
        readme = self.root / "README.md"
        if not readme.exists():
            readme.write_text(_BASIS_README, encoding="utf-8")
            angelegt.append(readme)
        gitignore = self.root / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "# Ablagefach fuer noch nicht einsortierte Dateien\n"
                "inbox/*\n!inbox/.gitkeep\n\n.DS_Store\n",
                encoding="utf-8",
            )
            angelegt.append(gitignore)
        return angelegt

    def pruefe(self) -> None:
        if not self.root.is_dir():
            raise FileNotFoundError(
                f"Ablage {self.root} existiert nicht. Erst 'wissen init' ausfuehren."
            )

    # -- Pfade -----------------------------------------------------------

    def dokument_pfad(self, meta: dict) -> Path:
        typ = meta["typ"]
        ordner = self.root / ROH_ORDNER[typ]
        slug = schema.slugify(meta.get("titel") or meta["id"])
        if typ == "youtube":
            kennung = str(meta["id"]).split(":", 1)[-1]
            return ordner / f"{kennung}--{slug}.md"
        kurs = schema.slugify(meta.get("kurs") or "ohne-kurs")
        lektion = meta.get("lektion")
        praefix = f"{int(lektion):02d}--" if lektion is not None else ""
        return ordner / kurs / f"{praefix}{slug}.md"

    def asset_ordner(self, quellen_id: str) -> Path:
        ordner = self.root / "assets" / schema.slugify(quellen_id)
        ordner.mkdir(parents=True, exist_ok=True)
        return ordner

    def rel(self, pfad: Path) -> str:
        """Pfad relativ zur Wurzel der Ablage, mit '/' als Trenner."""
        return Path(pfad).resolve().relative_to(self.root).as_posix()

    def rel_von(self, ziel: Path, quelle: Path) -> str:
        """Pfad von `quelle` (Datei) aus zu `ziel` -- fuer Markdown-Links."""
        return Path(
            os.path.relpath(Path(ziel).resolve(), Path(quelle).resolve().parent)
        ).as_posix()

    # -- Lesen und Schreiben ---------------------------------------------

    def schreibe(self, meta: dict, body: str, pfad: Path | None = None) -> Path:
        pfad = pfad or self.dokument_pfad(meta)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(schema.dokument(meta, body), encoding="utf-8")
        return pfad

    def finde_nach_id(self, quellen_id: str) -> Path | None:
        for pfad, meta, _ in self.dokumente():
            if meta.get("id") == quellen_id:
                return pfad
        return None

    def dokumente(self) -> Iterator[tuple[Path, dict, str]]:
        """Alle Rohdokumente mit Frontmatter und Fliesstext."""
        for pfad in sorted((self.root / "raw").rglob("*.md")):
            text = pfad.read_text(encoding="utf-8")
            meta, body = schema.frontmatter_load(text)
            if meta:
                yield pfad, meta, body

    def kopiere_original(self, quelle: Path, meta: dict) -> str:
        """Legt eine Originaldatei (z.B. das PDF) neben ihr Dokument."""
        ziel = self.dokument_pfad(meta).with_suffix(Path(quelle).suffix.lower())
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(quelle, ziel)
        return self.rel(ziel)

    # -- Index -----------------------------------------------------------

    def baue_index(self) -> Path:
        """Erzeugt INDEX.md neu aus den Frontmattern."""
        nach_typ: dict[str, list[tuple[Path, dict]]] = {}
        for pfad, meta, _ in self.dokumente():
            nach_typ.setdefault(meta.get("typ") or "sonstiges", []).append((pfad, meta))

        zeilen = [
            "# Index der Wissensbasis",
            "",
            "Maschinell erzeugt mit `wissen index` -- nicht von Hand bearbeiten.",
            "",
        ]
        gesamt = sum(len(v) for v in nach_typ.values())
        kompendien = sorted((self.root / "compendia").glob("*.md"))
        zeilen.append(
            f"{_anzahl(gesamt, 'Quelle', 'Quellen')}, "
            f"{_anzahl(len(kompendien), 'Kompendium', 'Kompendien')}, "
            f"Stand {schema.heute()}."
        )
        zeilen.append("")

        if kompendien:
            zeilen += ["## Kompendien", ""]
            for pfad in kompendien:
                meta, _ = schema.frontmatter_load(pfad.read_text(encoding="utf-8"))
                titel = meta.get("titel") or pfad.stem
                zeilen.append(f"- [{titel}]({self.rel(pfad)})")
            zeilen.append("")

        if "youtube" in nach_typ:
            zeilen += ["## YouTube-Tutorials", ""]
            for pfad, meta in sorted(nach_typ["youtube"], key=_sortierschluessel):
                zeilen.append(f"- {_eintrag(self, pfad, meta)}")
            zeilen.append("")

        for typ, titel in (("kurs", "Online-Kurse"), ("pdf", "PDF-Kurse und Trainingseinheiten")):
            if typ not in nach_typ:
                continue
            zeilen += [f"## {titel}", ""]
            nach_kurs: dict[str, list[tuple[Path, dict]]] = {}
            for pfad, meta in nach_typ[typ]:
                nach_kurs.setdefault(meta.get("kurs") or "ohne-kurs", []).append((pfad, meta))
            for kurs in sorted(nach_kurs):
                zeilen += [f"### {kurs}", ""]
                for pfad, meta in sorted(nach_kurs[kurs], key=_sortierschluessel):
                    zeilen.append(f"- {_eintrag(self, pfad, meta)}")
                zeilen.append("")

        ziel = self.root / "INDEX.md"
        ziel.write_text("\n".join(zeilen).rstrip() + "\n", encoding="utf-8")
        return ziel


def _skill_vorlage() -> str:
    """Die Kompendium-Skill, die mit der Wissensbasis mitwandert.

    Sie liegt in der Wissensbasis und nicht im Werkzeug, damit Claude sie
    dort findet, wo die Kompendien entstehen.
    """
    from importlib import resources

    return (
        resources.files("wissen.vorlagen")
        .joinpath("kompendium-skill.md")
        .read_text(encoding="utf-8")
    )


def _anzahl(wert: int, einzahl: str, mehrzahl: str) -> str:
    return f"{wert} {einzahl if wert == 1 else mehrzahl}"


def _sortierschluessel(paar: tuple[Path, dict]):
    pfad, meta = paar
    lektion = meta.get("lektion")
    return (0, int(lektion)) if lektion is not None else (1, 0), pfad.name


def _eintrag(ablage: Ablage, pfad: Path, meta: dict) -> str:
    titel = meta.get("titel") or pfad.stem
    teile = [f"[{titel}]({ablage.rel(pfad)})"]
    zusatz = []
    if meta.get("lektion") is not None:
        zusatz.append(f"Lektion {meta['lektion']}")
    if meta.get("dauer"):
        zusatz.append(f"Dauer {schema.sekunden_zu_zeit(meta['dauer'])}")
    if meta.get("seiten"):
        zusatz.append(_anzahl(meta["seiten"], "Seite", "Seiten"))
    if meta.get("assets"):
        zusatz.append(_anzahl(len(meta["assets"]), "Screenshot", "Screenshots"))
    if meta.get("braucht_ocr"):
        zusatz.append("**OCR nötig**")
    if meta.get("abgerufen"):
        zusatz.append(f"abgerufen {meta['abgerufen']}")
    if zusatz:
        teile.append("-- " + ", ".join(zusatz))

    # Bei PDFs ist `quelle` nur ein Dateiname -- dann auf das mitgelegte
    # Original verlinken statt einen toten Link zu bauen.
    quelle = meta.get("quelle") or ""
    if quelle.startswith(("http://", "https://")):
        teile.append(f"([Quelle]({quelle}))")
    elif meta.get("original"):
        teile.append(f"([Original]({meta['original']}))")
    elif quelle:
        teile.append(f"(aus `{quelle}`)")
    return " ".join(teile)
