"""Dateikopf und Hilfsfunktionen.

Der Kopf folgt dem Format aus ANLEITUNG.md, Ablauf C Schritt 2:
Titel, Kanal, URL, Erfassungsdatum, Abdeckung. Kein YAML -- die Dateien in
`eingang/` sind Rohmaterial im selben Stil wie die bereits vorhandenen.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
import unicodedata

# Umlaute vor dem Normalisieren ersetzen, sonst fallen sie zu "a"/"o"/"u"
# zusammen und "Loeschen"/"Laeschen" werden ununterscheidbar.
_ERSATZ = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}

ROHMATERIAL_HINWEIS = "Rohmaterial — wird nicht ins Buch zitiert."

#: Reihenfolge der Kopffelder.
KOPFFELDER = [
    "Titel", "Kanal", "Plattform", "Kurs", "Modul", "Lektion",
    "URL", "Datei", "Veröffentlicht", "Erfassungsdatum", "Abdeckung",
    "Screenshots", "Original",
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


# -- Zeitangaben ---------------------------------------------------------


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
    """Gepolsterte Form fuer Transkript-Marken: 252 -> '04:12'."""
    sekunden = int(sekunden)
    stunden, rest = divmod(sekunden, 3600)
    minuten, sek = divmod(rest, 60)
    if stunden:
        return f"{stunden:02d}:{minuten:02d}:{sek:02d}"
    return f"{minuten:02d}:{sek:02d}"


def zeit_kurz(sekunden: float) -> str:
    """Form fuer die Abdeckungszeile: 0 -> '0:00', 777 -> '12:57'."""
    sekunden = int(sekunden)
    stunden, rest = divmod(sekunden, 3600)
    minuten, sek = divmod(rest, 60)
    if stunden:
        return f"{stunden}:{minuten:02d}:{sek:02d}"
    return f"{minuten}:{sek:02d}"


def zeit_fuer_dateiname(sekunden: float) -> str:
    """Wie sekunden_zu_zeit, aber mit '-' statt ':' fuer Dateinamen."""
    return sekunden_zu_zeit(sekunden).replace(":", "-")


def abdeckung(letzte_marke: float, gesamtlaenge: float | None, automatisch: bool) -> str:
    """Baut die Abdeckungszeile: 'Transkript 0:00–12:57 von 13:03 (Auto-Captions)'."""
    quelle = "Auto-Captions" if automatisch else "Untertitel vom Kanal"
    if gesamtlaenge:
        return (
            f"Transkript 0:00–{zeit_kurz(letzte_marke)} "
            f"von {zeit_kurz(gesamtlaenge)} ({quelle})"
        )
    return f"Transkript 0:00–{zeit_kurz(letzte_marke)} ({quelle})"


def abdeckung_luecke(letzte_marke: float, gesamtlaenge: float | None) -> float | None:
    """Sekunden zwischen letzter Zeitmarke und Videoende.

    ANLEITUNG, Ablauf C Schritt 1: der letzte Timestamp muss bis etwa eine
    Minute an die Videolaenge heranreichen, sonst ist das Transkript
    unvollstaendig.
    """
    if not gesamtlaenge:
        return None
    return max(0.0, gesamtlaenge - letzte_marke)


# -- Dateikopf -----------------------------------------------------------


def kopf_bauen(felder: dict, hinweis: str | None = ROHMATERIAL_HINWEIS) -> str:
    """Baut den Markdown-Kopf in fester Feldreihenfolge."""
    titel = felder.get("Titel") or "Ohne Titel"
    zeilen = [f"# {titel}", ""]
    for name in KOPFFELDER:
        if name == "Titel":
            continue
        wert = felder.get(name)
        if wert is None or wert == "" or wert == []:
            continue
        if isinstance(wert, list):
            wert = ", ".join(str(w) for w in wert)
        zeilen.append(f"- {name}: {wert}")
    # Felder, die das Schema noch nicht kennt, hinten anhaengen statt verlieren.
    for name, wert in felder.items():
        if name not in KOPFFELDER and wert not in (None, "", []):
            zeilen.append(f"- {name}: {wert}")
    if hinweis:
        zeilen += ["", f"> {hinweis}"]
    zeilen += ["", "---", "", ""]
    return "\n".join(zeilen)


def kopf_lesen(text: str) -> dict:
    """Liest den Kopf einer Rohmaterialdatei zurueck.

    Gelesen wird bis zur Trennlinie `---`; danach beginnt das Transkript und
    dort koennen Zeilen stehen, die wie Kopffelder aussehen.
    """
    felder: dict = {}
    for zeile in text.split("\n"):
        blank = zeile.strip()
        if blank == "---":
            break
        if blank.startswith("# "):
            felder["Titel"] = blank[2:].strip()
            continue
        treffer = re.match(r"^-\s+([^:]{1,40}):\s*(.+)$", blank)
        if treffer:
            felder[treffer.group(1).strip()] = treffer.group(2).strip()
    return felder


def dokument(felder: dict, body: str, hinweis: str | None = ROHMATERIAL_HINWEIS) -> str:
    """Baut die komplette Markdown-Datei."""
    return kopf_bauen(felder, hinweis) + body.strip() + "\n"
