"""Die Ablage -- schreibt in den vorhandenen `buch/`-Ordner.

Das Werkzeug legt keine eigene Struktur an. Es bedient die Stellen, die
ANLEITUNG.md schon vorsieht:

    eingang/                      Sammelstelle, noch nicht eingearbeitet
    eingang/<praefix>_<id>.md     Rohtranskript (Ablauf C Schritt 2)
    eingang/media/<id>/           Screenshots zu offenen Fragen (Regel 5)
    eingang/verarbeitet/          nach dem Einarbeiten (Ablauf C Schritt 6)

Alles darueber -- Kursdetaildateien, Teil I-V, Konzeptregister, quellen.md --
bleibt Handarbeit nach ANLEITUNG.md. Das Werkzeug schreibt dort nicht hinein.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterator

from . import schema


class Ablage:
    """Zugriff auf den `buch/`-Ordner."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()

    @property
    def eingang(self) -> Path:
        return self.root / "eingang"

    @property
    def verarbeitet(self) -> Path:
        return self.eingang / "verarbeitet"

    @property
    def media(self) -> Path:
        return self.eingang / "media"

    # -- Einrichtung -----------------------------------------------------

    def init(self) -> list[Path]:
        """Legt nur die Eingangsordner an, falls sie fehlen."""
        angelegt: list[Path] = []
        for pfad in (self.eingang, self.verarbeitet, self.media):
            if not pfad.exists():
                pfad.mkdir(parents=True)
                angelegt.append(pfad)
        return angelegt

    def pruefe(self) -> None:
        if not self.root.is_dir():
            raise FileNotFoundError(
                f"Ablage {self.root} existiert nicht. In wissen.toml unter "
                "[ablage] pfad den buch/-Ordner eintragen."
            )
        self.init()

    def warnungen(self) -> list[str]:
        """Hinweise, wenn die Ablage nicht nach dem buch/-Ordner aussieht."""
        meldungen = []
        if not (self.root / "ANLEITUNG.md").is_file():
            meldungen.append(
                f"In {self.root} liegt keine ANLEITUNG.md -- ist das wirklich "
                "der buch/-Ordner?"
            )
        return meldungen

    # -- Pfade -----------------------------------------------------------

    def eingang_pfad(self, praefix: str, kennung: str) -> Path:
        """`eingang/<praefix>_<kennung>.md`, wie in ANLEITUNG.md Ablauf C."""
        return self.eingang / f"{schema.slugify(praefix, 40)}_{kennung}.md"

    def media_ordner(self, kennung: str) -> Path:
        ordner = self.media / schema.slugify(kennung, 40)
        ordner.mkdir(parents=True, exist_ok=True)
        return ordner

    def rel(self, pfad: Path) -> str:
        """Pfad relativ zur Wurzel der Ablage, mit '/' als Trenner."""
        return Path(pfad).resolve().relative_to(self.root).as_posix()

    def rel_von(self, ziel: Path, quelle: Path) -> str:
        """Pfad von `quelle` (Datei) aus zu `ziel` -- fuer Markdown-Links."""
        import os

        return Path(
            os.path.relpath(Path(ziel).resolve(), Path(quelle).resolve().parent)
        ).as_posix()

    # -- Lesen und Schreiben ---------------------------------------------

    def schreibe(self, felder: dict, body: str, pfad: Path) -> Path:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(schema.dokument(felder, body), encoding="utf-8")
        return pfad

    def kopiere_original(self, quelle: Path, ziel: Path) -> Path:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(quelle, ziel)
        return ziel

    def dokumente(self, auch_verarbeitet: bool = False) -> Iterator[tuple[Path, dict]]:
        """Rohmaterialdateien im Eingang, mit gelesenem Kopf."""
        ordner = [self.eingang]
        if auch_verarbeitet:
            ordner.append(self.verarbeitet)
        for basis in ordner:
            if not basis.is_dir():
                continue
            for pfad in sorted(basis.glob("*.md")):
                felder = schema.kopf_lesen(pfad.read_text(encoding="utf-8"))
                yield pfad, felder

    def finde_nach_url(self, url: str) -> Path | None:
        for pfad, felder in self.dokumente(auch_verarbeitet=True):
            if (felder.get("URL") or "").strip().rstrip("/") == url.strip().rstrip("/"):
                return pfad
        return None

    def verschiebe_verarbeitet(self, pfad: Path) -> Path:
        """Ablauf C Schritt 6: Eingangsdatei nach `eingang/verarbeitet/`."""
        pfad = Path(pfad).resolve()
        if pfad.parent == self.verarbeitet:
            return pfad
        if pfad.parent != self.eingang:
            raise ValueError(f"{pfad} liegt nicht in {self.eingang}.")
        self.verarbeitet.mkdir(parents=True, exist_ok=True)
        ziel = self.verarbeitet / pfad.name
        if ziel.exists():
            raise FileExistsError(f"{self.rel(ziel)} gibt es schon.")
        # Die Datei rutscht eine Ebene tiefer -- relative Bildlinks mitziehen,
        # sonst zeigen die Screenshots ins Leere.
        text = pfad.read_text(encoding="utf-8")
        gezogen = text.replace("](media/", "](../media/")
        pfad.rename(ziel)
        if gezogen != text:
            ziel.write_text(gezogen, encoding="utf-8")
        return ziel

    # -- quellen.md ------------------------------------------------------

    def quellen_eintrag(self, pfad: Path, felder: dict) -> str:
        """Entwurf fuer den Eintrag unter „Einzelquellen" in `quellen.md`.

        Nur ein Vorschlag zum Hineinkopieren -- `quellen.md` selbst wird vom
        Werkzeug nicht angefasst.
        """
        teile = [f"- „{felder.get('Titel', 'Ohne Titel')}“"]
        kopf = []
        if felder.get("Kanal"):
            kopf.append(felder["Kanal"])
        quelle = (felder.get("URL") or "").strip()
        if quelle.startswith(("http://", "https://")):
            kopf.append(f"<{quelle}>")
        elif felder.get("Datei"):
            # Bei PDFs gibt es keine URL, nur einen Dateinamen -- nicht als
            # Link ausgeben, sonst entsteht ein toter Verweis.
            kopf.append(f"Datei `{felder['Datei']}`")
        if felder.get("Veröffentlicht"):
            kopf.append(f"veröffentlicht {felder['Veröffentlicht']}")
        if kopf:
            teile.append(" — " + ", ".join(kopf))
        abdeckung = (felder.get("Abdeckung") or "").strip()
        if abdeckung:
            teile.append(f", {abdeckung}")
        bezeichnung = "Rohtranskript" if abdeckung.startswith("Transkript") else "Rohtext"
        teile.append(f"; {bezeichnung}: `{self.rel(pfad)}`")
        return "".join(teile)
