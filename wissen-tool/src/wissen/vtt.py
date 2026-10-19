"""Untertitel einlesen und in lesbaren Fliesstext mit Zeitmarken wandeln.

YouTubes automatische Untertitel sind rollend: jede Kachel wiederholt die
letzte Zeile der vorigen und haengt neue Woerter an. Unbehandelt kommt dabei
jeder Satz zwei- bis dreimal im Transkript vor. Darum der Dedup-Schritt.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

_ZEITZEILE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{1,2}:\d{2}[.,]\d{3})\s*-->\s*"
    r"(?P<ende>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{1,2}:\d{2}[.,]\d{3})"
)
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Kachel:
    """Ein Untertitel-Segment."""

    start: float
    ende: float
    text: str


def _zeit(wert: str) -> float:
    wert = wert.replace(",", ".")
    teile = wert.split(":")
    sekunden = 0.0
    for teil in teile:
        sekunden = sekunden * 60 + float(teil)
    return sekunden


def parse_vtt(inhalt: str) -> list[Kachel]:
    """Liest WebVTT (und SRT, dessen Zeitformat nur Komma statt Punkt nutzt)."""
    kacheln: list[Kachel] = []
    zeilen = inhalt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nr = 0
    while nr < len(zeilen):
        treffer = _ZEITZEILE.search(zeilen[nr])
        if not treffer:
            nr += 1
            continue
        start = _zeit(treffer.group("start"))
        ende = _zeit(treffer.group("ende"))
        nr += 1
        rohtext: list[str] = []
        while nr < len(zeilen) and zeilen[nr].strip() and not _ZEITZEILE.search(zeilen[nr]):
            rohtext.append(zeilen[nr])
            nr += 1
        text = " ".join(rohtext)
        text = html.unescape(_TAGS.sub("", text))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            kacheln.append(Kachel(start, ende, text))
    return kacheln


def parse_json3(inhalt: str) -> list[Kachel]:
    """Liest YouTubes json3-Format, das bei Auto-Untertiteln oft statt VTT kommt."""
    daten = json.loads(inhalt)
    kacheln: list[Kachel] = []
    for ereignis in daten.get("events", []):
        segmente = ereignis.get("segs")
        if not segmente:
            continue
        text = "".join(seg.get("utf8", "") for seg in segmente)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        start = ereignis.get("tStartMs", 0) / 1000.0
        dauer = ereignis.get("dDurationMs", 0) / 1000.0
        kacheln.append(Kachel(start, start + dauer, text))
    return kacheln


def parse(inhalt: str, format_hinweis: str | None = None) -> list[Kachel]:
    """Erkennt das Format selbst, wenn kein Hinweis mitkommt."""
    if format_hinweis == "json3" or inhalt.lstrip().startswith("{"):
        return parse_json3(inhalt)
    return parse_vtt(inhalt)


def entdoppeln(kacheln: list[Kachel]) -> list[Kachel]:
    """Entfernt die Wiederholungen der rollenden Untertitel.

    Gearbeitet wird zeilenweise: eine Zeile, die der zuletzt uebernommenen
    gleicht oder in ihr komplett enthalten ist, fliegt raus. So bleibt vom
    rollenden Fenster genau der jeweils neue Teil uebrig.
    """
    ergebnis: list[Kachel] = []
    zuletzt = ""
    for kachel in kacheln:
        text = kachel.text.strip()
        if not text:
            continue
        if text == zuletzt:
            continue
        if zuletzt and text in zuletzt:
            continue
        if zuletzt and zuletzt in text:
            # Das Fenster ist gewachsen: nur den Zuwachs behalten und die
            # vorige Kachel auf die neue Endzeit verlaengern.
            zuwachs = text[len(zuletzt):].strip()
            if not zuwachs:
                continue
            if ergebnis:
                ergebnis[-1] = Kachel(ergebnis[-1].start, kachel.ende, text)
                zuletzt = text
                continue
            text = zuwachs
        ergebnis.append(Kachel(kachel.start, kachel.ende, text))
        zuletzt = text
    return ergebnis


def zu_text(kacheln: list[Kachel], marke_alle: int = 30) -> str:
    """Baut Fliesstext mit Zeitmarken im Abstand von `marke_alle` Sekunden.

    Die Marken sind der Ankerpunkt fuer alles Weitere: Claude zitiert daraus
    und leitet daraus die Zeitpunkte fuer Screenshots ab.
    """
    kacheln = entdoppeln(kacheln)
    if not kacheln:
        return ""
    from .schema import sekunden_zu_zeit

    absaetze: list[str] = []
    puffer: list[str] = []
    block_start = kacheln[0].start
    for kachel in kacheln:
        if puffer and kachel.start - block_start >= marke_alle:
            absaetze.append(f"[{sekunden_zu_zeit(block_start)}] " + " ".join(puffer))
            puffer = []
            block_start = kachel.start
        puffer.append(kachel.text)
    if puffer:
        absaetze.append(f"[{sekunden_zu_zeit(block_start)}] " + " ".join(puffer))
    return "\n\n".join(absaetze)
