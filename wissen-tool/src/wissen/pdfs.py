"""PDF-Kurse und Trainingseinheiten einlesen.

Der Text bekommt Seitenmarken `[Seite n]` -- dasselbe Prinzip wie die
Zeitmarken im Transkript, damit ein Beleg nach Regel 2 der Genre-Rezepte
auch bei PDF-Quellen praezise zurueckverweisen kann.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import schema
from .config import Konfig
from .store import Ablage

#: Eine Seite mit weniger Zeichen gilt als leer (Scan, Bildseite, Trennblatt).
MIN_ZEICHEN_PRO_SEITE = 10

#: Ab diesem Anteil leerer Seiten gilt das PDF als Scan ohne Textlayer.
#: Nicht am Durchschnitt gemessen -- sonst gilt ein kurzes Titel- oder
#: Uebungsblatt faelschlich als Scan, obwohl sein Text sauber auslesbar ist.
MAX_LEERE_SEITEN = 0.5

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
    aus_meta = None
    try:
        aus_meta = (reader.metadata or {}).get("/Title")
    except Exception:
        pass
    if aus_meta:
        kandidat = str(aus_meta).strip()
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
    praefix: str,
    kurs: str | None = None,
    lektion: str | None = None,
    titel: str | None = None,
) -> tuple[Path, dict, bool]:
    """Liest ein PDF aus und legt Text plus Original im Eingang ab."""
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

    leere = sum(1 for t in seitentexte if len(t) < MIN_ZEICHEN_PRO_SEITE)
    braucht_ocr = (
        bool(seitentexte) and leere / len(seitentexte) >= MAX_LEERE_SEITEN
    )

    echter_titel = titel or _titel(reader, seitentexte, pfad)
    kennung = schema.slugify(echter_titel, 50)
    ziel = ablage.eingang_pfad(praefix, kennung)

    original = ablage.kopiere_original(
        pfad, ablage.media_ordner(kennung) / pfad.name
    )

    felder = {
        "Titel": echter_titel,
        "Kurs": kurs,
        "Lektion": lektion,
        "Datei": pfad.name,
        "Erfassungsdatum": schema.heute(),
        "Abdeckung": (
            f"PDF-Text, {len(seitentexte)} "
            f"{'Seite' if len(seitentexte) == 1 else 'Seiten'}"
            + (
                f" — {leere} davon ohne Text, OCR nötig" if braucht_ocr
                else f" ({leere} ohne Text)" if leere else ""
            )
        ),
        "Original": ablage.rel(original),
    }

    teile = []
    if braucht_ocr:
        teile += [
            "> **Kein Textlayer.** Das PDF ist wahrscheinlich ein Scan. Mit OCR",
            "> nachbearbeiten und erneut einlesen:",
            "> `ocrmypdf -l deu --skip-text alt.pdf neu.pdf`",
            "",
        ]
    for nr, text in enumerate(seitentexte, start=1):
        teile += [f"[Seite {nr}]", "", text or "_(leer)_", ""]

    ablage.schreibe(felder, "\n".join(teile), ziel)
    return ziel, felder, braucht_ocr


def lade_ordner(
    cfg: Konfig,
    ablage: Ablage,
    ordner: Path,
    *,
    praefix: str,
    kurs: str | None = None,
) -> list[tuple[Path, dict, bool]]:
    """Liest alle PDFs eines Ordners in alphabetischer Reihenfolge ein.

    Die Position wird als Lektionsnummer festgehalten -- bei Dateinamen wie
    `01 Einfuehrung.pdf` ergibt das direkt die richtige Kursgliederung.
    """
    ordner = Path(ordner).expanduser().resolve()
    dateien = sorted(
        (p for p in ordner.rglob("*") if p.suffix.lower() == ".pdf"),
        key=lambda p: (len(p.relative_to(ordner).parts), str(p).lower()),
    )
    if not dateien:
        raise PdfFehler(f"In {ordner} liegen keine PDF-Dateien.")

    ergebnisse: list[tuple[Path, dict, bool]] = []
    for nr, datei in enumerate(dateien, start=1):
        print(f"[{nr}/{len(dateien)}] {datei.name}")
        try:
            ergebnisse.append(
                lade_pdf(
                    cfg, ablage, datei, praefix=praefix, kurs=kurs,
                    lektion=str(nr),
                )
            )
        except Exception as exc:
            print(f"    uebersprungen: {exc}")
    return ergebnisse
