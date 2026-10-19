"""YouTube: Transkript holen, Einzelbilder an bestimmten Zeitpunkten ziehen.

Beides laeuft ohne API-Key. Das Transkript kommt aus der Untertitelspur
(auch der automatisch erzeugten), die Bilder zieht ffmpeg direkt aus dem
Videostream -- es wird nur der angefragte Augenblick geladen, nicht das Video.

Die Abdeckung wird gegen die Videolaenge geprueft (ANLEITUNG.md, Ablauf C
Schritt 1): reicht die letzte Zeitmarke nicht bis etwa eine Minute an das
Ende, ist das Transkript unvollstaendig und das Werkzeug sagt es.
"""

from __future__ import annotations

import contextlib
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


def abrufen(spur_url: str, referer: str | None = None) -> tuple[str, str]:
    """Laedt eine Spurdatei und beschreibt, was zurueckkam.

    Rueckgabe: (Text, Diagnose). Der Text kann unbrauchbar sein -- die
    Diagnose sagt dann, warum: Laenge, Content-Type und Anfang der Antwort.
    Ohne diese Angaben ist "leer oder nicht lesbar" nicht zu unterscheiden
    von einer Fehlerseite oder einem unerwarteten Format.
    """
    try:
        with _ydl(_referer_opts(referer)) as ydl:
            antwort = ydl.urlopen(spur_url)
            rohdaten = antwort.read()
    except Exception as exc:
        return "", f"Abruf fehlgeschlagen: {type(exc).__name__}: {exc}"

    typ = "?"
    with contextlib.suppress(Exception):
        typ = antwort.headers.get("Content-Type") or "?"
    text = rohdaten.decode("utf-8", "replace")
    vorschau = re.sub(r"\s+", " ", text[:200]).strip()
    return text, f"{len(rohdaten)} Bytes, Content-Type {typ}, Anfang: {vorschau!r}"


def spur_kandidaten(info: dict, sprachen: list[str]) -> list[tuple[str, str, str, bool]]:
    """Alle passenden Spuren als (sprache, format, url, automatisch), beste zuerst.

    Mehrere Kandidaten, weil eine einzelne URL leer zurueckkommen kann --
    dann ist die naechste dran, statt gleich aufzugeben.
    """
    manuell = info.get("subtitles") or {}
    maschinell = info.get("automatic_captions") or {}
    ergebnis: list[tuple[str, str, str, bool]] = []
    gesehen: set[tuple[str, str]] = set()

    for quelle, aus_maschine in ((manuell, False), (maschinell, True)):
        for sprache in sprachen:
            for key in passende_schluessel(quelle, sprache):
                eintraege = quelle.get(key) or []
                nach_vorzug = sorted(
                    (e for e in eintraege if e.get("url")),
                    key=lambda e: (
                        FORMAT_VORZUG.index(e["ext"])
                        if e.get("ext") in FORMAT_VORZUG else len(FORMAT_VORZUG)
                    ),
                )
                for eintrag in nach_vorzug:
                    marke = (key, eintrag["url"])
                    if marke in gesehen:
                        continue
                    gesehen.add(marke)
                    ergebnis.append((
                        key,
                        eintrag.get("ext") or "vtt",
                        eintrag["url"],
                        aus_maschine or ist_autogen(key),
                    ))
    return ergebnis


def spur_laden(url: str, sprachen: list[str], referer: str | None = None) -> dict:
    """Holt die Untertitelspur einer beliebigen von yt-dlp erkannten URL.

    Taugt fuer YouTube wie fuer eingebettete Vimeo-Player -- dieselbe
    Mechanik, nur eine andere Quelle. Probiert alle passenden Spuren der
    Reihe nach; scheitern alle, nennt der Fehler fuer jede den Grund.
    """
    info = _info(url, referer)
    kandidaten = spur_kandidaten(info, sprachen)
    if not kandidaten:
        vorhanden = sorted(
            set(info.get("subtitles") or {}) | set(info.get("automatic_captions") or {})
        )
        raise YoutubeFehler(
            "Keine Untertitelspur in den gewuenschten Sprachen "
            f"({', '.join(sprachen)}). Vorhanden: {', '.join(vorhanden) or 'keine'}. "
            "Sprachen in wissen.toml unter [youtube] sprachen anpassen."
        )

    gruende: list[str] = []
    for sprache, format_name, spur_url, automatisch in kandidaten:
        text, diagnose = abrufen(spur_url, referer)
        kacheln = vtt.entdoppeln(vtt.parse(text, format_name)) if text else []
        if kacheln:
            return {
                "info": info,
                "kacheln": kacheln,
                "sprache": sprache,
                "automatisch": automatisch,
                "diagnose": diagnose,
            }
        gruende.append(f"{sprache}/{format_name}: {diagnose}")

    raise YoutubeFehler(
        "Keine der gefundenen Untertitelspuren liess sich lesen:\n  "
        + "\n  ".join(gruende)
    )


