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
            video = web.finde_video(rahmen)
            if video is None:
                zeilen.append("- keiner gefunden")
            else:
                video_url, anbieter = video
                zeilen += [f"- {anbieter}: `{video_url}`", ""]
                zeilen.append(
                    "Untertitelspuren laut yt-dlp (Referer = diese Kursseite):"
                )
                zeilen.append("")
                try:
                    from . import youtube

                    spuren = youtube.spuren_auflisten(video_url, referer=url)
                    zeilen += [
                        f"- Titel: {spuren['titel']!r}",
                        f"- Dauer: {spuren['dauer']} s",
                        f"- vom Anbieter erstellt: "
                        f"{', '.join(spuren['manuell']) or 'keine'}",
                        f"- automatisch erzeugt: "
                        f"{', '.join(spuren['automatisch']) or 'keine'}",
                    ]
                except Exception as exc:
                    zeilen += [
                        f"- **nicht abrufbar:** {exc}",
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

            if not gefunden:
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
