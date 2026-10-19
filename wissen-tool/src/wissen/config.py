"""Konfiguration laden.

Gesucht wird in dieser Reihenfolge:
  1. Pfad aus $WISSEN_CONFIG
  2. ./wissen.toml im aktuellen Verzeichnis
  3. ~/.config/wissen/wissen.toml
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

STANDARD_SPRACHEN = ["de", "de-DE", "de-orig", "en", "en-US"]


class KonfigFehler(RuntimeError):
    """Konfiguration fehlt oder ist unbrauchbar."""


@dataclass
class Konfig:
    ablage: Path
    browser_profil: Path
    sprachen: list[str] = field(default_factory=lambda: list(STANDARD_SPRACHEN))
    marke_alle: int = 30
    max_luecke: int = 60
    warte_ms: int = 1500
    hosts: dict = field(default_factory=dict)
    quelle: Path | None = None

    def host_regeln(self, url: str) -> dict:
        """Host-spezifische Selektoren und Klicks fuer eine URL.

        Passend ist der laengste konfigurierte Host, der auf den Hostnamen der
        URL passt -- so kann `lernplattform.de` eine Grundregel setzen und
        `kurse.lernplattform.de` sie verfeinern.
        """
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
        treffer: dict = {}
        laenge = -1
        for muster, regeln in self.hosts.items():
            muster = muster.lower()
            if (host == muster or host.endswith("." + muster)) and len(muster) > laenge:
                treffer, laenge = regeln, len(muster)
        return treffer


def _finde_datei(explizit: str | os.PathLike | None = None) -> Path | None:
    kandidaten: list[Path] = []
    if explizit:
        kandidaten.append(Path(explizit))
    if os.environ.get("WISSEN_CONFIG"):
        kandidaten.append(Path(os.environ["WISSEN_CONFIG"]))
    kandidaten.append(Path.cwd() / "wissen.toml")
    kandidaten.append(Path.home() / ".config" / "wissen" / "wissen.toml")
    for pfad in kandidaten:
        pfad = pfad.expanduser()
        if pfad.is_file():
            return pfad
    return None


def lade(explizit: str | os.PathLike | None = None) -> Konfig:
    pfad = _finde_datei(explizit)
    if pfad is None:
        raise KonfigFehler(
            "Keine wissen.toml gefunden. Lege eine an (Vorlage: wissen.toml.example) "
            "oder setze $WISSEN_CONFIG auf ihren Pfad."
        )
    # Nicht tomllib.load(datei): Notepad und andere Windows-Editoren schreiben
    # der Datei gern eine unsichtbare Byte-Order-Mark voran, an der der Parser
    # in der ersten Zeile scheitert. 'utf-8-sig' entfernt sie, falls vorhanden.
    try:
        text = pfad.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise KonfigFehler(
            f"{pfad} ist nicht UTF-8-kodiert. Im Editor erneut als UTF-8 "
            f"speichern. ({exc})"
        ) from exc
    try:
        daten = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise KonfigFehler(
            f"{pfad} ist keine gültige TOML-Datei: {exc}\n"
            "Häufigste Ursache unter Windows: einfache Backslashes im Pfad. "
            'Schrägstriche nehmen, z.B. pfad = "C:/Users/Name/Ordner".'
        ) from exc

    ablage_roh = (daten.get("ablage") or {}).get("pfad")
    if not ablage_roh:
        raise KonfigFehler(f"In {pfad} fehlt [ablage] pfad = \"...\".")

    browser = daten.get("browser") or {}
    youtube = daten.get("youtube") or {}
    web = daten.get("web") or {}

    profil_roh = browser.get("profil") or "~/.local/share/wissen/browser-profil"

    return Konfig(
        ablage=Path(ablage_roh).expanduser().resolve(),
        browser_profil=Path(profil_roh).expanduser().resolve(),
        sprachen=list(youtube.get("sprachen") or STANDARD_SPRACHEN),
        marke_alle=int(youtube.get("marke_alle", 30)),
        max_luecke=int(youtube.get("max_luecke", 60)),
        warte_ms=int(web.get("warte_ms", 1500)),
        hosts=daten.get("hosts") or {},
        quelle=pfad,
    )
