"""Metadaten-Schema der Wissensbasis: Slugs, IDs, Frontmatter.

Jedes Dokument in der Wissensbasis ist eine Markdown-Datei mit YAML-Frontmatter.
Das Frontmatter ist die einzige Stelle, aus der Indizes und Kompendien gebaut
werden -- der Fliesstext bleibt unangetastete Rohform.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
import unicodedata

import yaml

# Umlaute vor dem Normalisieren ersetzen, sonst fallen sie zu "a"/"o"/"u"
# zusammen und "Loeschen"/"Laeschen" werden ununterscheidbar.
_ERSATZ = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}

LIZENZ_HINWEIS = "Gespeicherte Kopie fuer persoenliche Lernzwecke."

#: Reihenfolge der Frontmatter-Felder, damit Diffs lesbar bleiben.
FELDER = [
    "id", "typ", "titel", "quelle", "abgerufen", "kurs", "lektion",
    "sprache", "dauer", "seiten", "tags", "assets", "original",
    "lizenz_hinweis",
]


def slugify(text: str, maxlen: int = 60) -> str:
    """Macht aus beliebigem Text einen dateinamentauglichen Slug."""
    for zeichen, ersatz in _ERSATZ.items():
        text = text.replace(zeichen, ersatz)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if len(text) > maxlen:
        text = text[:maxlen].rstrip("-")
    return text or "ohne-titel"


def kurz_hash(wert: str, laenge: int = 10) -> str:
    """Stabile Kurzkennung -- gleiche Quelle ergibt immer dieselbe ID."""
    return hashlib.sha256(wert.encode("utf-8")).hexdigest()[:laenge]


def datei_hash(pfad, laenge: int = 10) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:laenge]


def heute() -> str:
    return _dt.date.today().isoformat()


def zeit_zu_sekunden(wert: str) -> int:
    """'4:12' -> 252, '1:02:03' -> 3723, '252' -> 252."""
    teile = [t.strip() for t in str(wert).split(":")]
    if not all(re.fullmatch(r"\d+(\.\d+)?", t) for t in teile) or len(teile) > 3:
        raise ValueError(f"Unlesbare Zeitangabe: {wert!r} (erwartet mm:ss oder hh:mm:ss)")
    sekunden = 0.0
    for teil in teile:
        sekunden = sekunden * 60 + float(teil)
    return int(sekunden)


def sekunden_zu_zeit(sekunden: float) -> str:
    """252 -> '04:12', 3723 -> '01:02:03'."""
    sekunden = int(sekunden)
    stunden, rest = divmod(sekunden, 3600)
    minuten, sek = divmod(rest, 60)
    if stunden:
        return f"{stunden:02d}:{minuten:02d}:{sek:02d}"
    return f"{minuten:02d}:{sek:02d}"


def zeit_fuer_dateiname(sekunden: float) -> str:
    """Wie sekunden_zu_zeit, aber mit '-' statt ':' fuer Dateinamen."""
    return sekunden_zu_zeit(sekunden).replace(":", "-")


def neues_frontmatter(**werte) -> dict:
    """Legt ein Frontmatter mit Standardwerten an."""
    meta = {
        "id": None,
        "typ": None,
        "titel": None,
        "quelle": None,
        "abgerufen": heute(),
        "kurs": None,
        "lektion": None,
        "sprache": None,
        "tags": [],
        "assets": [],
        "lizenz_hinweis": LIZENZ_HINWEIS,
    }
    meta.update(werte)
    return meta


def frontmatter_dump(meta: dict) -> str:
    """Serialisiert Frontmatter in stabiler Feldreihenfolge."""
    geordnet = {f: meta[f] for f in FELDER if f in meta and meta[f] is not None}
    # Felder, die das Schema noch nicht kennt, hinten anhaengen statt verlieren.
    for key, wert in meta.items():
        if key not in geordnet and wert is not None:
            geordnet[key] = wert
    rumpf = yaml.safe_dump(
        geordnet, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    return f"---\n{rumpf}---\n"


def frontmatter_load(text: str) -> tuple[dict, str]:
    """Trennt Frontmatter und Fliesstext. Ohne Frontmatter: ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    zeilen = text.split("\n")
    for nr in range(1, len(zeilen)):
        if zeilen[nr].strip() == "---":
            kopf = "\n".join(zeilen[1:nr])
            rest = "\n".join(zeilen[nr + 1:])
            meta = yaml.safe_load(kopf) or {}
            if not isinstance(meta, dict):
                return {}, text
            return meta, rest.lstrip("\n")
    return {}, text


def dokument(meta: dict, body: str) -> str:
    """Baut die komplette Markdown-Datei."""
    return frontmatter_dump(meta) + "\n" + body.strip() + "\n"
