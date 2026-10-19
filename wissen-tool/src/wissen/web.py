"""Online-Kurse hinter Login auslesen.

Gearbeitet wird mit einem dauerhaften Browser-Profil: du loggst dich einmal
von Hand ein (`wissen login`), Chromium behaelt die Sitzung im Profilordner,
und alle spaeteren Aufrufe nutzen sie weiter. Es wird nirgends ein Passwort
gespeichert -- nur die Cookies, die der Browser ohnehin haelt.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from . import schema
from .config import Konfig
from .store import Ablage

#: Kandidaten fuer das Transkript-Panel, wenn in wissen.toml keiner steht.
#: Bewusst grob -- genommen wird der Treffer mit dem meisten Text.
TRANSKRIPT_HEURISTIK = [
    "[data-purpose*='transcript' i]",
    "[class*='transcript' i]",
    "[id*='transcript' i]",
    "[class*='transkript' i]",
    "[id*='transkript' i]",
    "[aria-label*='transcript' i]",
    "[aria-label*='transkript' i]",
]

#: Knoepfe, die ein eingeklapptes Transkript oeffnen.
OEFFNER_HEURISTIK = [
    "button:has-text('Transkript')",
    "button:has-text('Transcript')",
    "button:has-text('Untertitel')",
    "[aria-label*='transcript' i]",
]

MIN_TRANSKRIPT = 200  # Zeichen; darunter ist es eher eine Beschriftung


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
            "navigiere einmal in den Kurs hinein, damit alle Cookies gesetzt sind.\n"
            f"Profil: {cfg.browser_profil}\n"
        )
        input("Danach hier Enter druecken, um den Browser zu schliessen: ")


def _text_von(seite, selektoren: list[str]) -> str:
    """Nimmt vom ersten passenden Selektor den laengsten Textknoten."""
    bester = ""
    for selektor in selektoren:
        try:
            elemente = seite.query_selector_all(selektor)
        except Exception:
            continue
        for element in elemente:
            try:
                text = (element.inner_text() or "").strip()
            except Exception:
                continue
            if len(text) > len(bester):
                bester = text
    return bester


def _hauptinhalt(seite) -> str:
    """Fliesstext der Seite, moeglichst ohne Navigation und Fusszeile."""
    try:
        import trafilatura
    except ImportError:
        trafilatura = None
    if trafilatura is not None:
        try:
            text = trafilatura.extract(
                seite.content(),
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )
            if text and len(text.strip()) > 100:
                return text.strip()
        except Exception:
            pass
    for selektor in ("main", "article", "[role='main']", "body"):
        element = seite.query_selector(selektor)
        if element:
            text = (element.inner_text() or "").strip()
            if len(text) > 100:
                return text
    return (seite.inner_text("body") or "").strip()


def _aufraeumen(text: str) -> str:
    """Mehrfach-Leerzeilen zusammenfassen, Zeilenenden trimmen."""
    zeilen = [z.rstrip() for z in text.replace("\r\n", "\n").split("\n")]
    ergebnis: list[str] = []
    for zeile in zeilen:
        if not zeile and ergebnis and not ergebnis[-1]:
            continue
        ergebnis.append(zeile)
    return "\n".join(ergebnis).strip()


def lade_seite(
    cfg: Konfig,
    ablage: Ablage,
    url: str,
    *,
    kurs: str,
    lektion: int | None = None,
    titel: str | None = None,
    screenshot: bool = False,
    headless: bool = False,
    kontext=None,
    tags: list[str] | None = None,
) -> tuple[Path, dict]:
    """Liest eine Kursseite aus und legt Seitentext plus Transkript ab."""
    if kontext is None:
        with browser(cfg, headless=headless) as neuer_kontext:
            return lade_seite(
                cfg, ablage, url, kurs=kurs, lektion=lektion, titel=titel,
                screenshot=screenshot, kontext=neuer_kontext, tags=tags,
            )

    regeln = cfg.host_regeln(url)
    seite = kontext.new_page()
    try:
        seite.goto(url, wait_until="domcontentloaded", timeout=120_000)
        with contextlib.suppress(Exception):
            seite.wait_for_load_state("networkidle", timeout=15_000)
        seite.wait_for_timeout(cfg.warte_ms)

        # Transkript-Panel ggf. aufklappen.
        for selektor in list(regeln.get("klicks") or []) + OEFFNER_HEURISTIK:
            try:
                element = seite.query_selector(selektor)
                if element and element.is_visible():
                    element.click(timeout=5_000)
                    seite.wait_for_timeout(cfg.warte_ms)
                    break
            except Exception:
                continue

        seiten_titel = titel or (seite.title() or "").strip() or url
        if not titel:
            kopfzeile = seite.query_selector("h1")
            if kopfzeile:
                h1 = (kopfzeile.inner_text() or "").strip()
                if 3 < len(h1) < 200:
                    seiten_titel = h1

        transkript_selektoren = list(regeln.get("transkript") or []) + TRANSKRIPT_HEURISTIK
        transkript = _aufraeumen(_text_von(seite, transkript_selektoren))
        if len(transkript) < MIN_TRANSKRIPT:
            transkript = ""

        inhalt_selektoren = regeln.get("inhalt")
        if inhalt_selektoren:
            seitentext = _aufraeumen(_text_von(seite, list(inhalt_selektoren)))
        else:
            seitentext = _aufraeumen(_hauptinhalt(seite))

        quellen_id = f"kurs-{schema.slugify(kurs)}-{schema.kurz_hash(url)}"
        meta = schema.neues_frontmatter(
            id=f"web:{schema.kurz_hash(url)}",
            typ="kurs",
            titel=seiten_titel,
            quelle=url,
            kurs=schema.slugify(kurs),
            lektion=lektion,
            tags=tags or [],
        )
        meta["hat_transkript"] = bool(transkript)

        if screenshot:
            ordner = ablage.asset_ordner(quellen_id)
            bild = ordner / f"seite-{schema.slugify(seiten_titel, 40)}.png"
            seite.screenshot(path=str(bild), full_page=True)
            meta["assets"] = [ablage.rel(bild)]

        teile = [f"# {seiten_titel}", "", f"Quelle: {url}", ""]
        if transkript:
            teile += ["## Transkript", "", transkript, ""]
        teile += ["## Seitentext", "", seitentext or "_(kein Text gefunden)_"]
        if meta.get("assets"):
            pfad_vorab = ablage.dokument_pfad(meta)
            teile += ["", "## Seitenbild", ""]
            for rel in meta["assets"]:
                teile.append(
                    f"![Seitenbild]({ablage.rel_von(ablage.root / rel, pfad_vorab)})"
                )

        pfad = ablage.schreibe(meta, "\n".join(teile))
        return pfad, meta
    finally:
        seite.close()


def lade_liste(
    cfg: Konfig,
    ablage: Ablage,
    datei: Path,
    *,
    kurs: str,
    screenshot: bool = False,
    headless: bool = False,
    tags: list[str] | None = None,
) -> list[tuple[Path, dict]]:
    """Liest eine Liste von URLs ab -- eine pro Zeile, optional `URL | Titel`.

    Die Zeilennummer wird zur Lektionsnummer, damit die Kursreihenfolge
    erhalten bleibt. Leerzeilen und Zeilen mit `#` werden uebersprungen.
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

    ergebnisse: list[tuple[Path, dict]] = []
    with browser(cfg, headless=headless) as kontext:
        for nr, (url, titel) in enumerate(eintraege, start=1):
            print(f"[{nr}/{len(eintraege)}] {url}")
            try:
                ergebnisse.append(
                    lade_seite(
                        cfg, ablage, url, kurs=kurs, lektion=nr, titel=titel,
                        screenshot=screenshot, kontext=kontext, tags=tags,
                    )
                )
            except Exception as exc:
                print(f"    uebersprungen: {exc}")
    return ergebnisse
