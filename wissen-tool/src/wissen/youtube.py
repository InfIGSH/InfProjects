"""YouTube: Transkript holen, Einzelbilder an bestimmten Zeitpunkten ziehen.

Beides laeuft ohne API-Key. Das Transkript kommt aus der Untertitelspur
(auch der automatisch erzeugten), die Bilder zieht ffmpeg direkt aus dem
Videostream -- es wird nur der angefragte Augenblick geladen, nicht das Video.

Die Abdeckung wird gegen die Videolaenge geprueft (ANLEITUNG.md, Ablauf C
Schritt 1): reicht die letzte Zeitmarke nicht bis etwa eine Minute an das
Ende, ist das Transkript unvollstaendig und das Werkzeug sagt es.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import schema, vtt
from .config import Konfig
from .store import Ablage

#: Reihenfolge, in der Untertitelformate bevorzugt werden.
FORMAT_VORZUG = ["vtt", "json3", "srv3", "srv1", "ttml", "srt"]

_ZEITMARKE = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]")


class YoutubeFehler(RuntimeError):
    pass


@dataclass
class Ergebnis:
    pfad: Path
    felder: dict
    luecke: float | None
    vollstaendig: bool


def _ydl(extra: dict | None = None):
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:  # pragma: no cover - Umgebungsproblem
        raise YoutubeFehler(
            "yt-dlp ist nicht installiert. Im Projektordner: pip install -e ."
        ) from exc
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    opts.update(extra or {})
    return YoutubeDL(opts)


def _info(url: str, referer: str | None = None) -> dict:
    with _ydl(_referer_opts(referer)) as ydl:
        return ydl.extract_info(url, download=False)


def _referer_opts(referer: str | None) -> dict:
    """Referer mitschicken -- Pflicht bei domainbeschraenkten Embeds.

    Vimeo-Videos in Kursplattformen sind meist auf die Domain der Plattform
    beschraenkt. Ohne passenden Referer verweigert Vimeo die Auskunft.
    """
    return {"http_headers": {"Referer": referer}} if referer else {}


def spur_laden(url: str, sprachen: list[str], referer: str | None = None) -> dict:
    """Holt die Untertitelspur einer beliebigen von yt-dlp erkannten URL.

    Taugt fuer YouTube wie fuer eingebettete Vimeo-Player -- dieselbe
    Mechanik, nur eine andere Quelle. Rueckgabe: info, Kacheln (schon
    entdoppelt), Sprache, ob automatisch erzeugt.
    """
    info = _info(url, referer)
    sprache, format_name, spur_url, automatisch = _waehle_spur(info, sprachen)
    with _ydl(_referer_opts(referer)) as ydl:
        rohdaten = ydl.urlopen(spur_url).read().decode("utf-8", "replace")
    kacheln = vtt.entdoppeln(vtt.parse(rohdaten, format_name))
    if not kacheln:
        raise YoutubeFehler(
            f"Die Untertitelspur ({sprache}/{format_name}) war leer oder nicht lesbar."
        )
    return {
        "info": info,
        "kacheln": kacheln,
        "sprache": sprache,
        "automatisch": automatisch,
    }


def spuren_auflisten(url: str, referer: str | None = None) -> dict:
    """Welche Untertitelspuren gibt es? Fuer die Diagnose in `wissen inspect`."""
    info = _info(url, referer)
    return {
        "titel": info.get("title"),
        "dauer": info.get("duration"),
        "manuell": sorted((info.get("subtitles") or {}).keys()),
        "automatisch": sorted((info.get("automatic_captions") or {}).keys()),
    }


def _waehle_spur(info: dict, sprachen: list[str]) -> tuple[str, str, str, bool]:
    """Sucht die beste Untertitelspur.

    Rueckgabe: (sprache, format, url, ist_automatisch). Von Hand erstellte
    Untertitel gewinnen immer gegen automatische, weil sie Interpunktion haben.
    """
    manuell = info.get("subtitles") or {}
    automatisch = info.get("automatic_captions") or {}

    def suche(quelle: dict) -> tuple[str, str, str] | None:
        for sprache in sprachen:
            for key in (sprache, sprache.split("-")[0]):
                eintraege = quelle.get(key)
                if not eintraege:
                    continue
                for ext in FORMAT_VORZUG:
                    for eintrag in eintraege:
                        if eintrag.get("ext") == ext and eintrag.get("url"):
                            return key, ext, eintrag["url"]
                for eintrag in eintraege:
                    if eintrag.get("url"):
                        return key, eintrag.get("ext") or "vtt", eintrag["url"]
        return None

    treffer = suche(manuell)
    if treffer:
        return (*treffer, False)
    treffer = suche(automatisch)
    if treffer:
        return (*treffer, True)

    vorhanden = sorted(set(manuell) | set(automatisch))
    raise YoutubeFehler(
        "Keine Untertitelspur in den gewuenschten Sprachen "
        f"({', '.join(sprachen)}). Vorhanden: {', '.join(vorhanden) or 'keine'}. "
        "Sprachen in wissen.toml unter [youtube] sprachen anpassen."
    )


def _datum(info: dict) -> str | None:
    roh = info.get("upload_date")
    if roh and len(str(roh)) == 8:
        roh = str(roh)
        return f"{roh[:4]}-{roh[4:6]}-{roh[6:]}"
    return None


def lade_transkript(
    cfg: Konfig,
    ablage: Ablage,
    url: str,
    *,
    praefix: str,
    kurs: str | None = None,
    modul: str | None = None,
    lektion: str | None = None,
) -> Ergebnis:
    """Holt Transkript und Metadaten eines Videos und legt sie im Eingang ab."""
    spur = spur_laden(url, cfg.sprachen)
    info, kacheln = spur["info"], spur["kacheln"]
    sprache, automatisch = spur["sprache"], spur["automatisch"]
    text = vtt.zu_text(kacheln, cfg.marke_alle, schon_entdoppelt=True)

    dauer = info.get("duration")
    letzte = kacheln[-1].ende
    luecke = schema.abdeckung_luecke(letzte, dauer)
    vollstaendig = luecke is None or luecke <= cfg.max_luecke

    video_id = info.get("id") or schema.kurz_hash(url)
    felder = {
        "Titel": info.get("title") or video_id,
        "Kanal": info.get("uploader") or info.get("channel"),
        "Kurs": kurs,
        "Modul": modul,
        "Lektion": lektion,
        "URL": info.get("webpage_url") or url,
        "Veröffentlicht": _datum(info),
        "Erfassungsdatum": schema.heute(),
        "Abdeckung": schema.abdeckung(letzte, dauer, automatisch),
    }
    if not vollstaendig:
        felder["Abdeckung"] += f" — UNVOLLSTÄNDIG, {int(luecke)} s fehlen"

    pfad = ablage.eingang_pfad(praefix, video_id)
    ablage.schreibe(felder, text, pfad)
    return Ergebnis(pfad, felder, luecke, vollstaendig)


# -- Einzelbilder --------------------------------------------------------


def _waehle_format(info: dict, max_hoehe: int = 720) -> dict:
    """Waehlt ein Videoformat, aus dem ffmpeg direkt lesen kann."""
    passend = [
        f for f in info.get("formats") or []
        if f.get("vcodec") not in (None, "none")
        and f.get("url")
        and (f.get("protocol") or "https").startswith("http")
        and not f.get("fragments")
    ]
    if not passend:
        raise YoutubeFehler("Kein direkt lesbares Videoformat gefunden.")
    unter_grenze = [f for f in passend if (f.get("height") or 0) <= max_hoehe]
    kandidaten = unter_grenze or passend
    return max(kandidaten, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))


def _ffmpeg_pflicht() -> str:
    pfad = shutil.which("ffmpeg")
    if not pfad:
        raise YoutubeFehler(
            "ffmpeg fehlt. macOS: brew install ffmpeg -- Debian/Ubuntu: "
            "sudo apt install ffmpeg -- Windows: winget install Gyan.FFmpeg"
        )
    return pfad


def _frame_aus_stream(fmt: dict, sekunden: int, ziel: Path) -> bool:
    """Schnellster Weg: ffmpeg springt im Stream und laedt nur den Augenblick."""
    kopfzeilen = fmt.get("http_headers") or {}
    befehl = [_ffmpeg_pflicht(), "-nostdin", "-loglevel", "error"]
    if kopfzeilen.get("User-Agent"):
        befehl += ["-user_agent", kopfzeilen["User-Agent"]]
    weitere = "".join(
        f"{k}: {v}\r\n" for k, v in kopfzeilen.items() if k != "User-Agent"
    )
    if weitere:
        befehl += ["-headers", weitere]
    befehl += [
        "-ss", str(sekunden), "-i", fmt["url"],
        "-frames:v", "1", "-q:v", "2", "-y", str(ziel),
    ]
    ergebnis = subprocess.run(befehl, capture_output=True, text=True, timeout=180)
    return ergebnis.returncode == 0 and ziel.exists() and ziel.stat().st_size > 0


def _frame_aus_abschnitt(url: str, fmt_id: str, sekunden: int, ziel: Path) -> None:
    """Rueckfallweg: nur die paar Sekunden um den Zeitpunkt herunterladen."""
    from yt_dlp.utils import download_range_func

    start = max(0, sekunden - 1)
    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": False,
            "format": fmt_id,
            "outtmpl": str(Path(tmp) / "schnipsel.%(ext)s"),
            "download_ranges": download_range_func(None, [(start, sekunden + 2)]),
            "force_keyframes_at_cuts": True,
        }
        with _ydl(opts) as ydl:
            ydl.download([url])
        dateien = list(Path(tmp).glob("schnipsel.*"))
        if not dateien:
            raise YoutubeFehler(f"Abschnitt um {sekunden}s konnte nicht geladen werden.")
        befehl = [
            _ffmpeg_pflicht(), "-nostdin", "-loglevel", "error",
            "-ss", str(sekunden - start), "-i", str(dateien[0]),
            "-frames:v", "1", "-q:v", "2", "-y", str(ziel),
        ]
        ergebnis = subprocess.run(befehl, capture_output=True, text=True, timeout=180)
        if ergebnis.returncode != 0 or not ziel.exists():
            raise YoutubeFehler(
                f"ffmpeg konnte bei {sekunden}s kein Bild erzeugen: {ergebnis.stderr.strip()}"
            )


def _bild_einfuegen(body: str, link: str, sekunden: int) -> str:
    """Setzt den Bildlink hinter den Transkript-Absatz, zu dem er gehoert."""
    absaetze = body.split("\n\n")
    marke = f"![Screenshot bei {schema.sekunden_zu_zeit(sekunden)}]({link})"
    if marke in body:
        return body
    letzter = None
    for nr, absatz in enumerate(absaetze):
        treffer = _ZEITMARKE.match(absatz.strip())
        if not treffer:
            continue
        try:
            if schema.zeit_zu_sekunden(treffer.group(1)) <= sekunden:
                letzter = nr
            else:
                break
        except ValueError:
            continue
    if letzter is None:
        return body.rstrip() + "\n\n" + marke
    absaetze.insert(letzter + 1, marke)
    return "\n\n".join(absaetze)


def hole_frames(
    cfg: Konfig, ablage: Ablage, url: str, zeiten: list[int]
) -> tuple[Path, list[str]]:
    """Zieht Einzelbilder zu den angegebenen Zeitpunkten und traegt sie ein.

    Gedacht fuer Regel 5 der Genre-Rezepte: was nur im Bild zu sehen ist, wird
    nicht geraten, sondern als offene Frage mit Timestamp vermerkt und erst mit
    Screenshot uebernommen. Genau diese Timestamps kommen hier herein.
    """
    info = _info(url)
    video_id = info.get("id") or schema.kurz_hash(url)

    dok = ablage.finde_nach_url(info.get("webpage_url") or url)
    if dok is None:
        raise YoutubeFehler(
            f"Zu {url} liegt noch kein Rohtranskript im Eingang. "
            "Erst 'wissen yt ...' ausfuehren."
        )

    fmt = _waehle_format(info)
    ordner = ablage.media_ordner(video_id)
    text = dok.read_text(encoding="utf-8")
    felder = schema.kopf_lesen(text)
    body = text.split("\n---\n", 1)[-1]

    vorhanden = [
        s.strip() for s in (felder.get("Screenshots") or "").split(",") if s.strip()
    ]
    neu: list[str] = []

    for sekunden in sorted(set(zeiten)):
        ziel = ordner / f"{schema.zeit_fuer_dateiname(sekunden)}.jpg"
        if not ziel.exists():
            if not _frame_aus_stream(fmt, sekunden, ziel):
                _frame_aus_abschnitt(url, fmt.get("format_id") or "best", sekunden, ziel)
        rel = ablage.rel(ziel)
        if rel not in vorhanden:
            vorhanden.append(rel)
            neu.append(rel)
        body = _bild_einfuegen(body, ablage.rel_von(ziel, dok), sekunden)

    felder["Screenshots"] = ", ".join(vorhanden)
    ablage.schreibe(felder, body, pfad=dok)
    return dok, neu
