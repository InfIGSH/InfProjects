"""Kursseiten auslesen -- auch wenn das Transkript in einem fremden Frame steckt.

Gearbeitet wird mit einem dauerhaften Browser-Profil: du loggst dich einmal
von Hand ein (`wissen login`), Chromium behaelt die Sitzung im Profilordner,
und alle spaeteren Aufrufe nutzen sie weiter. Es wird nirgends ein Passwort
gespeichert -- nur die Cookies, die der Browser ohnehin haelt.

**Zum Cross-Origin-iframe:** Playwright steuert den Browser von aussen und
erreicht jeden Frame, unabhaengig von dessen Origin. Die Sperre, an der eine
Browser-Erweiterung scheitert, gilt fuer Skripte *in* der Seite. Das
Transcript-Panel eines eingebetteten Players ist damit direkt als Text
lesbar, ohne Scrollen und Screenshots.

**Zum Klicken:** ANLEITUNG.md verbietet Fortschritts- und
"Mark as done"-Buttons. Darum wird hier nie geraten: geklickt wird nur, was
in wissen.toml ausdruecklich als `klicks` steht, und auch das nur, wenn der
Text des Elements nicht nach einem Fortschritts-Button aussieht.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

from . import erkennung, schema, vtt
from .config import Konfig
from .store import Ablage

#: Texte, bei denen nicht geklickt wird -- Fortschritt, Navigation, Abschluss.
#: Greift auch dann, wenn ein konfigurierter Selektor versehentlich passt.
VERBOTENE_TEXTE = [
    "complete", "completed", "mark as", "finish", "finished",
    "abgeschlossen", "erledigt", "als gelesen", "fertig",
    "next lesson", "naechste lektion", "nächste lektion", "weiter zu",
    "submit", "abgeben", "enroll", "einschreiben",
    "delete", "loeschen", "löschen", "abmelden", "log out", "sign out",
]

MIN_TRANSKRIPT = 200  # Zeichen; darunter ist es eher eine Beschriftung

#: Eingebettete Player, deren Untertitelspur yt-dlp direkt holen kann.
#: Das ist der verlaessliche Weg: die Spur statt der Player-Oberflaeche.
VIDEO_MUSTER = [
    (re.compile(r"player\.vimeo\.com/video/"), "Vimeo"),
    (re.compile(r"(?:www\.)?youtube(?:-nocookie)?\.com/embed/"), "YouTube"),
    (re.compile(r"(?:www\.)?youtube\.com/watch"), "YouTube"),
    (re.compile(r"wistia\.(?:net|com)/(?:embed/)?(?:iframe|medias)/"), "Wistia"),
]


class WebFehler(RuntimeError):
    pass


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - Umgebungsproblem
        raise WebFehler(
            "Playwright ist nicht installiert. Im Projektordner: "
            "pip install -e . && playwright install chromium"
        ) from exc
    return sync_playwright


def ist_verboten(text: str) -> bool:
    """Prueft, ob ein Elementtext auf einen Fortschritts-Button hindeutet."""
    klein = (text or "").strip().lower()
    if not klein:
        return False
    return any(wort in klein for wort in VERBOTENE_TEXTE)


@contextlib.contextmanager
def browser(cfg: Konfig, headless: bool = False):
    """Chromium mit dem dauerhaften Profil."""
    cfg.browser_profil.mkdir(parents=True, exist_ok=True)
    with _playwright()() as pw:
        kontext = pw.chromium.launch_persistent_context(
            user_data_dir=str(cfg.browser_profil),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            yield kontext
        finally:
            kontext.close()


def login(cfg: Konfig, url: str) -> None:
    """Oeffnet die Seite sichtbar, damit du dich einmal anmelden kannst."""
    with browser(cfg, headless=False) as kontext:
        seite = kontext.pages[0] if kontext.pages else kontext.new_page()
        seite.goto(url, wait_until="domcontentloaded", timeout=120_000)
        print(
            "\nBrowser ist offen. Melde dich an (inklusive Zwei-Faktor) und\n"
            "navigiere einmal in eine Lektion, damit alle Cookies gesetzt sind.\n"
            f"Profil: {cfg.browser_profil}\n"
        )
        input("Danach hier Enter druecken, um den Browser zu schliessen: ")


# -- Seite vorbereiten ---------------------------------------------------


def _oeffne_panel(seite, regeln: dict, warte_ms: int) -> list[str]:
    """Klickt die konfigurierten Oeffner -- und nur die.

    Rueckgabe: Meldungen darueber, was geklickt und was verweigert wurde.
    """
    meldungen: list[str] = []
    for selektor in regeln.get("klicks") or []:
        for rahmen in [seite] + list(seite.frames):
            try:
                element = rahmen.query_selector(selektor)
            except Exception:
                continue
            if not element:
                continue
            try:
                if not element.is_visible():
                    continue
                beschriftung = " ".join(
                    filter(None, [
                        element.inner_text() or "",
                        element.get_attribute("aria-label") or "",
                        element.get_attribute("title") or "",
                    ])
                )
            except Exception:
                continue
            if ist_verboten(beschriftung):
                meldungen.append(
                    f"NICHT geklickt: {selektor} heisst "
                    f"{beschriftung.strip()[:40]!r} -- sieht nach einem "
                    "Fortschritts-/Navigationsknopf aus."
                )
                break
            try:
                element.click(timeout=5_000)
                seite.wait_for_timeout(warte_ms)
                meldungen.append(f"geklickt: {selektor}")
            except Exception as exc:
                meldungen.append(f"Klick auf {selektor} fehlgeschlagen: {exc}")
            break
    return meldungen


def rahmen_von(seite) -> list:
    """Alle Frames der Seite, Hauptframe an Position 0.

    `page.frames` enthaelt den Hauptframe schon -- ihn zusaetzlich
    voranzustellen wuerde ihn doppelt verarbeiten.
    """
    return list(seite.frames)


def finde_video(rahmen: list) -> tuple[str, str] | None:
    """Sucht einen eingebetteten Player. Rueckgabe: (URL, Anbietername)."""
    for frame in rahmen:
        url = frame.url or ""
        for muster, anbieter in VIDEO_MUSTER:
            if muster.search(url):
                # Der Zeitanker (#t=00h07m05s) ist nur die Abspielposition
                # und verwirrt manche Extraktoren.
                return url.split("#")[0], anbieter
    return None


def _text_aus_selektor(frame, selektor: str) -> str:
    with contextlib.suppress(Exception):
        element = frame.query_selector(selektor)
        if element:
            return (element.inner_text() or "").strip()
    return ""


def _inhalt_geraten(frame) -> str:
    """Fliesstext eines Frames ohne Konfiguration -- mit Plausibilitaetsgrenzen.

    Die Laengengrenzen sind hier richtig: sie sortieren Navigationsreste und
    leere Huellen aus. Bei einem konfigurierten Selektor gelten sie nicht,
    siehe `_hauptinhalt`.
    """
    try:
        import trafilatura
    except ImportError:
        trafilatura = None
    if trafilatura is not None:
        with contextlib.suppress(Exception):
            html = frame.content()
            if html and len(html) > 50:
                text = trafilatura.extract(
                    html, include_comments=False,
                    include_tables=True, favor_recall=True,
                )
                if text and len(text.strip()) > 100:
                    return text.strip()

    for selektor in ("main", "article", "[role='main']", "body"):
        text = _text_aus_selektor(frame, selektor)
        if len(text) > 100:
            return text
    return ""


def _hauptinhalt(rahmen: list, regeln: dict) -> str:
    """Fliesstext der Seite -- quer ueber alle Frames.

    Kursplattformen laden den Lektionstext regelmaessig in ein eigenes
    iframe; im Hauptdokument steht dann nur die Navigationshuelle. Genommen
    wird darum der Frame mit dem meisten Text, nicht das Hauptdokument.

    Ein konfigurierter Selektor geht aber immer vor: wer ihn eintraegt, weiss
    besser, wo der Lektionstext steht -- auch wenn eine Navigationsspalte
    anderswo mehr Zeichen hat.
    """
    for selektor in regeln.get("inhalt") or []:
        bester = ""
        for frame in rahmen:
            text = _text_aus_selektor(frame, selektor)
            if len(text) > len(bester):
                bester = text
        if bester:
            return bester

    bester = ""
    for frame in rahmen:
        text = _inhalt_geraten(frame)
        if len(text) > len(bester):
            bester = text
    return bester


def _transkript_aus_dom(rahmen: list, regeln: dict) -> tuple[str, str]:
    """Sucht ein Transkript-Panel im DOM. Rueckgabe: (text, wie_gefunden)."""
    # Ausdrueckliche Konfiguration gewinnt -- in allen Frames gesucht.
    for selektor in regeln.get("transkript") or []:
        for frame in rahmen:
            with contextlib.suppress(Exception):
                element = frame.query_selector(selektor)
                if element:
                    text = (element.inner_text() or "").strip()
                    if len(text) >= MIN_TRANSKRIPT:
                        return _aufraeumen(text), f"Selektor {selektor}"

    kandidat, frame = erkennung.bester_kandidat(rahmen, MIN_TRANSKRIPT)
    if kandidat is None:
        return "", ""
    with contextlib.suppress(Exception):
        element = frame.query_selector(kandidat["selektor"])
        if element:
            text = (element.inner_text() or "").strip()
            if len(text) >= MIN_TRANSKRIPT:
                wie = (
                    f"automatisch erkannt ({kandidat['grund']}, "
                    f"{kandidat['zeitmarken']} Zeitmarken, "
                    f"Selektor {kandidat['selektor']})"
                )
                return _aufraeumen(text), wie
    return "", ""


def _aufraeumen(text: str) -> str:
    """Mehrfach-Leerzeilen zusammenfassen, Zeilenenden trimmen."""
    zeilen = [z.rstrip() for z in text.replace("\r\n", "\n").split("\n")]
    ergebnis: list[str] = []
    for zeile in zeilen:
        if not zeile and ergebnis and not ergebnis[-1]:
            continue
        ergebnis.append(zeile)
    return "\n".join(ergebnis).strip()


def _letzte_zeitmarke(text: str) -> float | None:
    """Groesste Zeitangabe im Transkript -- fuer die Abdeckungszeile."""
    marken = re.findall(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", text)
    werte = []
    for marke in marken:
        with contextlib.suppress(ValueError):
            werte.append(schema.zeit_zu_sekunden(marke))
    return max(werte) if werte else None


def _transkript_vom_player(
    cfg: Konfig, video: tuple[str, str], seiten_url: str, felder: dict
) -> tuple[str, dict, str]:
    """Holt die Untertitelspur eines eingebetteten Players per yt-dlp.

    Der Referer ist die Kursseite -- Embeds in Kursplattformen sind meist auf
    deren Domain beschraenkt und antworten ohne ihn nicht.
    """
    from . import youtube

    video_url, anbieter = video
    felder["Video"] = f"{anbieter}: {video_url}"
    try:
        spur = youtube.spur_laden(video_url, cfg.sprachen, referer=seiten_url)
    except Exception as exc:
        felder["Abdeckung"] = f"KEIN Transkript — {anbieter}-Spur nicht abrufbar"
        return "", felder, (
            f"{anbieter}-Video gefunden ({video_url}), aber keine Untertitelspur "
            f"abrufbar: {exc}"
        )

    text = vtt.zu_text(spur["kacheln"], cfg.marke_alle, schon_entdoppelt=True)
    dauer = (spur["info"] or {}).get("duration")
    letzte = spur["kacheln"][-1].ende
    luecke = schema.abdeckung_luecke(letzte, dauer)

    felder["Abdeckung"] = schema.abdeckung(letzte, dauer, spur["automatisch"])
    if luecke is not None and luecke > cfg.max_luecke:
        felder["Abdeckung"] += f" — UNVOLLSTÄNDIG, {int(luecke)} s fehlen"
    nachricht = (
        f"Transkript aus dem {anbieter}-Player geholt "
        f"(Sprache {spur['sprache']}, "
        f"{'automatisch' if spur['automatisch'] else 'vom Anbieter'})."
    )
    return text, felder, nachricht


# -- Hauptfunktion -------------------------------------------------------


def lade_seite(
    cfg: Konfig,
    ablage: Ablage,
    url: str,
    *,
    praefix: str,
    kurs: str | None = None,
    modul: str | None = None,
    lektion: str | None = None,
    titel: str | None = None,
    screenshot: bool = False,
    headless: bool = False,
    kontext=None,
) -> tuple[Path, dict, list[str]]:
    """Liest eine Kursseite aus und legt Transkript plus Seitentext im Eingang ab."""
    if kontext is None:
        with browser(cfg, headless=headless) as neuer_kontext:
            return lade_seite(
                cfg, ablage, url, praefix=praefix, kurs=kurs, modul=modul,
                lektion=lektion, titel=titel, screenshot=screenshot,
                kontext=neuer_kontext,
            )

    regeln = cfg.host_regeln(url)
    seite = kontext.new_page()
    meldungen: list[str] = []
    try:
        seite.goto(url, wait_until="domcontentloaded", timeout=120_000)
        with contextlib.suppress(Exception):
            seite.wait_for_load_state("networkidle", timeout=15_000)
        seite.wait_for_timeout(cfg.warte_ms)

        meldungen += _oeffne_panel(seite, regeln, cfg.warte_ms)

        seiten_titel = titel or (seite.title() or "").strip() or url
        if not titel:
            kopfzeile = seite.query_selector("h1")
            if kopfzeile:
                h1 = (kopfzeile.inner_text() or "").strip()
                if 3 < len(h1) < 200:
                    seiten_titel = h1

        rahmen = rahmen_von(seite)
        transkript, wie = _transkript_aus_dom(rahmen, regeln)
        seitentext = _aufraeumen(_hauptinhalt(rahmen, regeln))

        kennung = schema.slugify(lektion or seiten_titel, 50)
        felder = {
            "Titel": seiten_titel,
            "Plattform": (regeln.get("plattform") or _host(url)),
            "Kurs": kurs,
            "Modul": modul,
            "Lektion": lektion,
            "URL": url,
            "Erfassungsdatum": schema.heute(),
        }

        if transkript:
            letzte = _letzte_zeitmarke(transkript)
            felder["Abdeckung"] = (
                f"Transkript bis {schema.zeit_kurz(letzte)} ({wie})"
                if letzte else f"Transkript vorhanden ({wie})"
            )
        else:
            # Kein Panel im DOM -- dann die Untertitelspur des eingebetteten
            # Players holen. Das ist der verlaesslichere Weg: echte
            # Zeitstempel statt abgeschriebener Oberflaeche.
            video = finde_video(rahmen)
            if video:
                transkript, felder, nachricht = _transkript_vom_player(
                    cfg, video, url, felder
                )
                meldungen.append(nachricht)
            else:
                felder["Abdeckung"] = "KEIN Transkript gefunden — nur Seitentext"
                meldungen.append(
                    "Kein Transkript im DOM und kein eingebetteter Player. "
                    "'wissen inspect <url>' zeigt, was auf der Seite steht."
                )

        pfad = ablage.eingang_pfad(praefix, kennung)

        if screenshot:
            ordner = ablage.media_ordner(kennung)
            bild = ordner / "seite.png"
            seite.screenshot(path=str(bild), full_page=True)
            felder["Screenshots"] = ablage.rel(bild)

        teile = []
        if transkript:
            teile += ["## Transkript", "", transkript, ""]
        teile += ["## Seitentext", "", seitentext or "_(kein Text gefunden)_"]
        if felder.get("Screenshots"):
            teile += ["", "## Seitenbild", "",
                      f"![Seitenbild]({ablage.rel_von(bild, pfad)})"]

        ablage.schreibe(felder, "\n".join(teile), pfad)
        return pfad, felder, meldungen
    finally:
        seite.close()


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").replace("www.", "")


def lade_liste(
    cfg: Konfig,
    ablage: Ablage,
    datei: Path,
    *,
    praefix: str,
    kurs: str | None = None,
    screenshot: bool = False,
    headless: bool = False,
) -> list[tuple[Path, dict, list[str]]]:
    """Liest eine Liste von URLs ab -- eine pro Zeile, optional `URL | Titel`.

    Leerzeilen und Zeilen mit `#` werden uebersprungen. Der Browser bleibt
    fuer alle Seiten offen, die Anmeldung gilt also durchgehend.
    """
    eintraege: list[tuple[str, str | None]] = []
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        if "|" in zeile:
            url, _, roh_titel = zeile.partition("|")
            eintraege.append((url.strip(), roh_titel.strip() or None))
        else:
            eintraege.append((zeile, None))

    ergebnisse: list[tuple[Path, dict, list[str]]] = []
    with browser(cfg, headless=headless) as kontext:
        for nr, (url, titel) in enumerate(eintraege, start=1):
            print(f"[{nr}/{len(eintraege)}] {url}")
            try:
                ergebnisse.append(
                    lade_seite(
                        cfg, ablage, url, praefix=praefix, kurs=kurs,
                        lektion=titel, titel=titel, screenshot=screenshot,
                        kontext=kontext,
                    )
                )
            except Exception as exc:
                print(f"    uebersprungen: {exc}")
    return ergebnisse
