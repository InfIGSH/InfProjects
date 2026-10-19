"""Kommandozeile des Werkzeugs.

    wissen init                      Wissensbasis anlegen
    wissen login <url>               einmalig im Kursportal anmelden
    wissen yt <url>                  YouTube-Transkript holen
    wissen frames <url> --zeit 4:12  Screenshots zu Zeitpunkten nachziehen
    wissen kurs <url> --kurs <name>  Kursseite auslesen
    wissen pdf <pfad> --kurs <name>  PDF oder PDF-Ordner einlesen
    wissen index                     INDEX.md neu aufbauen
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, schema
from .store import Ablage


def _ablage(args) -> tuple[config.Konfig, Ablage]:
    cfg = config.lade(args.config)
    ablage = Ablage(cfg.ablage)
    ablage.pruefe()
    return cfg, ablage


def _melde(ablage: Ablage, pfad: Path, meta: dict) -> None:
    print(f"  -> {ablage.rel(pfad)}  ({meta.get('titel')})")


# -- Befehle -------------------------------------------------------------


def befehl_init(args) -> int:
    cfg = config.lade(args.config)
    ablage = Ablage(cfg.ablage)
    ablage.root.mkdir(parents=True, exist_ok=True)
    angelegt = ablage.init()
    ablage.baue_index()
    print(f"Wissensbasis unter {ablage.root}")
    for pfad in angelegt:
        print(f"  angelegt: {ablage.rel(pfad)}")
    if not angelegt:
        print("  (war schon vollstaendig)")
    if not (ablage.root / ".git").exists():
        print(
            "\nNoch kein Git-Repository. Zum Anlegen:\n"
            f"  cd {ablage.root} && git init && git add -A && "
            "git commit -m 'Wissensbasis angelegt'"
        )
    return 0


def befehl_login(args) -> int:
    from . import web

    cfg = config.lade(args.config)
    web.login(cfg, args.url)
    print(f"Profil gespeichert: {cfg.browser_profil}")
    return 0


def befehl_yt(args) -> int:
    from . import youtube

    cfg, ablage = _ablage(args)
    pfad, meta = youtube.lade_transkript(
        cfg, ablage, args.url, kurs=args.kurs, lektion=args.lektion, tags=args.tag
    )
    _melde(ablage, pfad, meta)
    if args.zeit:
        zeiten = [schema.zeit_zu_sekunden(z) for z in args.zeit]
        _, neu = youtube.hole_frames(cfg, ablage, args.url, zeiten)
        print(f"  {len(neu)} Screenshot(s) ergaenzt")
    if not args.kein_index:
        ablage.baue_index()
    return 0


def befehl_frames(args) -> int:
    from . import youtube

    cfg, ablage = _ablage(args)
    zeiten = [schema.zeit_zu_sekunden(z) for z in args.zeit]
    pfad, neu = youtube.hole_frames(cfg, ablage, args.url, zeiten)
    print(f"{len(neu)} neue(r) Screenshot(s) in {ablage.rel(pfad)}")
    for rel in neu:
        print(f"  {rel}")
    if not args.kein_index:
        ablage.baue_index()
    return 0


def befehl_kurs(args) -> int:
    from . import web

    cfg, ablage = _ablage(args)
    if args.liste:
        ergebnisse = web.lade_liste(
            cfg, ablage, Path(args.liste).expanduser(), kurs=args.kurs,
            screenshot=args.screenshot, headless=args.headless, tags=args.tag,
        )
        print(f"{len(ergebnisse)} Seite(n) abgelegt.")
    else:
        if not args.url:
            print("Entweder eine URL oder --liste angeben.", file=sys.stderr)
            return 2
        pfad, meta = web.lade_seite(
            cfg, ablage, args.url, kurs=args.kurs, lektion=args.lektion,
            titel=args.titel, screenshot=args.screenshot, headless=args.headless,
            tags=args.tag,
        )
        _melde(ablage, pfad, meta)
        if not meta.get("hat_transkript"):
            print(
                "  Hinweis: kein Transkript gefunden. Falls die Seite eines hat,\n"
                "  den Selektor in wissen.toml unter [hosts.\"<domain>\"] eintragen."
            )
    if not args.kein_index:
        ablage.baue_index()
    return 0


def befehl_pdf(args) -> int:
    from . import pdfs

    cfg, ablage = _ablage(args)
    ziel = Path(args.pfad).expanduser()
    if ziel.is_dir():
        ergebnisse = pdfs.lade_ordner(cfg, ablage, ziel, kurs=args.kurs, tags=args.tag)
        print(f"{len(ergebnisse)} PDF(s) abgelegt.")
        ocr = [m for _, m in ergebnisse if m.get("braucht_ocr")]
        if ocr:
            print(f"  {len(ocr)} davon ohne Textlayer -- siehe OCR-Hinweis im Dokument.")
    else:
        pfad, meta = pdfs.lade_pdf(
            cfg, ablage, ziel, kurs=args.kurs, lektion=args.lektion,
            titel=args.titel, tags=args.tag,
        )
        _melde(ablage, pfad, meta)
        if meta.get("braucht_ocr"):
            print("  Kein Textlayer -- siehe OCR-Hinweis im Dokument.")
    if not args.kein_index:
        ablage.baue_index()
    return 0


def befehl_index(args) -> int:
    _, ablage = _ablage(args)
    pfad = ablage.baue_index()
    print(f"Index neu gebaut: {pfad}")
    return 0


# -- Argumente -----------------------------------------------------------


def baue_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wissen",
        description="Liest Webinhalte, Kursseiten und PDFs aus und legt sie "
                    "als Markdown in einer zentralen Wissensbasis ab.",
    )
    p.add_argument("--config", help="Pfad zur wissen.toml")
    unter = p.add_subparsers(dest="befehl", required=True)

    def gemeinsam(sub):
        sub.add_argument("--tag", action="append", default=[],
                         help="Schlagwort, mehrfach moeglich")
        sub.add_argument("--kein-index", action="store_true",
                         help="INDEX.md nicht neu bauen (bei Stapelverarbeitung)")

    s = unter.add_parser("init", help="Ordnerstruktur der Wissensbasis anlegen")
    s.set_defaults(func=befehl_init)

    s = unter.add_parser("login", help="einmalig im Kursportal anmelden")
    s.add_argument("url", help="Login- oder Kursseite")
    s.set_defaults(func=befehl_login)

    s = unter.add_parser("yt", help="YouTube-Transkript holen")
    s.add_argument("url")
    s.add_argument("--kurs", help="Kurs-Slug, falls das Video zu einem Kurs gehoert")
    s.add_argument("--lektion", type=int, help="Position im Kurs")
    s.add_argument("--zeit", action="append", default=[],
                   help="Zeitpunkt fuer einen Screenshot, z.B. 4:12 (mehrfach)")
    gemeinsam(s)
    s.set_defaults(func=befehl_yt)

    s = unter.add_parser("frames", help="Screenshots zu Zeitpunkten nachziehen")
    s.add_argument("url")
    s.add_argument("--zeit", action="append", required=True,
                   help="Zeitpunkt, z.B. 4:12 oder 1:02:03 (mehrfach)")
    gemeinsam(s)
    s.set_defaults(func=befehl_frames)

    s = unter.add_parser("kurs", help="Kursseite(n) auslesen")
    s.add_argument("url", nargs="?", help="einzelne Seite")
    s.add_argument("--kurs", required=True, help="Kursname (wird zum Ordner)")
    s.add_argument("--liste", help="Datei mit einer URL pro Zeile, optional 'URL | Titel'")
    s.add_argument("--lektion", type=int, help="Position im Kurs")
    s.add_argument("--titel", help="Titel von Hand setzen")
    s.add_argument("--screenshot", action="store_true", help="Seitenbild mitspeichern")
    s.add_argument("--headless", action="store_true",
                   help="ohne sichtbares Fenster (loest bei manchen Portalen Sperren aus)")
    gemeinsam(s)
    s.set_defaults(func=befehl_kurs)

    s = unter.add_parser("pdf", help="PDF oder Ordner mit PDFs einlesen")
    s.add_argument("pfad")
    s.add_argument("--kurs", required=True, help="Kursname (wird zum Ordner)")
    s.add_argument("--lektion", type=int, help="Position im Kurs (nur bei Einzeldatei)")
    s.add_argument("--titel", help="Titel von Hand setzen (nur bei Einzeldatei)")
    gemeinsam(s)
    s.set_defaults(func=befehl_pdf)

    s = unter.add_parser("index", help="INDEX.md neu aufbauen")
    s.set_defaults(func=befehl_index)

    return p


def main(argv: list[str] | None = None) -> int:
    args = baue_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        return 130
    except (config.KonfigFehler, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
