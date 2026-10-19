"""PDF-Kurse und Trainingseinheiten einlesen und einsortieren.

Der Text bekommt Seitenmarken `[Seite n]` -- dasselbe Prinzip wie die
Zeitmarken im Transkript, damit ein Kompendium praezise zurueckverweisen kann.
Das Original-PDF wird neben das Textdokument gelegt.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import schema
from .config import Konfig
from .store import Ablage

#: Unter so vielen Zeichen pro Seite gehen wir von einem Scan ohne Textlayer aus.
MIN_ZEICHEN_PRO_SEITE = 40

_GENERISCH = re.compile(
    r"^(untitled|unbenannt|microsoft word|dokument\d*|pr(ae|ä)sentation\d*)",
    re.IGNORECASE,
)


class PdfFehler(RuntimeError):
    pass


def _reader(pfad: Path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - Umgebungsproblem
        raise PdfFehler("pypdf ist nicht installiert. Im Projektordner: pip install -e .") from exc
    return PdfReader(str(pfad))


def _titel(reader, seitentexte: list[str], pfad: Path) -> str:
    """Titel aus Metadaten, sonst erste sinnvolle Zeile, sonst Dateiname."""
    with_meta = None
    try:
        with_meta = (reader.metadata or {}).get("/Title")
    except Exception:
        pass
    if with_meta:
        kandidat = str(with_meta).strip()
        if len(kandidat) > 3 and not _GENERISCH.match(kandidat):
            return kandidat
    if seitentexte:
        for zeile in seitentexte[0].splitlines():
            zeile = zeile.strip()
            if 5 < len(zeile) < 120:
                return zeile
    return pfad.stem.replace("_", " ").strip()


def lade_pdf(
    cfg: Konfig,
    ablage: Ablage,
    pfad: Path,
    *,
    kurs: str,
    lektion: int | None = None,
    titel: str | None = None,
    tags: list[str] | None = None,
) -> tuple[Path, dict]:
    """Liest ein PDF aus und legt Text plus Original ab."""
    pfad = Path(pfad).expanduser().resolve()
    if not pfad.is_file():
        raise PdfFehler(f"{pfad} ist keine Datei.")

    reader = _reader(pfad)
    seitentexte: list[str] = []
    for seite in reader.pages:
        try:
            seitentexte.append((seite.extract_text() or "").strip())
        except Exception as exc:
            seitentexte.append(f"_(Seite nicht lesbar: {exc})_")

    zeichen = sum(len(t) for t in seitentexte)
    braucht_ocr = bool(seitentexte) and zeichen / len(seitentexte) < MIN_ZEICHEN_PRO_SEITE

    meta = schema.neues_frontmatter(
        id=f"pdf:{schema.datei_hash(pfad)}",
        typ="pdf",
        titel=titel or _titel(reader, seitentexte, pfad),
        quelle=pfad.name,
        kurs=schema.slugify(kurs),
        lektion=lektion,
        seiten=len(seitentexte),
        tags=tags or [],
    )
    meta["original"] = ablage.kopiere_original(pfad, meta)
    if braucht_ocr:
        meta["braucht_ocr"] = True

    teile = [f"# {meta['titel']}", "", f"Originaldatei: `{pfad.name}`",
             f"Seiten: {len(seitentexte)}", ""]
    if braucht_ocr:
        teile += [
            "> **Kein Textlayer.** Das PDF ist wahrscheinlich ein Scan. Mit OCR",
            "> nachbearbeiten und erneut einlesen:",
            "> `ocrmypdf -l deu --skip-text alt.pdf neu.pdf`",
            "",
        ]
    teile += ["## Inhalt", ""]
    for nr, text in enumerate(seitentexte, start=1):
        teile += [f"[Seite {nr}]", "", text or "_(leer)_", ""]

    ziel = ablage.schreibe(meta, "\n".join(teile))
    return ziel, meta


def lade_ordner(
    cfg: Konfig,
    ablage: Ablage,
    ordner: Path,
    *,
    kurs: str,
    tags: list[str] | None = None,
    nummerieren: bool = True,
) -> list[tuple[Path, dict]]:
    """Liest alle PDFs eines Ordners in alphabetischer Reihenfolge ein.

    Die Reihenfolge wird als Lektionsnummer festgehalten -- bei Dateinamen wie
    `01 Einfuehrung.pdf` ergibt das direkt die richtige Kursgliederung.
    """
    ordner = Path(ordner).expanduser().resolve()
    dateien = sorted(
        (p for p in ordner.rglob("*") if p.suffix.lower() == ".pdf"),
        key=lambda p: (len(p.relative_to(ordner).parts), str(p).lower()),
    )
    if not dateien:
        raise PdfFehler(f"In {ordner} liegen keine PDF-Dateien.")

    ergebnisse: list[tuple[Path, dict]] = []
    for nr, datei in enumerate(dateien, start=1):
        print(f"[{nr}/{len(dateien)}] {datei.name}")
        try:
            ergebnisse.append(
                lade_pdf(
                    cfg, ablage, datei, kurs=kurs,
                    lektion=nr if nummerieren else None, tags=tags,
                )
            )
        except Exception as exc:
            print(f"    uebersprungen: {exc}")
    return ergebnisse
