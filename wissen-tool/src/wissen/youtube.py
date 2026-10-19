"""YouTube: Transkript holen, Einzelbilder an bestimmten Zeitpunkten ziehen.

Beides laeuft ohne API-Key. Das Transkript kommt aus der Untertitelspur
(auch der automatisch erzeugten), die Bilder zieht ffmpeg direkt aus dem
Videostream -- es wird nur der angefragte Augenblick geladen, nicht das Video.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import schema, vtt
from .config import Konfig
from .store import Ablage

#: Reihenfolge, in der Untertitelformate bevorzugt werden.
FORMAT_VORZUG = ["vtt", "json3", "srv3", "srv1", "ttml", "srt"]

_ZEITMARKE = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]")


class YoutubeFehler(RuntimeError):
    pass


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


def _info(url: str) -> dict:
    with _ydl() as ydl:
        return ydl.extract_info(url, download=False)


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


def lade_transkript(
    cfg: Konfig,
    ablage: Ablage,
    url: str,
    *,
    kurs: str | None = None,
    lektion: int | None = None,
    tags: list[str] | None = None,
) -> tuple[Path, dict]:
    """Holt Transkript und Metadaten eines Videos und legt sie ab."""
    info = _info(url)
    sprache, format_name, spur_url, automatisch = _waehle_spur(info, cfg.sprachen)

    with _ydl() as ydl:
        rohdaten = ydl.urlopen(spur_url).read().decode("utf-8", "replace")

    kacheln = vtt.parse(rohdaten, format_name)
    text = vtt.zu_text(kacheln, cfg.marke_alle)
    if not text.strip():
        raise YoutubeFehler(
            f"Die Untertitelspur ({sprache}/{format_name}) war leer oder nicht lesbar."
        )

    video_id = info.get("id") or schema.kurz_hash(url)
    meta = schema.neues_frontmatter(
        id=f"yt:{video_id}",
        typ="youtube",
        titel=info.get("title") or video_id,
        quelle=info.get("webpage_url") or url,
        kurs=kurs,
        lektion=lektion,
        sprache=sprache,
        dauer=info.get("duration"),
        tags=tags or [],
    )
    if info.get("uploader"):
        meta["kanal"] = info["uploader"]
    meta["untertitel"] = "automatisch" if automatisch else "manuell"

    kopf = [f"# {meta['titel']}", ""]
    if info.get("uploader"):
        kopf.append(f"Kanal: {info['uploader']}")
    if info.get("duration"):
        kopf.append(f"Laenge: {schema.sekunden_zu_zeit(info['duration'])}")
    kopf.append(f"Quelle: {meta['quelle']}")
    kopf.append(
        "Untertitel: " + ("automatisch erzeugt (Fehler moeglich)" if automatisch
                          else "vom Kanal erstellt")
    )
    kopf += ["", "## Transkript", ""]

    pfad = ablage.schreibe(meta, "\n".join(kopf) + "\n" + text)
    return pfad, meta


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

    Das zugehoerige Transkript muss schon abgelegt sein -- die Bilder werden
    in dessen Frontmatter und an der passenden Stelle im Text verlinkt.
    """
    info = _info(url)
    video_id = info.get("id") or schema.kurz_hash(url)
    quellen_id = f"yt-{video_id}"

    dok = ablage.finde_nach_id(f"yt:{video_id}")
    if dok is None:
        raise YoutubeFehler(
            f"Zu Video {video_id} liegt noch kein Transkript in der Ablage. "
            f"Erst 'wissen yt {url}' ausfuehren."
        )

    fmt = _waehle_format(info)
    ordner = ablage.asset_ordner(quellen_id)
    meta, body = schema.frontmatter_load(dok.read_text(encoding="utf-8"))
    assets = list(meta.get("assets") or [])
    neu: list[str] = []

    for sekunden in sorted(set(zeiten)):
        ziel = ordner / f"{schema.zeit_fuer_dateiname(sekunden)}.jpg"
        if not ziel.exists():
            if not _frame_aus_stream(fmt, sekunden, ziel):
                _frame_aus_abschnitt(url, fmt.get("format_id") or "best", sekunden, ziel)
        rel = ablage.rel(ziel)
        if rel not in assets:
            assets.append(rel)
            neu.append(rel)
        body = _bild_einfuegen(body, ablage.rel_von(ziel, dok), sekunden)

    meta["assets"] = assets
    ablage.schreibe(meta, body, pfad=dok)
    return dok, neu
