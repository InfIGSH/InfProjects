"""`wissen inspect` -- nachsehen, was auf einer Kursseite tatsaechlich steht.

Gedacht fuer den Fall, dass ein Transkript nicht automatisch gefunden wird.
Der Befehl oeffnet die Seite mit der vorhandenen Anmeldung, geht jeden Frame
durch -- auch die fremden Origins -- und schreibt einen Bericht mit allen
Kandidaten samt fertigem Selektorvorschlag.

Es wird nur gelesen. Kein Klick, kein Fortschritt, keine Aenderung an der
Seite. Soll ein eingeklapptes Panel mitgeprueft werden, kann der oeffnende
Selektor mit `--klick` einmalig mitgegeben werden; auch der laeuft durch die
Sperrliste aus `web.py`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from . import erkennung, schema, web
from .config import Konfig


LINK_JS = """
() => [...document.querySelectorAll('a[href]')].map(a => ({
  href: a.href,
  text: (a.innerText || a.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
}))
"""


def _muster(url: str) -> str:
    """Pfadform einer URL, Zahlen durch '#' ersetzt.

    So fallen alle Lektionslinks eines Kurses zu einem Muster zusammen und
    heben sich von Navigation und Fusszeile ab.
    """
    from urllib.parse import urlparse

    pfad = urlparse(url).path or "/"
    teile = ["#" if t.isdigit() else t for t in pfad.split("/")]
    return "/".join(teile)


def sammle_links(
    cfg: Konfig, url: str, ausgabe: Path, *, headless: bool = False
) -> tuple[Path, Path | None, list[tuple[str, int]]]:
    """Sammelt alle Links einer Seite und gruppiert sie nach Pfadform.

    Gedacht zum Aufbauen der URL-Liste fuer `wissen kurs --liste`: die
    Lektionen eines Kurses teilen eine Pfadform, und die groesste Gruppe mit
    gleicher Form ist fast immer die Lektionsliste.
    """
    from collections import OrderedDict

    ausgabe = Path(ausgabe).expanduser()
    ausgabe.mkdir(parents=True, exist_ok=True)
    eigener_host = web._host(url)

    gefunden: "OrderedDict[str, list[tuple[str, str]]]" = OrderedDict()
    with web.browser(cfg, headless=headless) as kontext:
        seite = kontext.new_page()
        try:
            seite.goto(url, wait_until="domcontentloaded", timeout=120_000)
            with contextlib.suppress(Exception):
                seite.wait_for_load_state("networkidle", timeout=15_000)
            seite.wait_for_timeout(cfg.warte_ms)

            gesehen: set[str] = set()
            for frame in web.rahmen_von(seite):
                with contextlib.suppress(Exception):
                    for eintrag in frame.evaluate(LINK_JS) or []:
                        href = (eintrag.get("href") or "").split("#")[0]
                        if not href.startswith("http") or href in gesehen:
                            continue
                        if web._host(href) != eigener_host:
                            continue
                        gesehen.add(href)
                        gefunden.setdefault(_muster(href), []).append(
                            (href, eintrag.get("text") or "")
                        )
        finally:
            seite.close()

    gruppen = sorted(gefunden.items(), key=lambda p: -len(p[1]))
    marke = schema.dateiname_fuer_url(url)

    zeilen = [
        f"# Linkbericht: {url}", "",
        f"- Erfassungsdatum: {schema.heute()}",
        f"- {sum(len(v) for v in gefunden.values())} Links auf {eigener_host}",
        "", "Nach Pfadform gruppiert, groesste Gruppe zuerst. Die Lektionen eines",
        "Kurses teilen in der Regel eine Form.", "",
    ]
    for form, eintraege in gruppen[:12]:
        zeilen += [f"## `{form}` — {len(eintraege)} Links", ""]
        for href, text in eintraege[:40]:
            zeilen.append(f"- {href} | {text}" if text else f"- {href}")
        if len(eintraege) > 40:
            zeilen.append(f"- … und {len(eintraege) - 40} weitere")
        zeilen.append("")

    bericht = ausgabe / f"{marke}.links.md"
    bericht.write_text("\n".join(zeilen).rstrip() + "\n", encoding="utf-8")

    # Die groesste Gruppe gleich als fertige Liste ablegen.
    liste = None
    if gruppen and len(gruppen[0][1]) > 1:
        liste = ausgabe / f"{marke}.liste.txt"
        inhalt = [
            f"# Aus {url} gesammelt, Pfadform {gruppen[0][0]}",
            "# Zeilen pruefen und sortieren, dann:",
            "#   wissen kurs --liste <diese Datei> --praefix <kurs>",
            "",
        ]
        for href, text in gruppen[0][1]:
            inhalt.append(f"{href} | {text}" if text else href)
        liste.write_text("\n".join(inhalt) + "\n", encoding="utf-8")

    return bericht, liste, [(form, len(e)) for form, e in gruppen]


def _frame_name(frame, nr: int) -> str:
    url = frame.url or ""
    kurz = url if len(url) < 90 else url[:87] + "..."
    return f"Frame {nr}: {kurz or '(ohne URL)'}"


def pruefe(
    cfg: Konfig,
    url: str,
    ausgabe: Path,
    *,
    klicks: list[str] | None = None,
    headless: bool = False,
) -> Path:
    """Schreibt einen Bericht ueber die Seite und gibt dessen Pfad zurueck."""
    ausgabe = Path(ausgabe).expanduser()
    ausgabe.mkdir(parents=True, exist_ok=True)

    zeilen: list[str] = [
        f"# Seitenbericht: {url}",
        "",
        f"- Erfassungsdatum: {schema.heute()}",
        "",
        "Nur gelesen -- es wurde nichts angeklickt ausser den unten genannten",
        "ausdruecklichen `--klick`-Selektoren.",
        "",
    ]
    regeln = dict(cfg.host_regeln(url))
    if klicks:
        regeln["klicks"] = list(klicks)

    with web.browser(cfg, headless=headless) as kontext:
        seite = kontext.new_page()
        try:
            seite.goto(url, wait_until="domcontentloaded", timeout=120_000)
            with contextlib.suppress(Exception):
                seite.wait_for_load_state("networkidle", timeout=15_000)
            seite.wait_for_timeout(cfg.warte_ms)

            if regeln.get("klicks"):
                zeilen += ["## Klicks", ""]
                for meldung in web._oeffne_panel(seite, regeln, cfg.warte_ms):
                    zeilen.append(f"- {meldung}")
                zeilen.append("")

            zeilen += [
                f"## Titel", "",
                f"- `<title>`: {(seite.title() or '').strip()!r}",
            ]
            kopfzeile = seite.query_selector("h1")
            if kopfzeile:
                with contextlib.suppress(Exception):
                    zeilen.append(f"- `h1`: {(kopfzeile.inner_text() or '').strip()!r}")
            zeilen.append("")

            rahmen = web.rahmen_von(seite)
            zeilen += ["## Frames", ""]
            for nr, frame in enumerate(rahmen):
                beschreibung = (
                    f"Hauptdokument: {frame.url}" if nr == 0 else _frame_name(frame, nr)
                )
                laenge = 0
                with contextlib.suppress(Exception):
                    laenge = len(frame.evaluate("() => document.body.innerText || ''"))
                zeilen.append(f"- {beschreibung} — {laenge} Zeichen Text")
            zeilen.append("")

            # Der Lektionstext steckt oft in einem eigenen Frame; das
            # Hauptdokument traegt dann nur die Navigationshuelle.
            zeilen += ["## Seitentext", ""]
            seitentext = web._hauptinhalt(rahmen, regeln)
            if seitentext:
                zeilen += [
                    f"- {len(seitentext)} Zeichen, aus dem textreichsten Frame",
                    f"- Anfang: {seitentext[:200]!r}",
                ]
            else:
                zeilen.append("- kein Fliesstext gefunden")
            zeilen.append("")

            zeilen += ["## Eingebetteter Player", ""]
            spur_vorhanden = False
            video = web.finde_video(rahmen)
            if video is None:
                zeilen.append("- keiner gefunden")
            else:
                video_url, anbieter = video
                zeilen += [f"- {anbieter}: `{video_url}`", ""]
                try:
                    from . import youtube

                    info, proben = youtube.spur_probe(
                        video_url, cfg.sprachen, url, ausgabe,
                        schema.dateiname_fuer_url(url),
                    )
                    zeilen += [
                        f"- Titel: {(info.get('title') or '?')!r}",
                        f"- Dauer: {info.get('duration')} s",
                        "",
                    ]
                    if not proben:
                        vorhanden = sorted(
                            set(info.get("subtitles") or {})
                            | set(info.get("automatic_captions") or {})
                        )
                        zeilen += [
                            "Keine Spur passt zu den Sprachen "
                            f"{', '.join(cfg.sprachen)}.",
                            f"Vorhanden: {', '.join(vorhanden) or 'keine'}.",
                            "In wissen.toml unter [youtube] sprachen anpassen.",
                        ]
                    else:
                        zeilen.append(
                            "Spuren, jeweils wirklich abgerufen "
                            "(Referer = diese Kursseite):"
                        )
                        zeilen.append("")
                        for probe in proben:
                            art = "automatisch" if probe["automatisch"] else "vom Anbieter"
                            zeilen += [
                                f"- **{probe['sprache']}** ({probe['format']}, {art})",
                                f"  - Antwort: {probe['diagnose']}",
                                f"  - daraus gelesene Segmente: {probe['kacheln']}",
                            ]
                            if probe["datei"]:
                                zeilen.append(f"  - Rohdatei: `{probe['datei']}`")
                        zeilen.append("")
                        brauchbar = [p for p in proben if p["kacheln"]]
                        spur_vorhanden = bool(brauchbar)
                        if brauchbar:
                            zeilen.append(
                                "→ **`wissen kurs` kann das Transkript hier holen** "
                                f"(aus `{brauchbar[0]['sprache']}`, "
                                f"{brauchbar[0]['kacheln']} Segmente)."
                            )
                        else:
                            zeilen += [
                                "→ **Spur gefunden, aber ohne lesbaren Inhalt.**",
                                "",
                                "Die Rohdatei oben zeigt, was zurueckkam. Haeufige",
                                "Faelle: eine leere Antwort (0 Bytes), eine",
                                "HTML-Fehlerseite statt der Untertitel, oder ein",
                                "Format, das der Parser nicht kennt.",
                            ]
                except Exception as exc:
                    zeilen += [
                        f"- **Abruf fehlgeschlagen:** {type(exc).__name__}: {exc}",
                        "",
                        "Moegliche Gruende: das Video ist auf die Kursdomain"
                        " beschraenkt und braucht eine Anmeldung, die yt-dlp"
                        " nicht hat, oder der Anbieter wird nicht unterstuetzt.",
                    ]
            zeilen.append("")

            zeilen += ["## Transkript-Kandidaten", ""]
            gefunden = False
            bester: tuple[int, dict] | None = None
            for nr, frame in enumerate(rahmen):
                treffer = erkennung.kandidaten(frame)
                if not treffer:
                    continue
                gefunden = True
                kopf = "Hauptdokument" if nr == 0 else _frame_name(frame, nr)
                zeilen += [f"### {kopf}", ""]
                for kandidat in treffer:
                    zeilen += [
                        f"- **{kandidat['selektor']}**",
                        f"  - gefunden über: {kandidat['grund']}",
                        f"  - Zeitmarken: {kandidat['zeitmarken']}",
                        f"  - Textlänge: {kandidat['textlaenge']}",
                        f"  - sichtbar: {'ja' if kandidat['sichtbar'] else 'nein'}",
                        f"  - Treffer dieses Selektors auf der Seite: "
                        f"{kandidat['eindeutig']}",
                        f"  - Vorschau: {kandidat['vorschau']!r}",
                    ]
                    rang = (
                        0 if kandidat["grund"] == "zeitmarken" else 1,
                        -kandidat["zeitmarken"],
                        -kandidat["textlaenge"],
                    )
                    if bester is None or rang < bester[0]:
                        bester = (rang, kandidat)
                zeilen.append("")

            if not gefunden and spur_vorhanden:
                # Kein Mangel: die Spur des Players ist die bessere Quelle.
                zeilen += [
                    "Keine im DOM — wird hier auch nicht gebraucht, weil der",
                    "eingebettete Player eine Untertitelspur hat (siehe oben).",
                    "`wissen kurs` nimmt diese Spur.",
                    "",
                ]
            elif not gefunden:
                zeilen += [
                    "Keine Kandidaten gefunden. Moegliche Gruende:",
                    "",
                    "- Das Panel ist eingeklappt → oeffnenden Selektor mit",
                    "  `--klick '<selektor>'` mitgeben und erneut pruefen.",
                    "- Die Anmeldung fehlt → `wissen login <url>` ausfuehren.",
                    "- Das Transkript wird erst beim Abspielen geladen.",
                    "",
                ]

            # Rohdaten zum Nachsehen ablegen.
            marke = schema.dateiname_fuer_url(url)
            bild = ausgabe / f"{marke}.png"
            with contextlib.suppress(Exception):
                seite.screenshot(path=str(bild), full_page=True)
                zeilen += ["## Abgelegt", "", f"- Seitenbild: `{bild}`"]
            for nr, frame in enumerate(rahmen):
                with contextlib.suppress(Exception):
                    html = frame.content()
                    datei = ausgabe / f"{marke}.frame{nr}.html"
                    datei.write_text(html, encoding="utf-8")
                    zeilen.append(f"- Frame {nr} HTML: `{datei}`")
            zeilen.append("")

            if bester is not None:
                host = web._host(url)
                zeilen += [
                    "## Vorschlag für wissen.toml",
                    "",
                    "```toml",
                    f'[hosts."{host}"]',
                    f'transkript = ["{bester[1]["selektor"]}"]',
                    "# klicks = [\"<Selektor, der das Panel öffnet>\"]",
                    "```",
                    "",
                ]
        finally:
            seite.close()

    bericht = ausgabe / f"{schema.dateiname_fuer_url(url)}.bericht.md"
    bericht.write_text("\n".join(zeilen).rstrip() + "\n", encoding="utf-8")
    return bericht
