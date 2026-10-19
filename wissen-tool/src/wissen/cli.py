"""Kommandozeile des Werkzeugs.

Das Werkzeug deckt die Beschaffung ab -- Ablauf A Schritt 2 und Ablauf C
Schritte 1, 2 und 6 aus ANLEITUNG.md. Alles danach (Delta-Abgleich,
Einarbeiten, Konzeptregister, quellen.md, Notion-Meldung) bleibt Handarbeit
nach ANLEITUNG.md.

    wissen init                        Eingangsordner anlegen
    wissen login <url>                 einmalig im Kursportal anmelden
    wissen inspect <url>               nachsehen, was auf der Seite steht
    wissen yt <url> --praefix synthwave      YouTube-Transkript
    wissen frames <url> --zeit 4:12          Screenshots zu offenen Fragen
    wissen kurs <url> --praefix thinkspace_x Kursseite auslesen
    wissen pdf <pfad> --praefix training     PDF einlesen
    wissen eingang                     Rückstand im Eingang zeigen
    wissen quellen <datei>             Entwurf für quellen.md
    wissen verarbeitet <datei>         nach eingang/verarbeitet/ verschieben
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
    for warnung in ablage.warnungen():
        print(f"Hinweis: {warnung}", file=sys.stderr)
    return cfg, ablage


# -- Befehle -------------------------------------------------------------


def befehl_init(args) -> int:
    cfg = config.lade(args.config)
    ablage = Ablage(cfg.ablage)
    if not ablage.root.is_dir():
        print(
            f"Fehler: {ablage.root} existiert nicht. In wissen.toml unter "
            "[ablage] pfad den buch/-Ordner eintragen.",
            file=sys.stderr,
        )
        return 1
    angelegt = ablage.init()
    print(f"Ablage: {ablage.root}")
    for pfad in angelegt:
        print(f"  angelegt: {ablage.rel(pfad)}")
    if not angelegt:
        print("  (Eingangsordner waren schon vorhanden)")
    for warnung in ablage.warnungen():
        print(f"  Hinweis: {warnung}")
    return 0


def befehl_login(args) -> int:
    from . import web

    cfg = config.lade(args.config)
    web.login(cfg, args.url)
    print(f"Profil gespeichert: {cfg.browser_profil}")
    return 0


def befehl_inspect(args) -> int:
    from . import pruefen

    cfg = config.lade(args.config)
    # Aufgeloest, damit die ausgegebenen Pfade unmissverstaendlich sind --
    # ein relatives "./berichte" sagt nicht, wo es tatsaechlich liegt.
    ausgabe = (
        Path(args.ausgabe).expanduser() if args.ausgabe else Path.cwd() / "berichte"
    ).resolve()
    bericht = pruefen.pruefe(
        cfg, args.url, ausgabe, klicks=args.klick, headless=args.headless
    )
    print(f"\nOrdner:  {ausgabe}")
    print(f"Bericht: {bericht.name}")
    print("Darin stehen Frames, Kandidaten und ein Vorschlag für wissen.toml,")
    print("daneben das Seitenbild (.png) und das HTML jedes Frames.")
    return 0


def befehl_yt(args) -> int:
    from . import youtube

    cfg, ablage = _ablage(args)
    ergebnis = youtube.lade_transkript(
        cfg, ablage, args.url, praefix=args.praefix,
        kurs=args.kurs, modul=args.modul, lektion=args.lektion,
    )
    print(f"  -> {ablage.rel(ergebnis.pfad)}")
    print(f"     {ergebnis.felder['Abdeckung']}")
    if not ergebnis.vollstaendig:
        print(
            f"  WARNUNG: Das Transkript endet {int(ergebnis.luecke)} s vor dem "
            "Videoende. Vor dem Einarbeiten prüfen (ANLEITUNG, Ablauf C 1).",
            file=sys.stderr,
        )
    if args.zeit:
        zeiten = [schema.zeit_zu_sekunden(z) for z in args.zeit]
        _, neu = youtube.hole_frames(cfg, ablage, args.url, zeiten)
        print(f"  {len(neu)} Screenshot(s) ergänzt")
    return 0


def befehl_frames(args) -> int:
    from . import youtube

    cfg, ablage = _ablage(args)
    zeiten = [schema.zeit_zu_sekunden(z) for z in args.zeit]
    pfad, neu = youtube.hole_frames(cfg, ablage, args.url, zeiten)
    print(f"{len(neu)} neue(r) Screenshot(s) in {ablage.rel(pfad)}")
    for rel in neu:
        print(f"  {rel}")
    return 0


def befehl_links(args) -> int:
    from . import pruefen

    cfg = config.lade(args.config)
    ausgabe = (
        Path(args.ausgabe).expanduser() if args.ausgabe else Path.cwd() / "berichte"
    ).resolve()
    bericht, liste, gruppen = pruefen.sammle_links(
        cfg, args.url, ausgabe, headless=args.headless
    )
    print(f"\nOrdner:  {ausgabe}")
    print(f"Bericht: {bericht.name}")
    if liste:
        print(f"Liste:   {liste.name}  ({gruppen[0][1]} Zeilen, Form {gruppen[0][0]})")
        print("\nListe durchsehen, dann:")
        print(f"  wissen kurs --liste \"{liste}\" --praefix <kurs>")
    else:
        print("Keine Gruppe mit mehreren gleichartigen Links gefunden.")
        print("Der Bericht zeigt, was auf der Seite verlinkt ist.")
    return 0


def befehl_kurs(args) -> int:
    from . import web

    cfg, ablage = _ablage(args)
    if args.liste:
        ergebnisse, uebersprungen = web.lade_liste(
            cfg, ablage, Path(args.liste).expanduser(), praefix=args.praefix,
            kurs=args.kurs, screenshot=args.screenshot, headless=args.headless,
            neu_laden=args.neu_laden,
        )
        print(f"\n{len(ergebnisse)} Seite(n) abgelegt.")
        if uebersprungen:
            print(
                f"  {len(uebersprungen)} schon erfasst und übergangen "
                "(--neu-laden erzwingt sie)."
            )
        ohne = [f for _, f, _ in ergebnisse if "KEIN Transkript" in f.get("Abdeckung", "")]
        if ohne:
            print(f"  {len(ohne)} davon ohne Transkript -- 'wissen inspect' nutzen.")
        return 0

    if not args.url:
        print("Entweder eine URL oder --liste angeben.", file=sys.stderr)
        return 2
    if not args.neu_laden:
        vorhanden = ablage.finde_nach_url(args.url)
        if vorhanden is not None:
            print(f"Schon erfasst: {ablage.rel(vorhanden)}")
            print("Mit --neu-laden erneut holen.")
            return 0
    pfad, felder, meldungen = web.lade_seite(
        cfg, ablage, args.url, praefix=args.praefix, kurs=args.kurs,
        modul=args.modul, lektion=args.lektion, titel=args.titel,
        screenshot=args.screenshot, headless=args.headless,
    )
    print(f"  -> {ablage.rel(pfad)}")
    print(f"     {felder['Abdeckung']}")
    for meldung in meldungen:
        print(f"     {meldung}")
    return 0


def befehl_pdf(args) -> int:
    from . import pdfs

    cfg, ablage = _ablage(args)
    ziel = Path(args.pfad).expanduser()
    if ziel.is_dir():
        ergebnisse = pdfs.lade_ordner(
            cfg, ablage, ziel, praefix=args.praefix, kurs=args.kurs
        )
        print(f"\n{len(ergebnisse)} PDF(s) abgelegt.")
        ocr = [1 for _, _, braucht in ergebnisse if braucht]
        if ocr:
            print(f"  {len(ocr)} davon ohne Textlayer -- siehe OCR-Hinweis.")
    else:
        pfad, felder, braucht_ocr = pdfs.lade_pdf(
            cfg, ablage, ziel, praefix=args.praefix, kurs=args.kurs,
            lektion=args.lektion, titel=args.titel,
        )
        print(f"  -> {ablage.rel(pfad)}")
        print(f"     {felder['Abdeckung']}")
        if braucht_ocr:
            print("  Kein Textlayer -- siehe OCR-Hinweis im Dokument.")
    return 0


def befehl_eingang(args) -> int:
    _, ablage = _ablage(args)
    offen = list(ablage.dokumente())
    if not offen:
        print(f"Eingang leer: {ablage.rel(ablage.eingang)}")
        return 0
    print(f"{len(offen)} Datei(en) im Eingang, noch nicht eingearbeitet:\n")
    for pfad, felder in offen:
        print(f"  {pfad.name}")
        print(f"    {felder.get('Titel', '?')}")
        if felder.get("Abdeckung"):
            print(f"    {felder['Abdeckung']}")
    print(
        "\nNach dem Einarbeiten: 'wissen verarbeitet <datei>' "
        "(ANLEITUNG, Ablauf C 6)."
    )
    return 0


def befehl_quellen(args) -> int:
    _, ablage = _ablage(args)
    pfad = Path(args.datei).expanduser()
    if not pfad.is_absolute():
        for basis in (ablage.eingang, ablage.verarbeitet, Path.cwd()):
            if (basis / pfad.name).is_file():
                pfad = basis / pfad.name
                break
    if not pfad.is_file():
        print(f"Fehler: {pfad} nicht gefunden.", file=sys.stderr)
        return 1
    felder = schema.kopf_lesen(pfad.read_text(encoding="utf-8"))
    print("Entwurf für den Abschnitt „Einzelquellen“ in quellen.md:\n")
    print(ablage.quellen_eintrag(pfad, felder))
    print("\n(Nur ein Vorschlag -- quellen.md wird vom Werkzeug nicht angefasst.)")
    return 0


def befehl_verarbeitet(args) -> int:
    _, ablage = _ablage(args)
    pfad = Path(args.datei).expanduser()
    if not pfad.is_absolute():
        pfad = ablage.eingang / pfad.name
    ziel = ablage.verschiebe_verarbeitet(pfad)
    print(f"verschoben: {ablage.rel(ziel)}")
    return 0


# -- Argumente -----------------------------------------------------------


def baue_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wissen",
        description="Holt Transkripte, Kursseiten und PDF-Text in den "
                    "eingang/-Ordner des Buchprojekts.",
    )
    p.add_argument("--config", help="Pfad zur wissen.toml")
    unter = p.add_subparsers(dest="befehl", required=True)

    s = unter.add_parser("init", help="Eingangsordner anlegen")
    s.set_defaults(func=befehl_init)

    s = unter.add_parser("login", help="einmalig im Kursportal anmelden")
    s.add_argument("url", help="Login- oder Lektionsseite")
    s.set_defaults(func=befehl_login)

    s = unter.add_parser("inspect", help="nachsehen, was auf einer Seite steht")
    s.add_argument("url")
    s.add_argument("--klick", action="append", default=[],
                   help="Selektor, der ein Panel öffnet (mehrfach möglich)")
    s.add_argument("--ausgabe", help="Ordner für den Bericht (Standard: ./berichte)")
    s.add_argument("--headless", action="store_true")
    s.set_defaults(func=befehl_inspect)

    s = unter.add_parser("yt", help="YouTube-Transkript holen")
    s.add_argument("url")
    s.add_argument("--praefix", required=True,
                   help="Dateipräfix, z.B. das Genre: eingang/<präfix>_<video-id>.md")
    s.add_argument("--kurs", help="Kursname, falls das Video zu einem Kurs gehört")
    s.add_argument("--modul")
    s.add_argument("--lektion")
    s.add_argument("--zeit", action="append", default=[],
                   help="Zeitpunkt für einen Screenshot, z.B. 4:12 (mehrfach)")
    s.set_defaults(func=befehl_yt)

    s = unter.add_parser("frames", help="Screenshots zu Zeitpunkten nachziehen")
    s.add_argument("url")
    s.add_argument("--zeit", action="append", required=True,
                   help="Zeitpunkt, z.B. 4:12 oder 1:02:03 (mehrfach)")
    s.set_defaults(func=befehl_frames)

    s = unter.add_parser("kurs", help="Kursseite(n) auslesen")
    s.add_argument("url", nargs="?", help="einzelne Seite")
    s.add_argument("--praefix", required=True,
                   help="Dateipräfix, z.B. thinkspace_how-to-write-cinematic-music")
    s.add_argument("--liste", help="Datei mit einer URL pro Zeile, optional 'URL | Titel'")
    s.add_argument("--kurs")
    s.add_argument("--modul")
    s.add_argument("--lektion")
    s.add_argument("--titel", help="Titel von Hand setzen")
    s.add_argument("--screenshot", action="store_true", help="Seitenbild mitspeichern")
    s.add_argument("--headless", action="store_true",
                   help="ohne sichtbares Fenster (löst bei manchen Portalen Sperren aus)")
    s.add_argument("--neu-laden", action="store_true",
                   help="auch schon erfasste URLs erneut holen")
    s.set_defaults(func=befehl_kurs)

    s = unter.add_parser("links", help="Lektions-URLs einer Kursseite sammeln")
    s.add_argument("url", help="Kursübersicht, von der aus die Lektionen verlinkt sind")
    s.add_argument("--ausgabe", help="Ordner für Bericht und Liste (Standard: ./berichte)")
    s.add_argument("--headless", action="store_true")
    s.set_defaults(func=befehl_links)

    s = unter.add_parser("pdf", help="PDF oder Ordner mit PDFs einlesen")
    s.add_argument("pfad")
    s.add_argument("--praefix", required=True, help="Dateipräfix")
    s.add_argument("--kurs")
    s.add_argument("--lektion", help="nur bei Einzeldatei")
    s.add_argument("--titel", help="nur bei Einzeldatei")
    s.set_defaults(func=befehl_pdf)

    s = unter.add_parser("eingang", help="Rückstand im Eingang zeigen")
    s.set_defaults(func=befehl_eingang)

    s = unter.add_parser("quellen", help="Entwurf für den quellen.md-Eintrag")
    s.add_argument("datei")
    s.set_defaults(func=befehl_quellen)

    s = unter.add_parser("verarbeitet", help="Datei nach eingang/verarbeitet/ verschieben")
    s.add_argument("datei")
    s.set_defaults(func=befehl_verarbeitet)

    return p


def main(argv: list[str] | None = None) -> int:
    args = baue_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nAbgebrochen.", file=sys.stderr)
        return 130
    except (config.KonfigFehler, FileNotFoundError, FileExistsError,
            RuntimeError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
