"""Read-only course inventory: compare live players with existing source files."""
from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path

from . import web


def bewerte(text: str, videos: list[tuple[str, str]]) -> list[dict]:
    """Distinguish source references from actual timestamped transcript sections."""
    transkript = text.split('## Transkript\n', 1)[-1] if '## Transkript\n' in text else ''
    transkript = transkript.split('\n## ', 1)[0]
    abschnitte = re.split(r'(?m)^### Video \d+\s*$', transkript)
    ergebnis = []
    for url, anbieter in videos:
        muster = re.escape(url) + r"(?=$|[\s;])"
        teile = [t for t in abschnitte if re.search(muster, t)] if len(videos) > 1 else [transkript]
        teil = '\n'.join(teile)
        status = 'Zeitmarken vorhanden; Inhalt und Lücken ungeprüft'
        if not re.search(muster, text):
            status = 'Video fehlt in der Erfassung'
        elif web.ist_einstellungsdialog(teil):
            status = 'Untertitel-Einstellungsdialog statt Transkript'
        elif not re.search(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', teil):
            status = 'Kein zugeordnetes zeitgestempeltes Transkript'
        elif 'KEIN Transkript' in teil or 'UNVOLLSTÄNDIG' in teil:
            status = 'Fehlende oder unvollständige Untertitel; prüfen'
        ergebnis.append({'url': url, 'anbieter': anbieter, 'status': status})
    return ergebnis


def pruefe_kurs(cfg, ablage, liste: Path, ausgabe: Path, *, headless=False) -> Path:
    """Every input receives a result, including navigation errors and missing files."""
    ausgabe.mkdir(parents=True, exist_ok=True)
    bekannt = ablage.bekannte_urls()
    ergebnisse = []
    with web.browser(cfg, headless=headless) as kontext:
        for url, titel in web.lies_liste(liste):
            eintrag = {'url': url, 'titel': titel, 'videos': [], 'hinweise': [], 'fehler': None}
            ergebnisse.append(eintrag)
            seite = None
            try:
                seite = kontext.new_page()
                antwort = seite.goto(url, wait_until='domcontentloaded', timeout=120_000)
                if antwort and antwort.status >= 400:
                    raise RuntimeError(f'HTTP {antwort.status}')
                with contextlib.suppress(Exception):
                    seite.wait_for_load_state('networkidle', timeout=15_000)
                seite.wait_for_timeout(cfg.warte_ms)
                if web._host(seite.url) != web._host(url) or re.search(r'/(login|sign-in)(?:/|$)', seite.url):
                    raise RuntimeError('Umleitung: Anmeldung oder Zugriff prüfen')
                rahmen = web.rahmen_von(seite)
                videos = web.finde_videos(rahmen)
                datei = bekannt.get(ablage.url_marke(url))
                text = datei.read_text(encoding='utf-8') if datei else ''
                eintrag['datei'] = str(datei) if datei else None
                eintrag['videos'] = bewerte(text, videos)
                bekannte_player = {v[0] for v in videos}
                weitere = [q for q in web.frame_quellen(rahmen)
                           if q not in bekannte_player and q.startswith(('http://', 'https://'))
                           and q != seite.url.split('#')[0]
                           and not re.search(r'/student/(?:document/(?:byid|view)/|course/view/)', q)]
                eintrag['weitere_medienquellen'] = weitere
                if weitere:
                    eintrag['hinweise'].append('Weitere Frame-/Medienquellen ohne unterstützten Player: ' + '; '.join(weitere))
                if not datei:
                    eintrag['hinweise'].append('Keine vorhandene Lektionsdatei')
                if not videos:
                    eintrag['hinweise'].append('Kein bekannter Player gefunden; kann Aufgabe, Ressource, Quiz oder unerkanntes Video sein')
                seitentext = text.split('## Seitentext\n', 1)[-1].split('\n## ', 1)[0] if '## Seitentext\n' in text else ''
                if not seitentext.strip() or web.bereinige_seitentext(seitentext) != seitentext.strip():
                    eintrag['hinweise'].append('Seitentext fehlt oder enthält Cookie-Hinweise; Begleitmaterial prüfen')
                eintrag['hinweise'].append('Dynamisch erst nach Interaktion erzeugte Videos sowie Ton, Akkordnamen und inhaltliche Lücken bleiben manuell zu prüfen')
            except Exception as exc:
                eintrag['fehler'] = f'{type(exc).__name__}: {exc}'
            finally:
                if seite is not None:
                    seite.close()
            print(f"Geprüft: {url} ({len(eintrag['videos'])} Player; Fehler: {bool(eintrag['fehler'])})")
    # These reports never modify existing transcripts or progress on the platform.
    (ausgabe / 'kurs-audit.json').write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=2), encoding='utf-8')
    zeilen = ['# Kursprüfung', '',
              f'{len(ergebnisse)} Listeneinträge, {sum(bool(e["fehler"]) for e in ergebnisse)} Abruffehler.', '',
              'Dies ist ein Abgleich mit dem beim Abruf sichtbaren/deklarierten Bestand, kein Vollständigkeitsnachweis.', '']
    for e in ergebnisse:
        zeilen += [f'## {e["titel"] or e["url"]}', '', e['url'], '']
        if e['fehler']:
            zeilen.append(f'- ABRUFFEHLER: {e["fehler"]}')
        for v in e['videos']:
            zeilen.append(f'- {v["url"]}: {v["status"]}')
        zeilen += [f'- {h}' for h in e['hinweise']]
        zeilen.append('')
    bericht = ausgabe / 'kurs-audit.md'
    bericht.write_text('\n'.join(zeilen), encoding='utf-8')
    return bericht