def spur_probe(
    url: str,
    sprachen: list[str],
    referer: str | None,
    ordner: Path,
    marke: str,
) -> tuple[dict, list[dict]]:
    """Versucht jede Spur und legt die Rohantwort ab -- fuer `wissen inspect`.

    Nicht nur auflisten, sondern tatsaechlich abrufen: erst daran zeigt sich,
    ob eine gefundene Spur auch Inhalt hat. Die Rohdatei bleibt liegen, damit
    ein unerwartetes Format erkennbar ist.
    """
    info = _info(url, referer)
    ergebnis: list[dict] = []
    for nr, (sprache, format_name, spur_url, automatisch) in enumerate(
        spur_kandidaten(info, sprachen)
    ):
        text, diagnose = abrufen(spur_url, referer)
        datei = None
        if text:
            datei = ordner / (
                f"{marke}.spur{nr}-{schema.slugify(sprache, 20)}.{format_name}"
            )
            with contextlib.suppress(Exception):
                datei.write_text(text, encoding="utf-8")
        kacheln = vtt.entdoppeln(vtt.parse(text, format_name)) if text else []
        ergebnis.append({
            "sprache": sprache,
            "format": format_name,
            "automatisch": automatisch,
            "url": spur_url,
            "diagnose": diagnose,
            "kacheln": len(kacheln),
            "datei": datei,
        })
    return info, ergebnis


def spuren_auflisten(url: str, referer: str | None = None) -> dict:
    """Welche Untertitelspuren gibt es? Fuer die Diagnose in `wissen inspect`."""
    info = _info(url, referer)
    manuell = sorted((info.get("subtitles") or {}).keys())
    return {
        "titel": info.get("title"),
        "dauer": info.get("duration"),
        # Spuren mit Autogen-Kuerzel stehen bei Vimeo unter den regulaeren,
        # gehoeren aber zu den maschinellen -- hier getrennt ausgewiesen.
        "manuell": [k for k in manuell if not ist_autogen(k)],
        "automatisch": sorted(
            [k for k in manuell if ist_autogen(k)]
            + list((info.get("automatic_captions") or {}).keys())
        ),
    }


def ist_autogen(schluessel: str) -> bool:
    """Erkennt automatisch erzeugte Spuren am Sprachkuerzel.

    Vimeo listet seine Maschinenuntertitel als `en-x-autogen` unter den
    regulaeren Spuren, nicht unter den automatischen. Ohne diese Pruefung
    waeren sie als vom Anbieter erstellt ausgewiesen -- und damit
    vertrauenswuerdiger, als sie sind.
    """
    klein = (schluessel or "").lower()
    return "autogen" in klein or klein.endswith(("-auto", "-asr"))


def passende_schluessel(vorhanden, sprache: str) -> list[str]:
    """Spurschluessel, die zu einer Wunschsprache passen -- beste zuerst.

    Ein Wunsch nach `en` muss auch `en-US` und `en-x-autogen` finden; ein
    exakter Vergleich uebersieht genau die Spuren, die tatsaechlich da sind.
    Von Hand erstellte Varianten gehen vor automatisch erzeugten.
    """
    gewuenscht = sprache.lower()
    basis = gewuenscht.split("-")[0]
    reihenfolge: list[str] = []

    def dazu(kandidaten):
        for key in kandidaten:
            if key not in reihenfolge:
                reihenfolge.append(key)

    dazu([k for k in vorhanden if k.lower() == gewuenscht])
    dazu([k for k in vorhanden if k.lower() == basis])
    dazu(sorted(
        (k for k in vorhanden if k.lower().startswith(basis + "-")),
        key=lambda k: (ist_autogen(k), len(k), k),
    ))
    return reihenfolge


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
